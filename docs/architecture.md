# DATUM -- architecture

## Layering

```
contracts/datum_lib.py   pure Python, ZERO genlayer imports
                          -- constitution validation, publisher registry,
                             unit conversion, volatile-key stripping,
                             aggregation/equivalence, economics math.
                          -- unit-testable with plain pytest, no runtime.

contracts/Datum.py        gl.Contract storage + transaction glue.
                          -- imports nothing from datum_lib.py at the
                             Python level (Studio rejects sibling
                             imports); scripts/build_bundle.py inlines
                             datum_lib.py's body between two marker
                             comments to produce the single deployable
                             file Studio actually receives.

artifacts/Datum.bundled.py  the generated, single-file deploy artifact.
                          -- docstrings/comments stripped via an AST
                             round-trip (ast.parse -> strip docstrings
                             -> ast.unparse) to stay under the documented
                             52224-byte Studio ceiling with headroom.
                          -- regenerate with `python scripts/build_bundle.py`
                             after ANY edit to datum_lib.py or Datum.py.
                             Never hand-edit the generated file.
```

## Storage model

- `events: TreeMap[str, str]` -- event id (zero-padded decimal string, so
  lexicographic TreeMap order matches creation order) -> JSON record.
- `positions: TreeMap[str, str]` -- `"<event_id>:<address>"` -> JSON
  position (kept for forward-compat with a future multi-party pool; V1's
  1:1 wager model stores side/stake directly on the event record too).
- `creator_open_count: TreeMap[str, u256]` -- enforces `MAX_OPEN_PER_CREATOR`.
- `address_events: TreeMap[str, str]` -- address -> JSON list of event ids,
  backs `get_positions` / `get_activity` pagination.
- `claimable: TreeMap[str, u256]` -- address -> owed GEN balance. `claim()`
  is the only method that actually moves GEN out of the contract; every
  other settlement path (`_settle`, `expire_event`, `recover_refund`,
  `lapse_appeal`) only credits this ledger.
- `treasury_balance: u256` -- accumulated fee + slashed-bond balance.

All persisted maps are `TreeMap` (per this codebase's established,
confirmed-safe pattern), explicitly initialized in `__init__` as
`self.field = TreeMap()` -- never left as a bare class annotation. This
project has multiple differently-typed TreeMap fields
(`TreeMap[str,str]` and `TreeMap[str,u256]`); a prior finding on this
machine ("Mixed TreeMap bare-init crash") showed that 2+ differently-typed
TreeMap fields crash gltest deploy at import time unless every one of them
is explicitly initialized, so `Datum.__init__` initializes all five.

## The 1:1 wager model

A DATUM event is a single symmetric wager: the creator picks a side (YES
or NO) and a stake at `create_event`; exactly one counterparty picks the
opposite side and must match that stake exactly at `accept_event`. This
keeps the pot math and the "stranger cannot accept both sides" invariant
trivial (`acceptor` is `None` until the first accept; any second
`accept_event` call raises `"already accepted"`). A future version could
generalize to a pooled market; V1 keeps the API surface (`get_position`,
`get_positions`) shaped so that generalization would not require a
breaking read-side change.

## The non-deterministic adjudication call

`adjudicate()` makes exactly one top-level `gl.vm.run_nondet_unsafe(leader_fn,
validator_fn)` call. `leader_fn` calls `gl.nondet.exec_prompt` once with a
frozen prompt template (`_adjudication_prompt`) built only from plain,
already-validated local values (never `self.*`, so no consensus-state leak
into the closure). `validator_fn` parses the leader's returned JSON and
runs it through `datum_lib.evaluate_envelope` -- the exact same function
called again, deterministically, on the accepted `raw_envelope` afterward
to derive the stored verdict/code/agreed_value. This means the "does code
trust the model's own verdict field" question has one factual answer:
no -- `evaluate_envelope` always re-derives verdict/code from
`envelope["sources"]` and rejects the whole envelope on any mismatch.

## Why `run_nondet_unsafe` and not `strict_eq`

Per this codebase's own prior findings (`authorization-proof-settler`,
`independent-evidence-settler`): `gl.eq_principle.strict_eq`'s validator
path cannot be exercised in gltest direct-mode (`spawn_sandbox` needs an
uninstalled `cloudpickle`), while `run_nondet_unsafe`'s `validator_fn` is
independently, directly testable via `direct_vm.run_validator(...)`. Raw
HTTP/JSON responses across two independently-fetched publishers are also
never expected to be byte-identical (headers, volatile generation
timestamps, key order), which rules out `strict_eq` on raw payloads
regardless -- DATUM needs a custom comparator over the *derived* reading,
not the raw bytes, which is exactly what `evaluate_envelope` is.

## Funds flow

`create_event` and `accept_event` are `@gl.public.write.payable` and hold
the attached GEN in the contract's own balance (no outbound transfer).
Every settlement path (`_settle` on `finalize`, `cancel_event`,
`expire_event`, `recover_refund`, `lapse_appeal`) only credits the
`claimable` ledger -- it is `claim()` alone that performs the contract's
one `emit_transfer` call, always to `gl.message.sender_address` (never to
an address argument), paying that caller's *entire* claimable balance in
one shot. This is what prevents the "last claimant stranded by rounding
dust" failure mode: `claim()` never tries to split a pot at call time --
all pro-rata math (`datum_lib.payout_shares`) already happened once, at
settlement time, when each side's share was computed and credited.

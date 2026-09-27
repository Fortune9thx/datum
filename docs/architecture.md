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
  `get_position`/`get_positions` read side/stake straight off this record
  (V1's 1:1 wager model has no separate per-position row to maintain).
- `creator_open_count: TreeMap[str, u256]` -- enforces `MAX_OPEN_PER_CREATOR`.
- `address_events: TreeMap[str, str]` -- address -> JSON list of event ids,
  backs `get_positions` / `get_activity` pagination.
- `claimable: TreeMap[str, u256]` -- address -> owed GEN balance. `claim()`
  is the only method that actually moves GEN out of the contract; every
  other settlement path (`_settle`, `expire_event`, `recover_refund`,
  `lapse_appeal`) only credits this ledger.
- `treasury: str` -- a constructor-immutable address, not a counter. Fee
  shares and forfeited bonds are `_credit()`-ed to this address's
  `claimable` balance exactly like any other party's, and withdrawn
  through the same `claim()` path -- there is no separate counter-based
  treasury ledger that could accumulate value with no withdrawal method.

`Datum.__init__(self, treasury: str)` only assigns this one scalar field.
Every `TreeMap` field is left as a bare class annotation. The storage
generator (`Contract.__init_subclass__` -> `generate_storage`)
auto-allocates every declared persistent field at class-definition time
and rejects a hand-rolled `TreeMap()` call inside `__init__`
(`GenerationError: generic storage classes can not be instantiated with
__init__`).

## The 1:1 wager model

A DATUM event is a single symmetric wager: the creator picks a side (YES
or NO) and a stake at `create_event`; exactly one counterparty picks the
opposite side and must match that stake exactly at `accept_event`. This
keeps the pot math and the "stranger cannot accept both sides" invariant
trivial (`acceptor` is `None` until the first accept; any second
`accept_event` call is refused -- in practice it surfaces `"not open"`
rather than the more specific `"already accepted"` string, since the
state check runs first and `acceptor is not None` is consequently
unreachable; both refuse correctly, only the message differs, see
docs/audit.md). A future version could
generalize to a pooled market; V1 keeps the API surface (`get_position`,
`get_positions`) shaped so that generalization would not require a
breaking read-side change.

## The non-deterministic adjudication call

`adjudicate()` makes exactly one top-level `gl.vm.run_nondet(leader_fn,
validator_fn)` call. `leader_fn` does two things, in order, both inside the
same closure: first, for each of the event's locked publishers, it builds
the exact query URL from already-locked constitution fields only
(`build_publisher_url` -- station id/bbox/window, never anything caller- or
model-supplied) and calls `gl.nondet.web.get()` itself; second, it hands
the model the already-fetched raw responses and calls
`gl.nondet.exec_prompt` once, instructing it to interpret that text and
echo it back verbatim, never to retrieve anything on its own. Multiple
`web.get()` calls followed by one `exec_prompt` call, all inside a single
`leader_fn`, is the documented-safe shape for `genvm-lint`'s
one-non-deterministic-call-per-method rule -- the rule is about nested
top-level calls, not about how many nondet primitives a single leader
function uses internally.

`validator_fn` **calls `leader_fn()` again itself** -- a fresh, independent
round of fetches plus a fresh `exec_prompt` call, not a re-read of the
leader's own claimed result -- and runs `datum_lib.evaluate_envelope` on
BOTH the leader's envelope and its own independently-fetched one, accepting
only if the two independently-derived (verdict, code, agreed_value)
outcomes agree. A leader that fabricated a self-consistent-but-fictional
envelope cannot pass unless the validator's own independent fetch agrees.

`validator_fn`'s parameter is a `gl.vm.Return`/`VMError` wrapper, not the
leader's raw return value -- `getattr(leader_result, "calldata", None)`
unwraps it before parsing. An earlier version of this method did
`json.loads(str(leader_result))` directly: `str()` on the wrapper produces
its Python repr (`Return(calldata='...')`), never valid JSON, so every call
fell into the `except` branch and `validator_fn` returned `False`
unconditionally on a real network -- invisible locally because `gltest`'s
own `run_nondet` mock never enforces `validator_fn`'s return value on the
outer result at all (see `docs/testing.md`).

Two whole-envelope bindings run before any per-source check: the envelope's
`event_id` must match the event actually being adjudicated, and every key
in `sources` must be one of this event's own locked `publishers`.

Per source, `validate_source_reading` checks the claimed `"raw"` field
against the REAL text `leader_fn` actually fetched for that publisher on
that call (`stable_digest` comparison, tolerant of volatile formatting
noise, not of a substantively different body) -- a source whose citation
doesn't match, or whose fetch failed outright, is refused regardless of how
plausible its other claimed fields look. Since the leader and each
validator run as separate processes with no shared memory, this ground
truth is always "what THIS node itself just fetched," compared against
what the SAME node's own model call claims to have read (catching a model
that fabricates its citation) and against what the OTHER side (leader vs.
validator) claimed (via the existing verdict/code/agreed_value comparison
above). The outer, post-consensus evaluation that actually writes
`accepted_record` has no fetch of its own to check against -- by the time
it runs, at least one validator has already verified the accepted
envelope's citations during consensus itself.

## Why `run_nondet` and not `strict_eq`

`gl.eq_principle.strict_eq`'s validator path cannot be exercised in
`gltest` direct-mode (`spawn_sandbox` needs an uninstalled `cloudpickle`),
while `run_nondet`'s `validator_fn` is independently, directly testable
via `direct_vm.run_validator(...)`. Raw
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

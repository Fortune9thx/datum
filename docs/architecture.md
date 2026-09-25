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
  `claimable` balance exactly like any other party's -- there is no
  separate, undrainable treasury ledger. (An earlier version of this
  contract accumulated a `treasury_balance: u256` counter with no
  withdrawal method at all, permanently stranding every fee and slashed
  bond; fixed by routing treasury through the same tested ledger everyone
  else uses. See CHANGELOG.md.)

`Datum.__init__(self, treasury: str)` only assigns this one scalar field.
Every `TreeMap` field is left as a bare class annotation -- this SDK
generation's storage generator (`Contract.__init_subclass__` ->
`generate_storage`) auto-allocates every declared persistent field at
class-definition time and rejects a hand-rolled `TreeMap()` call inside
`__init__` outright (`GenerationError: generic storage classes can not be
instantiated with __init__`). This supersedes an earlier, differently
-behaved SDK generation this codebase had previously confirmed safe with
explicit `self.field = TreeMap()` init (see project memory
`genlayer-treemap-explicit-init-safe` for the version-dependent history)
-- treat that pattern as version-dependent, not universal, going forward.

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
validator_fn)` call. `leader_fn` calls `gl.nondet.exec_prompt` once with a
frozen prompt template (`_adjudication_prompt`) built only from plain,
already-validated local values (never `self.*`, so no consensus-state leak
into the closure). `validator_fn` **calls `leader_fn()` again itself** --
a fresh, independent `gl.nondet.exec_prompt` call, not a re-read of the
leader's own claimed result -- runs `datum_lib.evaluate_envelope` on BOTH
the leader's envelope and its own independently-fetched one, and only
accepts if the two independently-derived (verdict, code, agreed_value)
outcomes agree. A leader that fabricated a self-consistent-but-fictional
envelope (right shape, internally coherent, but not what the real
publishers actually returned) would pass a structural-only check; it
cannot pass this one unless the validator's own independent fetch agrees.

This was a real, confirmed bug in an earlier version of this contract:
`validator_fn` originally only ran `evaluate_envelope` on the LEADER's own
claimed JSON, checking internal self-consistency (does the claimed
verdict match the claimed sources) without ever independently re-acquiring
the underlying publisher data itself. That is exactly the pattern behind
multiple real GenLayer steward rejections on prior projects on this
machine (project memory `genlayer-master-audit-prompt` items 4/60/65:
"a validator function that only checks the leader's output is well-formed
... without independently re-deriving its own answer ... will be rejected
by GenLayer stewards"). Fixed by having `validator_fn` call `leader_fn()`
a second time and compare two independent derivations, per the
established correct pattern -- both to `evaluate_envelope` calls' outputs,
never to the leader's own claimed verdict/code fields directly. This means
the "does code trust the model's own verdict field, or even the model's
own claimed evidence" question has one factual answer: no -- every
accepted record reflects two independently-executed prompt calls that
agreed, not one call trusted at face value.

## Why `run_nondet` and not `strict_eq`

Per this codebase's own prior findings (`authorization-proof-settler`,
`independent-evidence-settler`): `gl.eq_principle.strict_eq`'s validator
path cannot be exercised in gltest direct-mode (`spawn_sandbox` needs an
uninstalled `cloudpickle`), while `run_nondet`'s `validator_fn` is
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

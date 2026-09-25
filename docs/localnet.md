# Running DATUM locally, without Studio Dev

Studio Dev's hosted deploy is currently blocked by an infra-side FeeManager
revert (`FeeValueMustBeNonZero`) unrelated to this contract -- see
`docs/STATUS.md` for the full proof. This document is the local substitute:
real evidence that `contracts/Datum.py` actually works, captured without
depending on Studio Dev at all.

Two local paths exist. This project uses the first one, which is real and
already passing; the second is documented for completeness but was not
exercised on this machine.

## Path A -- `gltest` direct-mode (used, passing)

`gltest` runs the contract's compiled bundle inside a real GenVM sandbox
(the same runner build Studio Dev itself uses, resolved from the
contract's own `Depends` header) in a single Python process, with a
Foundry-style cheatcode API for sender/value/time instead of a real
multi-node network. It is not a full consensus simulation -- there is no
second validator to disagree with the leader -- but the contract-class,
storage-allocation, event-emission, and write/view dispatch machinery it
exercises is the real GenVM implementation, not a mock of it.

### Setup (already done in this repo, documented for reuse elsewhere)

```bash
pip install genlayer-test genvm-linter
```

Getting `gltest` to actually deploy this contract required two fixes now
baked into the repo (see CHANGELOG.md's 1.1.2 entry for the full story):

- `contracts/Datum.py` uses the current SDK's real API
  (`import genlayer as gl`, `gl.contract.Contract`, `gl.chain.Event`,
  `gl.vm.run_nondet`) instead of stale pre-v0.3.0 names.
- `Datum.__init__` is empty -- this SDK's storage generator auto-allocates
  every declared `TreeMap`/scalar field at class-definition time, and
  rejects a hand-rolled `TreeMap()` call inside `__init__`.

If `gltest` still can't resolve the runner bundle for this project's
pinned hash (`5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`),
check whether it's already cached under a *different* `sdk_version`
string than expected:

```bash
find ~/.cache/gltest-direct/trees-v2/*/runners/py-genlayer/5j 2>/dev/null
```

On this machine it resolves under `v0.6.0-rc6` (and `v0.6.0-rc5`), not
`v0.3.0`/`v0.2.16` despite the contract predating that naming.

### Run it

```bash
cd C:\Users\HP\Desktop\datum
python scripts/build_bundle.py
python -m pytest tests/direct/test_datum_contract.py -q
```

**Real captured output (2026-09-25):**

```
$ python -m pytest tests/direct/test_datum_contract.py -q
.........                                                                [100%]
9 passed in 5.89s
```

### What the 9 tests actually prove

| Test | What it exercises |
|---|---|
| `test_create_event_returns_id_and_freezes_hash` | Real deploy, `create_event` with real GEN attached (`direct_vm.value`), `get_constitution` returns a 64-char sha256 hash |
| `test_accept_moves_to_active` | A second account (`direct_vm.prank(direct_bob)`) accepts the opposite side; `get_event` shows `state == "ACTIVE"` |
| `test_reject_short_window` | `create_event` refuses a window below the class minimum, before any value is checked |
| `test_reject_single_publisher` | `create_event` refuses a constitution naming only one publisher |
| `test_reject_below_min_lead` | `create_event` refuses a window starting too soon relative to real chain time |
| `test_second_accept_rejected` | A second `accept_event` on an already-ACTIVE event is refused |
| `test_creator_can_cancel_before_accept` | The creator can `cancel_event` before anyone accepts; state moves to `CANCELED` |
| `test_stranger_cannot_cancel` | A non-creator calling `cancel_event` is refused with `"not a party"` |
| `test_adjudicate_before_window_close_rejected` | `adjudicate` refuses to run before the locked window has actually closed |

### What this does *not* prove

- **No real validator disagreement.** `gltest` direct-mode has one
  in-process "leader"; it cannot exercise genuine multi-validator
  equivalence-principle disagreement. `gl.vm.run_nondet`'s validator
  closure can be invoked manually via `direct_vm.run_validator(...)` for
  a narrower unit-style check of that logic in isolation, not attempted
  here.
- **No real LLM call.** `adjudicate()`'s `gl.nondet.exec_prompt` call was
  not exercised end-to-end with a mocked or live model response in this
  pass (the one adjudicate test here only proves the window-not-closed
  *guard*, which runs before the prompt is ever built). A follow-up pass
  worth doing: `direct_vm.mock_llm(pattern, response)` for a CLEAR/YES,
  a MISSING/INCONCLUSIVE, and a CONFLICT/INCONCLUSIVE envelope, to prove
  `evaluate_envelope`'s three outcome paths end-to-end through the real
  contract method, not just through `datum_lib`'s own unit tests (which
  already cover `evaluate_envelope` directly and thoroughly).
- **No real GEN economics.** `direct_vm.value` is a cheatcode, not a real
  balance -- fee deduction, bond slashing, and payout math are proven at
  the `datum_lib` unit-test level (`TestEconomics` in
  `test_datum_lib.py`), not through this file's real-money accounting.

## Path B -- `genlayer up` (full localnet, not exercised on this machine)

`genlayer up` starts GenLayer's own Docker-based localnet simulator (a
real multi-validator network, not a single-process mock), which is the
more complete local substitute for a hosted network. **This machine has
no Docker installed**, so this path was not attempted here -- documented
for whoever picks this up next, on a machine that has it:

```bash
genlayer up --numValidators 5
genlayer network set localnet
genlayer deploy --contract artifacts/Datum.bundled.py --args []
```

Then run the same create -> accept -> (wait for window close) -> adjudicate
-> claim / recover_refund flow either through the CLI's `write`/`call`
commands or through `tests/integration/` (see `RUNBOOK.md`), against the
localnet RPC instead of Studio Dev's.

## What a steward should see in `get_record` after a real adjudication

Whether reached via Path A (with a mocked LLM response) or Path B (a real
model call against localnet), a decisive `CLEAR` outcome's `get_record`
should look like:

```json
{
  "verdict": "YES",
  "code": "CLEAR",
  "agreed_value": 361,
  "accepted_record": {
    "sources": {
      "USGS_WATER": {"usable": true, "station_id": "01646500", "unit": "m", "converted": 362, "product_status": "FINAL"},
      "NOAA_NWPS":  {"usable": true, "station_id": "01646500", "unit": "m", "converted": 360, "product_status": "FINAL"}
    },
    "verdict": "YES",
    "code": "CLEAR"
  },
  "state": "VERDICT_PENDING"
}
```

`agreed_value` is the VALUE_SCALE-scaled average of the usable readings
(361 = 3.61m). A `MISSING`/`CONFLICT`/`PRELIMINARY_BLOCKED` outcome looks
identical in shape but with `verdict: "INCONCLUSIVE"`, `agreed_value:
null`, and each unusable source's `reason` field populated instead of
`converted`.

# Testing

Two layers of tests, both run without needing a live deployment.

## Unit tests

`contracts/datum_lib.py` has no GenLayer imports, so it runs under plain `pytest` with no runtime dependency:

```bash
python -m pytest tests/direct/test_datum_lib.py -q
```

64 tests covering constitution validation, unit conversion, volatile-key stripping, the full envelope acceptance/rejection logic, economics (fee split, appeal bond floor, payout rounding), and comparator behavior: given two independently-derived envelopes, the contract's equivalence logic accepts only when they agree and rejects on any disagreement in usability, station id, tolerance, or window.

## Integration tests (`gltest`)

`gltest` deploys the compiled bundle into a real GenVM sandbox and exercises the full contract surface:

```bash
python scripts/build_bundle.py
python -m pytest tests/direct/test_datum_contract.py -q
```

27 tests, covering both the success path and the refusal path for every one of the twelve write methods: `create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`, `recover_refund`, `reclaim_bonds`. Payable calls attach real value via `direct_vm.value`; multi-account flows use `direct_vm.prank`.

`gltest` clears its own `artifacts/` output directory at session start, so rebuild the bundle before each run.

### What `gltest` proves and what it doesn't

`gltest` runs the real GenVM runtime in a single process, with one in-process leader standing in for the network. It genuinely exercises storage allocation, event emission, write/view dispatch, and the non-deterministic adjudication call — this is not a mock of the contract's logic.

It cannot simulate two independent validators disagreeing over the network, since there is only one process. The adjudication comparator itself — the logic that would reject a disagreeing leader — is proven independently at the `datum_lib` level (`TestLyingLeaderDetection` in `test_datum_lib.py`) and exercised end-to-end through `gltest`, but a live multi-validator disagreement has not been captured against a real network.

## Static analysis

```bash
PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
```

Runs AST-based safety checks and full schema validation against the deployable bundle.

## Full local check

```bash
python scripts/build_bundle.py
python -m pytest tests/direct/ -q
PYTHONIOENCODING=utf-8 genvm-lint check artifacts/Datum.bundled.py
```

## Sample adjudication record

A decisive `CLEAR` outcome's `get_record` looks like:

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

`agreed_value` is the `VALUE_SCALE`-scaled average of the usable readings (361 = 3.61m). A `MISSING`, `CONFLICT`, or `PRELIMINARY_BLOCKED` outcome has the same shape with `verdict: "INCONCLUSIVE"`, `agreed_value: null`, and each unusable source's `reason` field populated instead of `converted`.

## Full local network (optional)

`genlayer up` starts a Docker-based localnet with real multi-validator consensus, closer to production than `gltest`'s single-process sandbox:

```bash
genlayer up --numValidators 5
genlayer network set localnet
genlayer deploy --contract artifacts/Datum.bundled.py --args '"0xYOUR_TREASURY_ADDRESS"'
```

Then run the same create → accept → adjudicate → claim flow through `genlayer write`/`genlayer call` against the localnet RPC.

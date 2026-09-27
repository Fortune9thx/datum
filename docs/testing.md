# Testing

Two layers of tests, both run without needing a live deployment.

## Unit tests

`contracts/datum_lib.py` has no GenLayer imports, so it runs under plain `pytest` with no runtime dependency:

```bash
python -m pytest tests/direct/test_datum_lib.py -q
```

83 tests covering constitution validation, unit conversion, volatile-key stripping, the full envelope acceptance/rejection logic, economics (fee split, appeal bond floor, payout rounding), and comparator behavior: given two independently-derived envelopes, the contract's equivalence logic accepts only when they agree and rejects on any disagreement in usability, station id, tolerance, or window. Also covers envelope-level binding (an envelope claiming the wrong `event_id`, or containing a `sources` key that isn't one of the locked `publishers`, is refused outright), the real publisher URL builder (`build_publisher_url` — every locked publisher's actual query endpoint, built only from constitution fields), and the raw-citation authentication check (a source's claimed `"raw"` is verified against a code-side fetch ground truth, not just hashed and trusted).

## Integration tests (`gltest`)

`gltest` deploys the compiled bundle into a real GenVM sandbox and exercises the full contract surface:

```bash
python scripts/build_bundle.py
python -m pytest tests/direct/test_datum_contract.py -q
```

33 tests, covering both the success path and the refusal path for every one of the twelve write methods: `create_event`, `accept_event`, `adjudicate`, `finalize`, `appeal`, `re_adjudicate`, `lapse_appeal`, `cancel_event`, `expire_event`, `claim`, `recover_refund`, `reclaim_bonds`. Payable calls attach real value via `direct_vm.value`; multi-account flows use `direct_vm.prank`. Several of these exercise the event-id/publisher-key binding and evidence-provenance schema against a real deploy, not just the pure-logic level.

`gltest` clears its own `artifacts/` output directory at session start, so rebuild the bundle before each run.

### What `gltest` proves and what it doesn't

`gltest` runs the real GenVM runtime in a single process, with one in-process leader standing in for the network. It genuinely exercises storage allocation, event emission, write/view dispatch, and the non-deterministic adjudication call — this is not a mock of the contract's logic.

**`gltest`'s own `run_nondet` mock never enforces `validator_fn`'s return value on `adjudicate()`'s outer result** — it calls the leader once and returns that result regardless of what the captured `validator_fn` would compute. A test that only calls `contract.adjudicate(...)` and checks the outcome proves nothing about `validator_fn` at all; this is exactly how a real, critical bug in this contract's `validator_fn` (it unwrapped the leader's result incorrectly and would have returned `False` unconditionally on a real network — see `docs/architecture.md`) went undetected through this project's own full test suite for as long as it did. `direct_vm.run_validator(leader_result=...)` is the documented way around this: it invokes the real captured `validator_fn` with a genuine `gl.vm.Return` wrapper, mocks still apply (swap them between the `adjudicate()` call and `run_validator()` to simulate the validator seeing different external data), and this is the only path in this suite that actually proves the validator's own logic — see `TestValidatorFnRealFetchAndAuthentication` in `test_datum_contract.py`.

It cannot simulate two independent validators disagreeing over the network, since there is only one process. The adjudication comparator itself is proven independently at the `datum_lib` level (`TestLyingLeaderDetection`) and, via `run_validator()`, through the real contract-level closure in `gltest` — but a live multi-validator disagreement over a real network has not been captured end-to-end.

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
genlayer deploy --contract artifacts/Datum.bundled.py --args 0xYOUR_TREASURY_ADDRESS
```

Then run the same create → accept → adjudicate → claim flow through `genlayer write`/`genlayer call` against the localnet RPC.

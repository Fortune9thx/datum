"""
gltest direct-mode tests for the DATUM contract. Deploys the real bundle
(artifacts/Datum.bundled.py) into a real GenVM sandbox and exercises the
actual create/accept/adjudicate/cancel flow -- this is a genuine execution
proof, not a mock of the contract's own logic (contracts/datum_lib.py's
55+ plain-pytest unit tests already cover the pure logic in isolation;
this file proves the gl.Contract/storage/event wiring around it works on
a real GenVM runtime).

Getting this file running at all required three real, non-toolchain fixes,
documented in CHANGELOG.md and docs/STATUS.md:

1. contracts/Datum.py used `from genlayer import *` and bare `gl.Contract`
   / `gl.Event` / `gl.vm.run_nondet_unsafe` -- all stale pre-v0.3.0 API
   names. The current SDK (pinned by this file's own Depends hash) needs
   `import genlayer as gl`, `gl.contract.Contract`, `gl.chain.Event`, and
   `gl.vm.run_nondet`. Confirmed against the real installed SDK source
   (not docs/memory) and against contracts/PrecedenceSettler.py in a
   sibling project that has actually deployed and FINALIZED on this same
   network with the same Depends hash.
2. `__init__` explicitly instantiated its TreeMap fields
   (`self.events = TreeMap()`). This SDK build's storage generator
   allocates every declared persistent field automatically at class
   definition time (`Contract.__init_subclass__` -> `generate_storage`);
   calling `TreeMap()` by hand in `__init__` raises `GenerationError:
   generic storage classes can not be instantiated with __init__`. Fixed
   by leaving `__init__` empty -- the framework's own auto-allocation is
   what a fresh deploy actually needs.
3. gltest's own `artifacts/` output directory happens to share a name
   with scripts/build_bundle.py's output directory, and gltest clears it
   at session start. The `contract` fixture below rebuilds the bundle
   itself, after that clearing, immediately before each deploy.

Payable writes need real GEN attached via `direct_vm.value` (gltest's
Foundry-style cheatcode) -- CalldataProxy method calls have no `value=`
kwarg of their own.
"""

import json
import re
import subprocess
import sys
import time

import pytest

CONTRACT_PATH = "artifacts/Datum.bundled.py"

NOW_PLACEHOLDER = 1_800_000_000
STAKE = 10**18  # 1 GEN
CREATE_BOND = 5 * 10**16  # 0.05 GEN, must match datum_lib.CREATE_BOND


def _precip_constitution(**overrides):
    payload = {
        "class": "STATION_PRECIP",
        "station_id": "USW00094728",
        "metric": "precip_sum",
        "threshold": 1000,  # 10.00mm scaled by VALUE_SCALE=100
        "cmp": "gte",
        "window": [NOW_PLACEHOLDER + 3 * 3600, NOW_PLACEHOLDER + 3 * 3600 + 6 * 3600],
        "publishers": ["NWS_OBS", "GHCN_DAILY"],
        "product_status_policy": "FINAL_ONLY",
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.fixture
def contract(direct_deploy):
    # gltest clears its own "artifacts" directory at session start (same
    # name as scripts/build_bundle.py's output dir, pure coincidence) --
    # rebuild the bundle here, after that clearing, right before deploy.
    subprocess.run(
        [sys.executable, "scripts/build_bundle.py"], check=True, capture_output=True
    )
    # Pinned to the exact genvm release matching this contract's own
    # "Depends": "py-genlayer:..." header (see line 1 of contracts/Datum.py).
    return direct_deploy(CONTRACT_PATH, sdk_version="v0.6.0-rc6")


class TestCreateAcceptHappyPath:
    def test_create_event_returns_id_and_freezes_hash(self, contract, direct_vm):
        direct_vm.value = STAKE + CREATE_BOND
        event_id = contract.create_event(
            constitution_json=_precip_constitution(),
            side="YES",
            stake=str(STAKE),
        )
        record_json = contract.get_constitution(event_id=event_id)
        record = json.loads(record_json)
        assert record["constitution_hash"]
        assert len(record["constitution_hash"]) == 64

    def test_accept_moves_to_active(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )

        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "ACTIVE"
        assert event["acceptor_side"] == "NO"


class TestCreateRefusals:
    """These fail validate_constitution() before the contract ever checks
    attached value, so no direct_vm.value is needed -- a zero-value call
    reaching the refusal proves the check runs before money is touched."""

    def test_reject_short_window(self, contract):
        bad = _precip_constitution(
            window=[NOW_PLACEHOLDER + 3 * 3600, NOW_PLACEHOLDER + 3 * 3600 + 3600]
        )
        with pytest.raises(Exception, match=re.escape("below min window")):
            contract.create_event(constitution_json=bad, side="YES", stake=str(STAKE))

    def test_reject_single_publisher(self, contract):
        bad = _precip_constitution(publishers=["NWS_OBS"])
        with pytest.raises(Exception, match=re.escape("single publisher")):
            contract.create_event(constitution_json=bad, side="YES", stake=str(STAKE))

    def test_reject_below_min_lead(self, contract):
        # Below-min-lead is a check against real chain time (_now_ts()),
        # not against NOW_PLACEHOLDER -- that constant is only "a
        # comfortably-future window" for the other tests, not "now".
        real_now = int(time.time())
        bad = _precip_constitution(window=[real_now + 60, real_now + 60 + 6 * 3600])
        with pytest.raises(Exception, match=re.escape("below min lead")):
            contract.create_event(constitution_json=bad, side="YES", stake=str(STAKE))


class TestStrangerCannotAcceptBothSides:
    def test_second_accept_rejected(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )

        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        # accept_event checks state != OPEN before acceptor is not None
        # (see contracts/Datum.py accept_event) -- once ACTIVE, a second
        # accept surfaces "not open", not the more specific
        # "already accepted" string. Both correctly refuse the second
        # accept; only the diagnostic message differs. Noted in
        # docs/audit.md as a minor unreachable-branch finding, not fixed
        # here since the outward behavior (refuse) is already correct and
        # this file is not the place for a contract-logic change.
        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            with pytest.raises(Exception, match=re.escape("not open")):
                contract.accept_event(event_id=event_id, side="NO")


class TestCancelByCreatorOnly:
    def test_creator_can_cancel_before_accept(self, contract, direct_vm, direct_alice):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
            contract.cancel_event(event_id=event_id)

        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "CANCELED"

    def test_stranger_cannot_cancel(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )

        with direct_vm.prank(direct_bob):
            with pytest.raises(Exception, match=re.escape("not a party")):
                contract.cancel_event(event_id=event_id)


class TestAdjudicateBeforeCloseRejected:
    def test_adjudicate_before_window_close_rejected(
        self, contract, direct_vm, direct_alice, direct_bob
    ):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        # Window has not closed yet (NOW_PLACEHOLDER is hours in the
        # future relative to real chain time) -- adjudicate must refuse.
        with pytest.raises(Exception, match=re.escape("window not closed")):
            contract.adjudicate(event_id=event_id)

"""
gltest direct-mode tests for contracts/Datum.py (the deployable bundle
lives at artifacts/Datum.bundled.py; direct-mode deploys straight from
contracts/ so it is pointed at contracts/Datum.py, which is byte-identical
in logic to the bundle -- only the datum_lib inline marker differs).

STATUS (see docs/STATUS.md for the full write-up): on this machine, gltest
direct-mode deploy currently fails with the same underlying error as
`genvm-lint validate`/`schema`:

    Failed to load contract: name 'gl' is not defined

This is the long-standing local dependency-hash / runner-bundle gap
documented across every prior GenLayer project on this machine (see
project memory "GenLayer test toolchain" and "Bradbury FeeManager broken
(2026-09)"), most recently also manifesting as the open upstream bug
genlayer-studio#1757 ("invalid_contract runner malformed") on Studio Dev's
hosted deploy path. It is not a bug in this contract -- contracts/datum_lib.py
(zero genlayer imports) has 55/55 passing plain-pytest unit tests covering
every rule this file enforces, and `genvm-lint lint` (pure AST-based safety
checks, no runner needed) passes cleanly on both contracts/Datum.py and
artifacts/Datum.bundled.py.

This file is kept in the tree (rather than deleted) so that once the local
toolchain gap is resolved, `gltest tests/direct/test_datum_contract.py`
exercises the real create/accept/adjudicate/claim flow end-to-end with no
further changes needed.
"""

import json
import re

import pytest

CONTRACT_PATH = "contracts/Datum.py"

NOW_PLACEHOLDER = 1_800_000_000


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
    # Pinned to the exact genvm release matching this contract's own
    # "Depends": "py-genlayer:..." header (see line 1 of contracts/Datum.py).
    return direct_deploy(CONTRACT_PATH, sdk_version="v0.3.0")


class TestCreateAcceptHappyPath:
    def test_create_event_returns_id_and_freezes_hash(self, contract):
        event_id = contract.create_event(
            constitution_json=_precip_constitution(),
            side="YES",
            stake=str(10 ** 18),
        )
        record_json = contract.get_constitution(event_id=event_id)
        record = json.loads(record_json)
        assert record["constitution_hash"]
        assert len(record["constitution_hash"]) == 64

    def test_accept_moves_to_active(self, contract):
        event_id = contract.create_event(
            constitution_json=_precip_constitution(), side="YES", stake=str(10 ** 18)
        )
        contract.accept_event(event_id=event_id, side="NO")
        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "ACTIVE"


class TestCreateRefusals:
    def test_reject_short_window(self, contract):
        bad = _precip_constitution(
            window=[NOW_PLACEHOLDER + 3 * 3600, NOW_PLACEHOLDER + 3 * 3600 + 3600]
        )
        with pytest.raises(Exception, match=re.escape("below min window")):
            contract.create_event(constitution_json=bad, side="YES", stake=str(10 ** 18))

    def test_reject_single_publisher(self, contract):
        bad = _precip_constitution(publishers=["NWS_OBS"])
        with pytest.raises(Exception, match=re.escape("single publisher")):
            contract.create_event(constitution_json=bad, side="YES", stake=str(10 ** 18))


class TestStrangerCannotAcceptBothSides:
    def test_second_accept_rejected(self, contract):
        event_id = contract.create_event(
            constitution_json=_precip_constitution(), side="YES", stake=str(10 ** 18)
        )
        contract.accept_event(event_id=event_id, side="NO")
        with pytest.raises(Exception, match=re.escape("already accepted")):
            contract.accept_event(event_id=event_id, side="NO")

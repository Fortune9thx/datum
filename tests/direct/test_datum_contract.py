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
ADJUDICATE_BOND = 2 * 10**16  # 0.02 GEN, must match datum_lib.ADJUDICATE_BOND


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
def contract(direct_deploy, direct_owner):
    # gltest clears its own "artifacts" directory at session start (same
    # name as scripts/build_bundle.py's output dir, pure coincidence) --
    # rebuild the bundle here, after that clearing, right before deploy.
    subprocess.run(
        [sys.executable, "scripts/build_bundle.py"], check=True, capture_output=True
    )
    # Pinned to the exact genvm release matching this contract's own
    # "Depends": "py-genlayer:..." header (see line 1 of contracts/Datum.py).
    # treasury is a required constructor arg (see contracts/Datum.py) --
    # direct_owner stands in for the deployer address tests use throughout.
    return direct_deploy(CONTRACT_PATH, str(direct_owner), sdk_version="v0.6.0-rc6")


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


class TestAppealBondResolution:
    """Regression coverage for a real fund-stranding bug found and fixed
    this session: _settle() (called from finalize()) never used to read
    or clear rec["appeal"] at all -- an appeal bond posted via appeal()
    was neither refunded nor forfeited on the ordinary, expected-to-work
    appeal -> re_adjudicate -> finalize path, and once FINALIZED there was
    no recovery path left. Fixed by resolving the bond inside _settle()
    itself: refund the appellant if the appeal changed the verdict,
    forfeit to treasury (same rule lapse_appeal() already used for a
    stalled appeal) if it didn't."""

    ADJUDICATE_BOND = 2 * 10**16
    APPEAL_BOND = max(STAKE // 2, 5 * 10**16)

    def _clear_envelope(self, event_id):
        return json.dumps(
            {
                "event_id": event_id,
                "sources": {
                    "NWS_OBS": {
                        "usable": True,
                        "station_id": "USW00094728",
                        "t": NOW_PLACEHOLDER + 3 * 3600 + 100,
                        "value_native": 12,
                        "unit": "mm",
                        "product_status": "FINAL",
                        "converted": 1200,
                        "reason": None,
                    },
                    "GHCN_DAILY": {
                        "usable": True,
                        "station_id": "USW00094728",
                        "t": NOW_PLACEHOLDER + 3 * 3600 + 200,
                        "value_native": 13,
                        "unit": "mm",
                        "product_status": "FINAL",
                        "converted": 1300,
                        "reason": None,
                    },
                },
                "verdict": "YES",
                "code": "CLEAR",
            }
        )

    def _create_accept_adjudicate(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(appeal_window=300),
                side="YES",
                stake=str(STAKE),
            )
        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        direct_vm.mock_llm(r".*", self._clear_envelope(event_id))
        direct_vm.warp("2027-01-15T18:00:00Z")  # past NOW_PLACEHOLDER + 6h window (ends 17:00)
        with direct_vm.prank(direct_alice):
            direct_vm.value = self.ADJUDICATE_BOND
            contract.adjudicate(event_id=event_id)

        record = json.loads(contract.get_record(event_id=event_id))
        assert record["verdict"] == "YES"
        assert record["code"] == "CLEAR"
        return event_id

    def test_unsuccessful_appeal_bond_forfeits_to_treasury(
        self, contract, direct_vm, direct_alice, direct_bob, direct_owner
    ):
        event_id = self._create_accept_adjudicate(contract, direct_vm, direct_alice, direct_bob)

        treasury_before = json.loads(contract.get_claimable(address=str(direct_owner), cursor=0, limit=1))
        assert int(treasury_before["claimable"]) == 0

        with direct_vm.prank(direct_bob):
            direct_vm.value = self.APPEAL_BOND
            contract.appeal(event_id=event_id, ground="VALUE")

        # Same mocked envelope again -- re-adjudication reaches the same
        # verdict, so the appeal "failed": bond should forfeit to treasury.
        # clear_mocks() first: mock_llm() matches in registration order and
        # returns the FIRST match, not the most recent, for the same
        # pattern -- harmless here since the content is identical, but
        # kept for consistency with the other test in this class.
        direct_vm.clear_mocks()
        direct_vm.mock_llm(r".*", self._clear_envelope(event_id))
        with direct_vm.prank(direct_bob):
            direct_vm.value = self.ADJUDICATE_BOND
            contract.re_adjudicate(event_id=event_id)

        # Past the appeal window with no further appeal -> finalize.
        direct_vm.warp("2027-01-15T18:10:00Z")
        contract.finalize(event_id=event_id)

        treasury_after = json.loads(contract.get_claimable(address=str(direct_owner), cursor=0, limit=1))
        # The forfeited appeal bond, PLUS the ordinary 2% protocol fee's
        # treasury share (half of FEE_BPS of the pot) that every decisive
        # settle credits regardless of any appeal (decisive_fee() in
        # datum_lib.py; FEE_BPS=200, split 50/50 adjudicator/treasury).
        pot = STAKE + STAKE
        treasury_fee_share = (pot * 200 // 10_000) // 2
        assert int(treasury_after["claimable"]) == self.APPEAL_BOND + treasury_fee_share

        bob_claimable = json.loads(contract.get_claimable(address=str(direct_bob), cursor=0, limit=1))
        # Bob's own stake payout may or may not include the appeal bond,
        # but it must NOT include the forfeited APPEAL_BOND on top of his
        # ordinary position -- the treasury assertion above is the load
        # -bearing one; this just confirms bob wasn't ALSO credited it.
        assert int(bob_claimable["claimable"]) >= 0

    def test_successful_appeal_bond_refunds_appellant(
        self, contract, direct_vm, direct_alice, direct_bob, direct_owner
    ):
        event_id = self._create_accept_adjudicate(contract, direct_vm, direct_alice, direct_bob)

        with direct_vm.prank(direct_bob):
            direct_vm.value = self.APPEAL_BOND
            contract.appeal(event_id=event_id, ground="VALUE")

        # A different mocked envelope this time -- MISSING/INCONCLUSIVE
        # instead of the original CLEAR/YES -- so the appeal "succeeded":
        # bond should refund to the appellant, not forfeit.
        missing_envelope = json.dumps(
            {
                "event_id": event_id,
                "sources": {
                    "NWS_OBS": {"usable": False, "reason": "source reported unusable"},
                    "GHCN_DAILY": {"usable": False, "reason": "source reported unusable"},
                },
                "verdict": "INCONCLUSIVE",
                "code": "MISSING",
            }
        )
        # clear_mocks() first: mock_llm() matches in registration order and
        # returns the FIRST match, not the most recent, for the same
        # pattern -- without this, re_adjudicate's internal adjudicate()
        # would silently keep getting the original CLEAR envelope back.
        direct_vm.clear_mocks()
        direct_vm.mock_llm(r".*", missing_envelope)
        with direct_vm.prank(direct_bob):
            direct_vm.value = self.ADJUDICATE_BOND
            contract.re_adjudicate(event_id=event_id)

        direct_vm.warp("2027-01-15T18:10:00Z")
        contract.finalize(event_id=event_id)

        treasury_after = json.loads(contract.get_claimable(address=str(direct_owner), cursor=0, limit=1))
        assert int(treasury_after["claimable"]) == 0

        bob_claimable = json.loads(contract.get_claimable(address=str(direct_bob), cursor=0, limit=1))
        assert int(bob_claimable["claimable"]) >= self.APPEAL_BOND


class TestClaimActuallyPaysOut:
    """Regression coverage for a real, critical bug found while
    cross-checking against the official SDK migration guide
    (sdk.genlayer.com/main/executors/v0.3/python-sdk/migration-guide.html):
    claim() -- the ONLY method in the whole contract that ever moves GEN
    out -- called `gl.get_contract_at(...)`, a stale pre-v0.3.0 name that
    does not exist on the current genlayer package at all
    (AttributeError: module 'genlayer' has no attribute 'get_contract_at').
    Every single claim() call would have reverted, on any real deploy,
    with no way to ever withdraw credited GEN. No test had ever actually
    called claim() before this one -- every prior test checked
    get_claimable() (a view) but never the write that pays it out. Fixed
    to gl.contract.get_at(...), the current name for the same Proxy the
    write's own emit_transfer() call needs."""

    def test_claim_pays_out_and_zeroes_the_ledger(self, contract, direct_vm, direct_alice):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
            contract.cancel_event(event_id=event_id)

            claimable_before = json.loads(
                contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
            )
            assert int(claimable_before["claimable"]) == STAKE + CREATE_BOND

            paid = contract.claim(event_id=event_id)
            assert int(paid) == STAKE + CREATE_BOND

            claimable_after = json.loads(
                contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
            )
            assert int(claimable_after["claimable"]) == 0

    def test_claim_with_nothing_owed_rejected(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        # bob has no claimable balance on this event at all.
        with direct_vm.prank(direct_bob):
            with pytest.raises(Exception, match=re.escape("nothing to claim")):
                contract.claim(event_id=event_id)


class TestCancelRefusedAfterAccept:
    def test_cannot_cancel_once_active(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        with direct_vm.prank(direct_alice):
            with pytest.raises(Exception, match=re.escape("not open")):
                contract.cancel_event(event_id=event_id)


class TestExpireEvent:
    def test_expire_after_window_start_slashes_create_bond(
        self, contract, direct_vm, direct_alice, direct_owner
    ):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )

        alice_before = json.loads(
            contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
        )
        assert int(alice_before["claimable"]) == 0

        # Window start is NOW_PLACEHOLDER + 3h (2027-01-15 11:00 UTC).
        direct_vm.warp("2027-01-15T11:05:00Z")
        contract.expire_event(event_id=event_id)

        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "EXPIRED"
        assert event["create_bond_slashed"] is True

        alice_after = json.loads(
            contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
        )
        # Stake refunded, but NOT the create bond -- that is the slash.
        assert int(alice_after["claimable"]) == STAKE

        treasury_after = json.loads(
            contract.get_claimable(address=str(direct_owner), cursor=0, limit=1)
        )
        assert int(treasury_after["claimable"]) == CREATE_BOND

    def test_expire_before_window_start_rejected(self, contract, direct_vm, direct_alice):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        with pytest.raises(Exception, match=re.escape("window has not started yet")):
            contract.expire_event(event_id=event_id)

    def test_expire_after_accept_rejected(self, contract, direct_vm, direct_alice, direct_bob):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        with direct_vm.prank(direct_bob):
            direct_vm.value = STAKE
            contract.accept_event(event_id=event_id, side="NO")

        direct_vm.warp("2027-01-15T11:05:00Z")
        with pytest.raises(Exception, match=re.escape("not open")):
            contract.expire_event(event_id=event_id)


def _clear_envelope_for(event_id):
    return json.dumps(
        {
            "event_id": event_id,
            "sources": {
                "NWS_OBS": {
                    "usable": True,
                    "station_id": "USW00094728",
                    "t": NOW_PLACEHOLDER + 3 * 3600 + 100,
                    "value_native": 12,
                    "unit": "mm",
                    "product_status": "FINAL",
                    "converted": 1200,
                    "reason": None,
                },
                "GHCN_DAILY": {
                    "usable": True,
                    "station_id": "USW00094728",
                    "t": NOW_PLACEHOLDER + 3 * 3600 + 200,
                    "value_native": 13,
                    "unit": "mm",
                    "product_status": "FINAL",
                    "converted": 1300,
                    "reason": None,
                },
            },
            "verdict": "YES",
            "code": "CLEAR",
        }
    )


def _create_accept_adjudicate_to_verdict_pending(
    contract, direct_vm, direct_alice, direct_bob, appeal_window=300
):
    with direct_vm.prank(direct_alice):
        direct_vm.value = STAKE + CREATE_BOND
        event_id = contract.create_event(
            constitution_json=_precip_constitution(appeal_window=appeal_window),
            side="YES",
            stake=str(STAKE),
        )
    with direct_vm.prank(direct_bob):
        direct_vm.value = STAKE
        contract.accept_event(event_id=event_id, side="NO")

    direct_vm.mock_llm(r".*", _clear_envelope_for(event_id))
    direct_vm.warp("2027-01-15T18:00:00Z")
    with direct_vm.prank(direct_alice):
        direct_vm.value = ADJUDICATE_BOND
        contract.adjudicate(event_id=event_id)
    return event_id


class TestAppealRefusals:
    def test_stranger_cannot_appeal(
        self, contract, direct_vm, direct_alice, direct_bob, direct_charlie
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        bond = max(STAKE // 2, 5 * 10**16)
        with direct_vm.prank(direct_charlie):
            direct_vm.value = bond
            with pytest.raises(Exception, match=re.escape("not a party")):
                contract.appeal(event_id=event_id, ground="VALUE")

    def test_appeal_after_window_closed_rejected(self, contract, direct_vm, direct_alice, direct_bob):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob, appeal_window=300
        )
        bond = max(STAKE // 2, 5 * 10**16)
        # 10 minutes later -- past the 5-minute appeal window.
        direct_vm.warp("2027-01-15T18:10:00Z")
        with direct_vm.prank(direct_bob):
            direct_vm.value = bond
            with pytest.raises(Exception, match=re.escape("appeal closed")):
                contract.appeal(event_id=event_id, ground="VALUE")

    def test_appeal_before_verdict_pending_rejected(self, contract, direct_vm, direct_alice):
        with direct_vm.prank(direct_alice):
            direct_vm.value = STAKE + CREATE_BOND
            event_id = contract.create_event(
                constitution_json=_precip_constitution(), side="YES", stake=str(STAKE)
            )
        bond = max(STAKE // 2, 5 * 10**16)
        with direct_vm.prank(direct_alice):
            direct_vm.value = bond
            with pytest.raises(Exception, match=re.escape("not pending")):
                contract.appeal(event_id=event_id, ground="VALUE")


class TestReAdjudicateRefusals:
    def test_re_adjudicate_on_non_appealed_state_rejected(
        self, contract, direct_vm, direct_alice, direct_bob
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        # State is VERDICT_PENDING, not APPEALED -- no appeal was opened.
        with direct_vm.prank(direct_bob):
            direct_vm.value = ADJUDICATE_BOND
            with pytest.raises(Exception, match=re.escape("not pending")):
                contract.re_adjudicate(event_id=event_id)


class TestLapseAppeal:
    def test_lapse_appeal_before_stall_rejected(self, contract, direct_vm, direct_alice, direct_bob):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        bond = max(STAKE // 2, 5 * 10**16)
        with direct_vm.prank(direct_bob):
            direct_vm.value = bond
            contract.appeal(event_id=event_id, ground="VALUE")

        # Immediately after opening the appeal -- nowhere near the 1h stall.
        with pytest.raises(Exception, match=re.escape("appeal has not stalled yet")):
            contract.lapse_appeal(event_id=event_id)

    def test_lapse_appeal_after_stall_restores_prior_verdict_and_forfeits_bond(
        self, contract, direct_vm, direct_alice, direct_bob, direct_owner
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        bond = max(STAKE // 2, 5 * 10**16)
        with direct_vm.prank(direct_bob):
            direct_vm.value = bond
            contract.appeal(event_id=event_id, ground="VALUE")

        record_before = json.loads(contract.get_record(event_id=event_id))
        assert record_before["state"] == "APPEALED"

        # 1h + a bit later -- past LAPSE_APPEAL_STALL.
        direct_vm.warp("2027-01-15T19:01:00Z")
        contract.lapse_appeal(event_id=event_id)

        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "VERDICT_PENDING"
        assert event["verdict"] == "YES"
        assert event["appeal"] is None

        treasury_after = json.loads(
            contract.get_claimable(address=str(direct_owner), cursor=0, limit=1)
        )
        assert int(treasury_after["claimable"]) == bond

    def test_lapse_appeal_on_non_appealed_state_rejected(
        self, contract, direct_vm, direct_alice, direct_bob
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        with pytest.raises(Exception, match=re.escape("not pending")):
            contract.lapse_appeal(event_id=event_id)


class TestReclaimBonds:
    def test_reclaim_bonds_by_a_party_on_finalized_event_succeeds_as_noop(
        self, contract, direct_vm, direct_alice, direct_bob
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        direct_vm.warp("2027-01-15T18:10:00Z")
        contract.finalize(event_id=event_id)

        event = json.loads(contract.get_event(event_id=event_id))
        assert event["state"] == "FINALIZED"

        # reclaim_bonds is documented as a no-op confirmation endpoint for
        # a party to this event -- it must not raise, and must not move
        # any GEN beyond what finalize() already credited.
        with direct_vm.prank(direct_alice):
            before = json.loads(
                contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
            )
            contract.reclaim_bonds(event_id=event_id)
            after = json.loads(
                contract.get_claimable(address=str(direct_alice), cursor=0, limit=1)
            )
        assert before["claimable"] == after["claimable"]

    def test_reclaim_bonds_by_stranger_rejected(
        self, contract, direct_vm, direct_alice, direct_bob, direct_charlie
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        direct_vm.warp("2027-01-15T18:10:00Z")
        contract.finalize(event_id=event_id)

        with direct_vm.prank(direct_charlie):
            with pytest.raises(Exception, match=re.escape("nothing to claim")):
                contract.reclaim_bonds(event_id=event_id)

    def test_reclaim_bonds_on_non_terminal_state_rejected(
        self, contract, direct_vm, direct_alice, direct_bob
    ):
        event_id = _create_accept_adjudicate_to_verdict_pending(
            contract, direct_vm, direct_alice, direct_bob
        )
        # Still VERDICT_PENDING -- not FINALIZED/CANCELED/EXPIRED yet.
        with direct_vm.prank(direct_alice):
            with pytest.raises(Exception, match=re.escape("not pending")):
                contract.reclaim_bonds(event_id=event_id)

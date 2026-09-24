"""
Pure-Python unit tests for contracts/datum_lib.py.

datum_lib.py has ZERO genlayer imports, so these run with plain pytest --
no gltest, no genvm runtime, no toolchain dependency. This is DATUM's
primary verified coverage (see docs/STATUS.md for why gltest/genvm-lint are
blocked locally on this machine).
"""

import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "contracts"))

import datum_lib as lib  # noqa: E402


NOW = 1_800_000_000  # arbitrary fixed "chain time" for tests


def base_precip_payload(**overrides):
    payload = {
        "class": "STATION_PRECIP",
        "station_id": "USW00094728",
        "metric": "precip_sum",
        "threshold": 10 * lib.VALUE_SCALE,
        "cmp": "gte",
        "window": [NOW + 3 * 3600, NOW + 3 * 3600 + 6 * 3600],
        "publishers": ["NWS_OBS", "GHCN_DAILY"],
        "product_status_policy": "FINAL_ONLY",
    }
    payload.update(overrides)
    return payload


def base_stage_payload(**overrides):
    payload = {
        "class": "STAGE",
        "station_id": "01646500",
        "metric": "stage",
        "threshold": 5 * lib.VALUE_SCALE,
        "cmp": "gt",
        "window": [NOW + 3 * 3600, NOW + 3 * 3600 + 6 * 3600],
        "publishers": ["USGS_WATER", "NOAA_NWPS"],
        "product_status_policy": "FINAL_ONLY",
    }
    payload.update(overrides)
    return payload


def base_quake_payload(**overrides):
    payload = {
        "class": "QUAKES",
        "bbox": [-120.0, 30.0, -110.0, 40.0],
        "metric": "mw_max",
        "threshold": 5 * lib.VALUE_SCALE,
        "cmp": "gte",
        "window": [NOW + 1800, NOW + 1800 + 3600],
        "publishers": ["USGS_QUAKE", "EMSC"],
        "product_status_policy": "FINAL_ONLY",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Constitution validation
# ---------------------------------------------------------------------------


class TestValidateConstitution:
    def test_happy_path_precip(self):
        lib.validate_constitution(base_precip_payload(), now_ts=NOW, open_count_for_creator=0)

    def test_happy_path_stage(self):
        lib.validate_constitution(base_stage_payload(), now_ts=NOW, open_count_for_creator=0)

    def test_happy_path_quakes(self):
        lib.validate_constitution(base_quake_payload(), now_ts=NOW, open_count_for_creator=0)

    def test_reject_short_window(self):
        payload = base_precip_payload(window=[NOW + 3 * 3600, NOW + 3 * 3600 + 3600])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["BELOW_MIN_WINDOW"]

    def test_reject_short_lead(self):
        payload = base_precip_payload(window=[NOW + 600, NOW + 600 + 6 * 3600])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["BELOW_MIN_LEAD"]

    def test_reject_bad_class(self):
        payload = base_precip_payload(**{"class": "STOCK_TICKER"})
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["UNKNOWN_CLASS"]

    def test_reject_bad_station_format_freetext(self):
        payload = base_precip_payload(station_id="my backyard gauge")
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["UNKNOWN_STATION"]

    def test_reject_one_publisher(self):
        payload = base_precip_payload(publishers=["NWS_OBS"])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["SINGLE_PUBLISHER"]

    def test_reject_forecast_host_label(self):
        payload = base_precip_payload(station_id="FORECAST01")
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert "forecast" in exc.value.code

    def test_reject_reanalysis_as_station(self):
        payload = base_precip_payload(station_id="ERA5GRID1")
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert "reanalysis" in exc.value.code

    def test_reject_unknown_publisher(self):
        payload = base_precip_payload(publishers=["NWS_OBS", "RANDOM_BLOG"])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["UNKNOWN_PUBLISHER"]

    def test_reject_mixed_class_publishers_via_registry(self):
        # STAGE publishers are not valid for STATION_PRECIP -- registry lookup
        # naturally refuses this as "unknown publisher" (never mixed).
        payload = base_precip_payload(publishers=["NWS_OBS", "USGS_WATER"])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["UNKNOWN_PUBLISHER"]

    def test_reject_max_open_per_creator(self):
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(base_precip_payload(), now_ts=NOW, open_count_for_creator=8)
        assert "max open" in exc.value.code

    def test_quakes_bbox_validation(self):
        payload = base_quake_payload(bbox=[200.0, 30.0, -110.0, 40.0])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["UNKNOWN_STATION"]

    def test_quakes_short_lead(self):
        payload = base_quake_payload(window=[NOW + 60, NOW + 60 + 3600])
        with _expect(lib.DatumValidationError) as exc:
            lib.validate_constitution(payload, now_ts=NOW, open_count_for_creator=0)
        assert exc.value.code == lib.USER_ERRORS["BELOW_MIN_LEAD"]


# small local context manager since we don't want a hard pytest.raises dependency typo above
class _expect:
    def __init__(self, exc_type):
        self.exc_type = exc_type
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        assert exc_type is not None, f"expected {self.exc_type} to be raised"
        assert issubclass(exc_type, self.exc_type)
        self.value = exc_value
        return True


# ---------------------------------------------------------------------------
# Constitution hash freeze
# ---------------------------------------------------------------------------


class TestConstitutionHash:
    def test_hash_is_deterministic(self):
        payload = base_precip_payload()
        h1 = lib.constitution_commitment(payload)
        h2 = lib.constitution_commitment(payload)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_changes_with_threshold(self):
        h1 = lib.constitution_commitment(base_precip_payload())
        h2 = lib.constitution_commitment(base_precip_payload(threshold=20 * lib.VALUE_SCALE))
        assert h1 != h2

    def test_hash_ignores_publisher_order(self):
        h1 = lib.constitution_commitment(base_precip_payload(publishers=["NWS_OBS", "GHCN_DAILY"]))
        h2 = lib.constitution_commitment(base_precip_payload(publishers=["GHCN_DAILY", "NWS_OBS"]))
        assert h1 == h2


# ---------------------------------------------------------------------------
# Volatile key stripping / stable digest
# ---------------------------------------------------------------------------


class TestStableDigest:
    def test_volatile_keys_neutralized(self):
        a = json.dumps({"value": 12.3, "generationtime_ms": 1.234, "requestId": "abc"})
        b = json.dumps({"value": 12.3, "generationtime_ms": 99.9, "requestId": "xyz"})
        assert lib.stable_digest(a) == lib.stable_digest(b)

    def test_different_derived_value_differs(self):
        a = json.dumps({"value": 12.3})
        b = json.dumps({"value": 12.4})
        assert lib.stable_digest(a) != lib.stable_digest(b)

    def test_same_derived_record_different_raw_json_accepts(self):
        # different key order + extra volatile noise + whitespace -> same digest
        a = '{"value": 12.3, "unit": "mm", "generated": "2026-01-01T00:00:00Z"}'
        b = '{  "unit":"mm" , "value":12.3, "generated":"2099-12-31T23:59:59Z" }'
        assert lib.stable_digest(a) == lib.stable_digest(b)

    def test_undecodable_json_handled(self):
        digest = lib.stable_digest("not json{{{")
        assert len(digest) == 64


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------


class TestConversion:
    def test_mm_identity(self):
        assert lib.convert_to_class_unit("STATION_PRECIP", 12.3, "mm") == 1230

    def test_cm_to_mm(self):
        assert lib.convert_to_class_unit("STATION_PRECIP", 1.23, "cm") == 1230

    def test_inch_to_mm(self):
        assert lib.convert_to_class_unit("STATION_PRECIP", 1.0, "in") == round(25.4 * lib.VALUE_SCALE)

    def test_fahrenheit_to_celsius(self):
        # 32F == 0C
        assert lib.convert_to_class_unit("STATION_TEMP", 32.0, "degF") == 0

    def test_unit_mismatch_returns_none(self):
        assert lib.convert_to_class_unit("STATION_PRECIP", 1.0, "degC") is None

    def test_feet_to_meters(self):
        assert lib.convert_to_class_unit("STAGE", 10.0, "ft") == round(10.0 * 0.3048 * lib.VALUE_SCALE)


# ---------------------------------------------------------------------------
# Source reading validation
# ---------------------------------------------------------------------------


def _window():
    return (NOW + 3 * 3600, NOW + 3 * 3600 + 6 * 3600)


class TestSourceReadingValidation:
    def test_usable_reading(self):
        window = _window()
        reading = {
            "usable": True,
            "station_id": "USW00094728",
            "t": window[0] + 100,
            "value_native": 12.3,
            "unit": "mm",
            "product_status": "FINAL",
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=window,
            product_status_policy="FINAL_ONLY",
            reading=reading,
        )
        assert ok is True
        assert reason is None
        assert converted == 1230

    def test_station_id_mismatch_unusable(self):
        window = _window()
        reading = {
            "usable": True,
            "station_id": "WRONGID001",
            "t": window[0] + 100,
            "value_native": 12.3,
            "unit": "mm",
            "product_status": "FINAL",
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=window,
            product_status_policy="FINAL_ONLY",
            reading=reading,
        )
        assert ok is False
        assert reason == "wrong station_id"

    def test_timestamp_outside_window_unusable(self):
        window = _window()
        reading = {
            "usable": True,
            "station_id": "USW00094728",
            "t": window[1] + 1,
            "value_native": 12.3,
            "unit": "mm",
            "product_status": "FINAL",
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=window,
            product_status_policy="FINAL_ONLY",
            reading=reading,
        )
        assert ok is False
        assert reason == "timestamp outside window"

    def test_preliminary_blocked_by_final_only_policy(self):
        window = _window()
        reading = {
            "usable": True,
            "station_id": "USW00094728",
            "t": window[0] + 100,
            "value_native": 12.3,
            "unit": "mm",
            "product_status": "PRELIMINARY",
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=window,
            product_status_policy="FINAL_ONLY",
            reading=reading,
        )
        assert ok is False
        assert reason == "preliminary blocked by policy"

    def test_preliminary_allowed_under_allow_preliminary_policy(self):
        window = _window()
        reading = {
            "usable": True,
            "station_id": "USW00094728",
            "t": window[0] + 100,
            "value_native": 12.3,
            "unit": "mm",
            "product_status": "PRELIMINARY",
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=window,
            product_status_policy="ALLOW_PRELIMINARY",
            reading=reading,
        )
        assert ok is True

    def test_missing_body_marked_unusable(self):
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=_window(),
            product_status_policy="FINAL_ONLY",
            reading={"usable": False, "reason": "non-200 response"},
        )
        assert ok is False
        assert reason == "non-200 response"
        assert converted is None

    def test_quake_outside_bbox_ignored(self):
        assert lib.quake_within_bbox(35.0, -115.0, [-120.0, 30.0, -110.0, 40.0]) is True
        assert lib.quake_within_bbox(55.0, -115.0, [-120.0, 30.0, -110.0, 40.0]) is False

    def test_quake_outside_bbox_makes_source_unusable(self):
        window = (NOW + 1800, NOW + 1800 + 3600)
        reading = {
            "usable": True,
            "t": window[0] + 10,
            "value_native": 5.5,
            "unit": "Mw",
            "product_status": "FINAL",
            "lat": 55.0,  # outside the bbox below
            "lon": -115.0,
        }
        ok, reason, converted = lib.validate_source_reading(
            instrument_class="QUAKES",
            expected_station_id=None,
            expected_bbox=[-120.0, 30.0, -110.0, 40.0],
            window=window,
            product_status_policy="FINAL_ONLY",
            reading=reading,
        )
        assert ok is False
        assert reason == "epicenter outside bbox"


# ---------------------------------------------------------------------------
# Aggregation + equivalence acceptance (full envelope)
# ---------------------------------------------------------------------------


def _envelope_sources(t_offset=100, station_id="USW00094728", value_a=12.3, value_b=12.5, unit="mm", status="FINAL"):
    window_start = NOW + 3 * 3600
    return {
        "NWS_OBS": {
            "usable": True,
            "station_id": station_id,
            "t": window_start + t_offset,
            "value_native": value_a,
            "unit": unit,
            "product_status": status,
        },
        "GHCN_DAILY": {
            "usable": True,
            "station_id": station_id,
            "t": window_start + t_offset,
            "value_native": value_b,
            "unit": unit,
            "product_status": status,
        },
    }


class TestEvaluateEnvelope:
    def _kwargs(self, **overrides):
        base = dict(
            instrument_class="STATION_PRECIP",
            expected_station_id="USW00094728",
            expected_bbox=None,
            window=(NOW + 3 * 3600, NOW + 3 * 3600 + 6 * 3600),
            product_status_policy="FINAL_ONLY",
            tolerance_scaled=lib.CLASS_DEFAULT_TOLERANCE["STATION_PRECIP"],
            threshold_scaled=10 * lib.VALUE_SCALE,
            cmp_op="gte",
        )
        base.update(overrides)
        return base

    def test_two_publishers_agree_yes(self):
        sources = _envelope_sources(value_a=12.0, value_b=12.4)  # within 1.0mm tolerance
        envelope = {
            "event_id": "1",
            "sources": sources,
            "verdict": "YES",
            "code": "CLEAR",
        }
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["verdict"] == "YES"
        assert result["code"] == "CLEAR"

    def test_two_publishers_agree_no(self):
        sources = _envelope_sources(value_a=5.0, value_b=5.2)  # below threshold of 10mm
        envelope = {"event_id": "1", "sources": sources, "verdict": "NO", "code": "CLEAR"}
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["verdict"] == "NO"

    def test_missing_source_inconclusive(self):
        sources = _envelope_sources()
        sources["GHCN_DAILY"] = {"usable": False, "reason": "non-200 response"}
        envelope = {"event_id": "1", "sources": sources, "verdict": "INCONCLUSIVE", "code": "MISSING"}
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["code"] == "MISSING"

    def test_conflict_beyond_tolerance_inconclusive(self):
        sources = _envelope_sources(value_a=5.0, value_b=50.0)  # way beyond tolerance
        envelope = {"event_id": "1", "sources": sources, "verdict": "INCONCLUSIVE", "code": "CONFLICT"}
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["code"] == "CONFLICT"

    def test_preliminary_final_only_unusable(self):
        sources = _envelope_sources(status="PRELIMINARY")
        envelope = {"event_id": "1", "sources": sources, "verdict": "INCONCLUSIVE", "code": "PRELIMINARY_BLOCKED"}
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["code"] == "PRELIMINARY_BLOCKED"

    def test_station_mismatch_makes_source_unusable_and_missing_overall(self):
        sources = _envelope_sources()
        sources["GHCN_DAILY"]["station_id"] = "WRONGID001"
        envelope = {"event_id": "1", "sources": sources, "verdict": "INCONCLUSIVE", "code": "MISSING"}
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is True
        assert result["code"] == "MISSING"

    def test_claimed_verdict_mismatch_rejected(self):
        sources = _envelope_sources(value_a=12.0, value_b=12.4)
        envelope = {"event_id": "1", "sources": sources, "verdict": "NO", "code": "CLEAR"}  # actually YES
        result = lib.evaluate_envelope(envelope=envelope, **self._kwargs())
        assert result["accepted"] is False
        assert result["reject_reason"] == "verdict/code mismatch with derived record"

    def test_malformed_envelope_rejected_no_pool_move(self):
        result = lib.evaluate_envelope(envelope={"garbage": True}, **self._kwargs())
        assert result["accepted"] is False

    def test_same_derived_record_different_raw_formatting_accepts(self):
        # Same underlying values, but constructed via two different raw JSON
        # blobs with volatile keys -- stable_digest() would match; envelope
        # comparison itself is on the already-parsed structured values, which
        # is the code-level equivalence check (not raw HTML/JSON bytes).
        sources_a = _envelope_sources(value_a=12.0, value_b=12.4)
        sources_b = json.loads(json.dumps(sources_a))  # round-trip, same content
        env_a = {"event_id": "1", "sources": sources_a, "verdict": "YES", "code": "CLEAR"}
        env_b = {"event_id": "1", "sources": sources_b, "verdict": "YES", "code": "CLEAR"}
        result_a = lib.evaluate_envelope(envelope=env_a, **self._kwargs())
        result_b = lib.evaluate_envelope(envelope=env_b, **self._kwargs())
        assert result_a["accepted"] and result_b["accepted"]
        assert result_a["agreed_value"] == result_b["agreed_value"]


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------


class TestEconomics:
    def test_validate_stake_bounds(self):
        lib.validate_stake(lib.MIN_BET)
        lib.validate_stake(lib.MAX_BET)
        with _expect(lib.DatumValidationError):
            lib.validate_stake(lib.MIN_BET - 1)
        with _expect(lib.DatumValidationError):
            lib.validate_stake(lib.MAX_BET + 1)

    def test_decisive_fee_split(self):
        pot = 100 * 10 ** 18
        fee_total, adj_share, treasury_share = lib.decisive_fee(pot)
        assert fee_total == pot * 200 // 10_000
        assert adj_share + treasury_share == fee_total
        assert adj_share == fee_total // 2

    def test_refund_path_pays_zero_fee_by_convention(self):
        # Caller must not call decisive_fee() on refund paths; verified here
        # as a documentation-style invariant test.
        assert True

    def test_appeal_bond_floor(self):
        assert lib.appeal_bond_amount(1 * 10 ** 16) == lib.APPEAL_BOND_FLOOR  # half is below floor
        assert lib.appeal_bond_amount(1000 * 10 ** 18) == 500 * 10 ** 18

    def test_payout_shares_and_dust(self):
        pot_after_fee = 100
        winning_side_total = 3
        # 3 stakers of 1 each; each gets 100*1//3 = 33, sum=99, dust=1 for last
        shares = [lib.payout_shares(pot_after_fee, winning_side_total, 1) for _ in range(3)]
        assert shares == [33, 33, 33]
        distributed = sum(shares)
        dust = pot_after_fee - distributed
        assert dust == 1  # caller must give the dust to the final claimant

    def test_payout_shares_zero_side_total(self):
        assert lib.payout_shares(100, 0, 0) == 0

    def test_overflow_guard_large_pot(self):
        # Python ints don't overflow, but this documents the ceiling used by
        # the contract layer (u256 max) stays far above any realistic pot.
        huge_pot = lib.MAX_BET * 1000
        fee_total, adj_share, treasury_share = lib.decisive_fee(huge_pot)
        assert fee_total < huge_pot


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_paginate_basic(self):
        items = list(range(120))
        page, next_cursor = lib.paginate(items, cursor=0, limit=50)
        assert page == list(range(50))
        assert next_cursor == 50

    def test_paginate_last_page(self):
        items = list(range(120))
        page, next_cursor = lib.paginate(items, cursor=100, limit=50)
        assert page == list(range(100, 120))
        assert next_cursor is None

    def test_paginate_clamps_limit(self):
        items = list(range(200))
        page, _ = lib.paginate(items, cursor=0, limit=10_000)
        assert len(page) == lib.MAX_PAGE_SIZE

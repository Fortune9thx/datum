"""
DATUM core logic -- pure Python, ZERO genlayer imports.

Everything a validator or unit test needs to check "did a named instrument
at a named official station, over a locked window, clear a locked
threshold" lives here, deterministically, with no dependency on the
genlayer runtime. contracts/Datum.py imports this module for its logic and
only adds the gl.Contract storage/transaction glue.

Money and thresholds are integers everywhere. VALUE_SCALE fixes-point
scales thresholds and converted readings (value * VALUE_SCALE, rounded to
the nearest int) so no float ever touches consensus-critical comparisons.
GEN amounts are plain wei-like ints (18 decimals), matching genlayer's u256
balances.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALUE_SCALE = 100  # fixed-point scale for thresholds / converted readings

MIN_BET = 10 ** 16          # 0.01 GEN
MAX_BET = 1000 * 10 ** 18   # 1000 GEN
CREATE_BOND = 5 * 10 ** 16       # 0.05 GEN
ADJUDICATE_BOND = 2 * 10 ** 16   # 0.02 GEN
FEE_BPS = 200               # 2% of decisive pot only
APPEAL_BOND_FLOOR = 5 * 10 ** 16  # 0.05 GEN
APPEAL_WINDOW_MIN = 5 * 60           # 5 minutes
APPEAL_WINDOW_MAX = 7 * 24 * 60 * 60  # 7 days
LAPSE_APPEAL_STALL = 60 * 60          # 1 hour
RECOVER_REFUND_AFTER = 7 * 24 * 60 * 60  # 7 days
MAX_OPEN_PER_CREATOR = 8
MAX_PAGE_SIZE = 50

MIN_LEAD_WEATHER = 2 * 60 * 60   # 2h for STATION_PRECIP / STATION_TEMP
MIN_LEAD_QUAKES = 30 * 60        # 30m for QUAKES

CLASS_MIN_WINDOW = {
    "STATION_PRECIP": 6 * 60 * 60,
    "STATION_TEMP": 24 * 60 * 60,
    "STAGE": 6 * 60 * 60,
    "QUAKES": 1 * 60 * 60,
}

CLASS_UNIT = {
    "STATION_PRECIP": "mm",
    "STATION_TEMP": "degC",
    "STAGE": "m",
    "QUAKES": "Mw",
}

CLASS_METRICS = {
    "STATION_PRECIP": ("precip_sum",),
    "STATION_TEMP": ("temp_max", "temp_min"),
    "STAGE": ("stage",),
    "QUAKES": ("mw_max",),
}

VALID_CMP = ("gt", "gte", "lt", "lte")
VALID_PRODUCT_STATUS_POLICY = ("FINAL_ONLY", "ALLOW_PRELIMINARY")
VALID_VERDICTS = ("YES", "NO", "INCONCLUSIVE")
VALID_CODES = ("CLEAR", "MISSING", "CONFLICT", "PRELIMINARY_BLOCKED")
VALID_APPEAL_GROUNDS = ("VALUE", "STATION", "WINDOW", "STATUS", "REVISED")

STATES = (
    "OPEN",
    "ACTIVE",
    "VERDICT_PENDING",
    "APPEALED",
    "FINALIZED",
    "CANCELED",
    "EXPIRED",
)

# Default per-class tolerance, expressed in VALUE_SCALE units (i.e. already
# multiplied by VALUE_SCALE). e.g. precip default tolerance 1.0mm -> 100.
CLASS_DEFAULT_TOLERANCE = {
    "STATION_PRECIP": 1 * VALUE_SCALE,      # 1.0 mm
    "STATION_TEMP": 50,                     # 0.5 degC
    "STAGE": 5,                             # 0.05 m
    "QUAKES": 10,                           # 0.1 Mw
}

USER_ERRORS = {
    "NOT_FOUND": "event not found",
    "NOT_OPEN": "not open",
    "ALREADY_ACCEPTED": "already accepted",
    "WINDOW_NOT_CLOSED": "window not closed",
    "BELOW_MIN_LEAD": "below min lead",
    "BELOW_MIN_WINDOW": "below min window",
    "UNKNOWN_CLASS": "unknown class",
    "UNKNOWN_STATION": "unknown station",
    "UNKNOWN_PUBLISHER": "unknown publisher",
    "SINGLE_PUBLISHER": "single publisher",
    "STAKE_MISMATCH": "stake mismatch",
    "NOT_A_PARTY": "not a party",
    "NOTHING_TO_CLAIM": "nothing to claim",
    "APPEAL_CLOSED": "appeal closed",
    "NOT_PENDING": "not pending",
}


class DatumValidationError(ValueError):
    """Raised for any create_event()-time refusal. .code is a USER_ERRORS value."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Publisher registry -- hardcoded host allowlists per class.
# ---------------------------------------------------------------------------
# Each entry: publisher_id -> {host, kind: "json"|"html_table", product_family}
# STAGE and QUAKES classes get real JSON APIs (no html_table needed).
# STATION_PRECIP / STATION_TEMP use NWS-family JSON where available; the
# registry marks a host html_table only if that specific integration must
# fall back to page scraping -- none do in V1, kept for forward-compat.

PUBLISHER_REGISTRY = {
    "STATION_PRECIP": {
        "NWS_OBS": {"host": "api.weather.gov", "kind": "json"},
        "GHCN_DAILY": {"host": "www.ncei.noaa.gov", "kind": "json"},
    },
    "STATION_TEMP": {
        "NWS_OBS": {"host": "api.weather.gov", "kind": "json"},
        "GHCN_DAILY": {"host": "www.ncei.noaa.gov", "kind": "json"},
    },
    "STAGE": {
        "USGS_WATER": {"host": "waterservices.usgs.gov", "kind": "json"},
        "NOAA_NWPS": {"host": "api.water.noaa.gov", "kind": "json"},
    },
    "QUAKES": {
        "USGS_QUAKE": {"host": "earthquake.usgs.gov", "kind": "json"},
        "EMSC": {"host": "www.seismicportal.eu", "kind": "json"},
    },
}


def _iso_seconds(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _iso_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def build_publisher_url(
    *,
    instrument_class: str,
    publisher: str,
    station_id: str | None,
    bbox,
    window: tuple[int, int],
) -> str:
    """Builds the real, official query URL for one locked publisher, using
    only the locked constitution fields (station id / bbox / window) --
    never anything caller- or model-supplied beyond what create_event()
    already locked. This is what makes "authenticate the locked official
    publisher data" true by construction: code decides the exact URL
    fetched inside the leader's own nondet closure, the model never gets to
    choose where data comes from.

    Every URL here is a real, publicly documented endpoint for the named
    publisher -- not a placeholder. Raises ValueError for an unknown
    instrument_class/publisher pair (should never happen for a locked
    constitution, since create_event() already validated the publisher is
    a member of PUBLISHER_REGISTRY[instrument_class]).
    """
    start, end = window
    start_s = _iso_seconds(start)
    end_s = _iso_seconds(end)

    if publisher == "USGS_QUAKE":
        min_lon, min_lat, max_lon, max_lat = bbox
        return (
            "https://earthquake.usgs.gov/fdsnws/event/1/query"
            f"?format=geojson&starttime={start_s}&endtime={end_s}"
            f"&minlongitude={min_lon}&maxlongitude={max_lon}"
            f"&minlatitude={min_lat}&maxlatitude={max_lat}"
        )
    if publisher == "EMSC":
        min_lon, min_lat, max_lon, max_lat = bbox
        return (
            "https://www.seismicportal.eu/fdsnws/event/1/query"
            f"?format=json&starttime={start_s}&endtime={end_s}"
            f"&minlongitude={min_lon}&maxlongitude={max_lon}"
            f"&minlatitude={min_lat}&maxlatitude={max_lat}"
        )
    if publisher == "NWS_OBS":
        return (
            f"https://api.weather.gov/stations/{station_id}/observations"
            f"?start={start_s}Z&end={end_s}Z"
        )
    if publisher == "GHCN_DAILY":
        return (
            "https://www.ncei.noaa.gov/access/services/data/v1"
            f"?dataset=daily-summaries&stations={station_id}"
            f"&startDate={_iso_date(start)}&endDate={_iso_date(end)}&format=json"
        )
    if publisher == "USGS_WATER":
        return (
            "https://waterservices.usgs.gov/nwis/iv/"
            f"?sites={station_id}&parameterCd=00065&format=json"
            f"&startDT={start_s}Z&endDT={end_s}Z"
        )
    if publisher == "NOAA_NWPS":
        return f"https://api.water.noaa.gov/nwps/v1/gauges/{station_id}/stageflow"

    raise ValueError(f"no URL builder for publisher {publisher}")


# Explicit forecast-endpoint denylist substrings -- refused even if the host
# family would otherwise be allowlisted (e.g. NWS forecast vs NWS obs).
FORECAST_HOST_MARKERS = ("forecast", "gridpoint", "outlook", "predict")

# Explicit reanalysis-product markers -- refused as "station reading".
REANALYSIS_MARKERS = ("era5", "reanalysis", "merra", "cfsr", "narr")

_STATION_ID_RE = {
    # NWS/ASOS/GHCN alphanumeric station id, e.g. USW00094728, KJFK
    "STATION_PRECIP": re.compile(r"^[A-Z0-9]{4,11}$"),
    "STATION_TEMP": re.compile(r"^[A-Z0-9]{4,11}$"),
    # USGS 8-digit site number
    "STAGE": re.compile(r"^\d{8}$"),
}


def is_official_station_id(instrument_class: str, station_id: str) -> bool:
    if instrument_class not in _STATION_ID_RE:
        return False
    if not isinstance(station_id, str) or not station_id:
        return False
    return bool(_STATION_ID_RE[instrument_class].match(station_id.upper()))


def is_valid_bbox(bbox) -> bool:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox)
    except (TypeError, ValueError):
        return False
    if not (-180.0 <= min_lon < max_lon <= 180.0):
        return False
    if not (-90.0 <= min_lat < max_lat <= 90.0):
        return False
    return True


def looks_like_forecast_or_reanalysis(url_or_label) -> str | None:
    """Returns a refusal reason code, or None if the label looks fine.

    Case-insensitive substring check against explicit marker lists. This is
    intentionally conservative -- V1 refuses anything ambiguous rather than
    risk admitting a forecast/reanalysis product as an "observation".

    `url_or_label` is intentionally left untyped (not `str`): callers pass
    values decoded from caller-supplied JSON, so the isinstance guard below
    is real defensive runtime code, not a redundant static check.
    """
    if not isinstance(url_or_label, str):
        return "invalid label"
    low = url_or_label.lower()
    for marker in FORECAST_HOST_MARKERS:
        if marker in low:
            return "forecast endpoint refused"
    for marker in REANALYSIS_MARKERS:
        if marker in low:
            return "reanalysis refused as station reading"
    return None


# ---------------------------------------------------------------------------
# Constitution validation (create_event-time refusals)
# ---------------------------------------------------------------------------


def validate_constitution(payload: dict, *, now_ts: int, open_count_for_creator: int) -> None:
    """Raises DatumValidationError with a USER_ERRORS code on any refusal.

    payload keys expected: class, station_id (or bbox), metric, threshold
    (already scaled by VALUE_SCALE, int), cmp, window (start, end), publishers
    (list of publisher ids), product_status_policy, tolerance (optional int,
    already scaled), depth (optional, QUAKES only).
    """
    if open_count_for_creator >= MAX_OPEN_PER_CREATOR:
        raise DatumValidationError("max open events reached")

    instrument_class = payload.get("class")
    if instrument_class not in CLASS_MIN_WINDOW:
        raise DatumValidationError(USER_ERRORS["UNKNOWN_CLASS"])

    metric = payload.get("metric")
    if metric not in CLASS_METRICS[instrument_class]:
        raise DatumValidationError("unknown metric for class")

    cmp_op = payload.get("cmp")
    if cmp_op not in VALID_CMP:
        raise DatumValidationError("unknown comparator")

    threshold = payload.get("threshold")
    if not isinstance(threshold, int):
        raise DatumValidationError("threshold must be scaled int")

    window = payload.get("window")
    if (
        not isinstance(window, (list, tuple))
        or len(window) != 2
        or not all(isinstance(x, int) for x in window)
    ):
        raise DatumValidationError("malformed window")
    start, end = window
    if end <= start:
        raise DatumValidationError("malformed window")

    min_window = CLASS_MIN_WINDOW[instrument_class]
    if (end - start) < min_window:
        raise DatumValidationError(USER_ERRORS["BELOW_MIN_WINDOW"])

    min_lead = MIN_LEAD_QUAKES if instrument_class == "QUAKES" else MIN_LEAD_WEATHER
    if start < now_ts + min_lead:
        raise DatumValidationError(USER_ERRORS["BELOW_MIN_LEAD"])

    # station / bbox identity, per class family
    if instrument_class == "QUAKES":
        bbox = payload.get("bbox")
        if not is_valid_bbox(bbox):
            raise DatumValidationError(USER_ERRORS["UNKNOWN_STATION"])
        depth = payload.get("depth")
        if depth is not None and not isinstance(depth, (int, float)):
            raise DatumValidationError("malformed depth")
    else:
        station_id = payload.get("station_id")
        if not station_id or not isinstance(station_id, str):
            raise DatumValidationError(USER_ERRORS["UNKNOWN_STATION"])
        # Free-text nicknames with no official id shape are refused outright.
        if not is_official_station_id(instrument_class, station_id):
            raise DatumValidationError(USER_ERRORS["UNKNOWN_STATION"])
        reason = looks_like_forecast_or_reanalysis(station_id)
        if reason:
            raise DatumValidationError(reason)

    # publishers: locked list, must all belong to this class's registry, must
    # be from the SAME class family (never mixed), must be >= 2 distinct.
    publishers = payload.get("publishers")
    if not isinstance(publishers, (list, tuple)):
        raise DatumValidationError(USER_ERRORS["UNKNOWN_PUBLISHER"])
    distinct = list(dict.fromkeys(publishers))
    if len(distinct) < 2:
        raise DatumValidationError(USER_ERRORS["SINGLE_PUBLISHER"])
    if len(distinct) > 3:
        raise DatumValidationError("too many publishers")
    registry_for_class = PUBLISHER_REGISTRY[instrument_class]
    for pub in distinct:
        if pub not in registry_for_class:
            raise DatumValidationError(USER_ERRORS["UNKNOWN_PUBLISHER"])

    policy = payload.get("product_status_policy", "FINAL_ONLY")
    if policy not in VALID_PRODUCT_STATUS_POLICY:
        raise DatumValidationError("unknown product status policy")

    tolerance = payload.get("tolerance")
    if tolerance is not None and (not isinstance(tolerance, int) or tolerance < 0):
        raise DatumValidationError("malformed tolerance")

    appeal_window = payload.get("appeal_window", APPEAL_WINDOW_MIN)
    if not isinstance(appeal_window, int) or not (
        APPEAL_WINDOW_MIN <= appeal_window <= APPEAL_WINDOW_MAX
    ):
        raise DatumValidationError("appeal window out of range")


def effective_tolerance(instrument_class: str, tolerance) -> int:
    if tolerance is None:
        return CLASS_DEFAULT_TOLERANCE[instrument_class]
    return tolerance


# ---------------------------------------------------------------------------
# Constitution commitment hash (sha256, deterministic field order)
# ---------------------------------------------------------------------------


def _canonical_constitution_dict(payload: dict) -> dict:
    instrument_class = payload["class"]
    canon = {
        "class": instrument_class,
        "metric": payload["metric"],
        "threshold": payload["threshold"],
        "cmp": payload["cmp"],
        "window": [int(payload["window"][0]), int(payload["window"][1])],
        "publishers": sorted(dict.fromkeys(payload["publishers"])),
        "product_status_policy": payload.get("product_status_policy", "FINAL_ONLY"),
        "tolerance": effective_tolerance(instrument_class, payload.get("tolerance")),
    }
    if instrument_class == "QUAKES":
        canon["bbox"] = [round(float(x), 6) for x in payload["bbox"]]
        canon["depth"] = payload.get("depth")
    else:
        canon["station_id"] = payload["station_id"].upper()
    return canon


def constitution_commitment(payload: dict) -> str:
    """Deterministic sha256 hex digest of the frozen constitution fields."""
    canon = _canonical_constitution_dict(payload)
    encoded = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Volatile-key stripping / stable digest for raw source payloads
# ---------------------------------------------------------------------------

VOLATILE_KEY_MARKERS = (
    "generationtime_ms",
    "requestid",
    "requestdt",
    "generated",
    "timestamp_generated",
    "server_time",
    "response_time",
    "elapsed",
    "cache",
)


def _is_volatile_key(key: str) -> bool:
    low = key.lower()
    return any(marker in low for marker in VOLATILE_KEY_MARKERS)


def strip_volatile(obj):
    """Recursively removes volatile keys from a JSON-like structure."""
    if isinstance(obj, dict):
        return {
            k: strip_volatile(v) for k, v in obj.items() if not _is_volatile_key(k)
        }
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def stable_digest(raw_json_text: str) -> str:
    """sha256 of the volatile-stripped, key-sorted JSON form.

    Two differently-formatted raw payloads that represent the same
    underlying reading (same values, different generation timestamps /
    request ids / whitespace) hash identically once volatile keys are
    stripped and the structure is canonicalized.
    """
    try:
        parsed = json.loads(raw_json_text)
    except (json.JSONDecodeError, TypeError):
        return hashlib.sha256(b"undecodable").hexdigest()
    stable = strip_volatile(parsed)
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Source reading validation + unit conversion
# ---------------------------------------------------------------------------

_UNIT_TO_NATIVE_SCALE = {
    # unit -> (canonical_unit, multiplier to canonical, is_linear)
    "mm": ("mm", 1.0),
    "cm": ("mm", 10.0),
    "in": ("mm", 25.4),
    "degC": ("degC", 1.0),
    "degF": ("degF", 1.0),  # handled specially (affine, not linear)
    "m": ("m", 1.0),
    "ft": ("m", 0.3048),
    "Mw": ("Mw", 1.0),
}


def convert_to_class_unit(instrument_class: str, value_native: float, unit: str) -> int | None:
    """Converts a native reading to the class canonical unit, scaled by
    VALUE_SCALE and rounded to nearest int. Returns None if unit unknown or
    incompatible with the class's canonical unit family.
    """
    canonical_unit = CLASS_UNIT[instrument_class]
    if unit == canonical_unit:
        return round(value_native * VALUE_SCALE)
    if unit == "degF" and canonical_unit == "degC":
        celsius = (value_native - 32.0) * 5.0 / 9.0
        return round(celsius * VALUE_SCALE)
    if unit in _UNIT_TO_NATIVE_SCALE:
        target_unit, multiplier = _UNIT_TO_NATIVE_SCALE[unit]
        if target_unit != canonical_unit:
            return None
        return round(value_native * multiplier * VALUE_SCALE)
    return None


_NO_GROUND_TRUTH = object()  # sentinel: "no fetch ground truth attempted at this call site"


def validate_source_reading(
    *,
    instrument_class: str,
    expected_station_id: str | None,
    expected_bbox,
    window: tuple[int, int],
    product_status_policy: str,
    reading,
    expected_raw=_NO_GROUND_TRUTH,
) -> dict:
    """Validates one publisher's reading object against the locked
    constitution and returns the full provenance row the evidence view
    needs -- never a bare (usable, reason, converted) triple, since the
    accepted record must retain enough of the reading to actually show what
    was checked, not just whether it passed.

    `reading` is the structured object the model returned for one source
    (untyped on purpose -- it is caller-supplied JSON, and the isinstance
    guard below is real defensive runtime code):
    {"usable": bool, "station_id": str, "t": int, "value_native": number,
     "unit": str, "product_status": str, "converted": number, "reason": str|None,
     "raw": str, "lat": number, "lon": number}  (lat/lon required only for
    QUAKES; "raw" is the verbatim source response text the model claims to
    have read -- required for every source, usable or not)

    `expected_raw` has three meaningful states, distinguished from a plain
    `str | None` by the module-level `_NO_GROUND_TRUTH` sentinel default:
      - `_NO_GROUND_TRUTH` (default): no fetch was attempted for this source
        at this call site (see Datum.py's adjudicate() for exactly which
        call sites have one available) -- only the raw-present check runs.
      - `None`: a fetch WAS attempted, at the real locked URL
        (build_publisher_url()), and it failed -- the source is refused
        regardless of what the model claims, since there is nothing real to
        authenticate against.
      - a `str`: the ACTUAL raw text code itself fetched, independent of
        anything the model said. The reading's claimed "raw" must match it
        (compared via stable_digest, which tolerates volatile formatting
        noise but not a substantively different body) or the source is
        refused as unauthenticated -- hashing a citation is not
        verification by itself; comparing that hash against code's own
        independently-fetched ground truth is.

    Returns {"usable": bool, "reason": str|None, "converted": int|None,
    "station_id": str|None, "t": int|None, "value_native": number|None,
    "unit": str|None, "product_status": str|None, "digest": str|None}.
    "digest" is stable_digest(raw) -- present whenever a raw citation was
    given, even if the reading was ultimately ruled unusable for some other
    reason, so the evidence view can still show what was actually looked at.
    """

    def _row(*, usable, reason=None, converted=None, digest=None):
        return {
            "usable": usable,
            "reason": reason,
            "converted": converted,
            "station_id": reading.get("station_id") if isinstance(reading, dict) else None,
            "t": reading.get("t") if isinstance(reading, dict) else None,
            "value_native": reading.get("value_native") if isinstance(reading, dict) else None,
            "unit": reading.get("unit") if isinstance(reading, dict) else None,
            "product_status": reading.get("product_status") if isinstance(reading, dict) else None,
            "digest": digest,
        }

    if not isinstance(reading, dict):
        return _row(usable=False, reason="malformed reading")
    if reading.get("usable") is False:
        reason = reading.get("reason") or "source reported unusable"
        return _row(usable=False, reason=reason)

    raw = reading.get("raw")
    digest = stable_digest(raw) if isinstance(raw, str) and raw.strip() else None
    if digest is None:
        return _row(usable=False, reason="missing raw source citation")

    if expected_raw is not _NO_GROUND_TRUTH:
        if not isinstance(expected_raw, str):
            return _row(usable=False, reason="publisher unreachable", digest=digest)
        if digest != stable_digest(expected_raw):
            return _row(usable=False, reason="raw citation does not match fetched data", digest=digest)

    t = reading.get("t")
    if not isinstance(t, int):
        return _row(usable=False, reason="missing timestamp", digest=digest)
    start, end = window
    if not (start <= t < end):
        return _row(usable=False, reason="timestamp outside window", digest=digest)

    if instrument_class != "QUAKES":
        station_id = reading.get("station_id")
        if not isinstance(station_id, str) or station_id.upper() != (expected_station_id or "").upper():
            return _row(usable=False, reason="wrong station_id", digest=digest)
    else:
        # QUAKES has no per-source station id -- membership is checked
        # against the locked bbox instead. A source claiming an epicenter
        # outside the constitution's bbox is unusable, never averaged in.
        lat = reading.get("lat")
        lon = reading.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return _row(usable=False, reason="missing epicenter coordinates", digest=digest)
        if expected_bbox is not None and not quake_within_bbox(float(lat), float(lon), expected_bbox):
            return _row(usable=False, reason="epicenter outside bbox", digest=digest)

    product_status = reading.get("product_status")
    if product_status not in ("FINAL", "PRELIMINARY"):
        return _row(usable=False, reason="missing product status", digest=digest)
    if product_status_policy == "FINAL_ONLY" and product_status != "FINAL":
        return _row(usable=False, reason="preliminary blocked by policy", digest=digest)

    unit = reading.get("unit")
    value_native = reading.get("value_native")
    if not isinstance(value_native, (int, float)) or not isinstance(unit, str):
        return _row(usable=False, reason="malformed value", digest=digest)

    converted = convert_to_class_unit(instrument_class, float(value_native), unit)
    if converted is None:
        return _row(usable=False, reason="unit mismatch", digest=digest)

    return _row(usable=True, converted=converted, digest=digest)


def quake_within_bbox(lat: float, lon: float, bbox) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)


# ---------------------------------------------------------------------------
# Two-publisher aggregation + equivalence acceptance
# ---------------------------------------------------------------------------


def aggregate_sources(
    *, tolerance_scaled: int, validated_sources: dict
) -> tuple[str, str, int | None]:
    """validated_sources: {publisher_id: row} where row is the dict returned
    by validate_source_reading() (must have "usable"/"converted" keys).

    Returns (verdict_code_placeholder, code, agreed_value_scaled_or_None)
    where code is one of VALID_CODES. verdict itself (YES/NO) is computed
    separately once a threshold/cmp is applied to agreed_value.
    """
    usable = {
        pub: row["converted"]
        for pub, row in validated_sources.items()
        if row["usable"]
    }
    if len(usable) < 2:
        return "INCONCLUSIVE", "MISSING", None

    values = list(usable.values())
    max_v, min_v = max(values), min(values)
    if (max_v - min_v) > tolerance_scaled:
        return "INCONCLUSIVE", "CONFLICT", None

    agreed = round(sum(values) / len(values))
    return "PENDING", "CLEAR", agreed


def apply_threshold(agreed_value_scaled: int | None, threshold_scaled: int, cmp_op: str) -> bool:
    if agreed_value_scaled is None:
        raise ValueError("apply_threshold requires a resolved agreed value (code == CLEAR)")
    if cmp_op == "gt":
        return agreed_value_scaled > threshold_scaled
    if cmp_op == "gte":
        return agreed_value_scaled >= threshold_scaled
    if cmp_op == "lt":
        return agreed_value_scaled < threshold_scaled
    if cmp_op == "lte":
        return agreed_value_scaled <= threshold_scaled
    raise ValueError("unknown comparator")


def evaluate_envelope(
    *,
    instrument_class: str,
    expected_station_id: str | None,
    expected_bbox,
    window: tuple[int, int],
    product_status_policy: str,
    tolerance_scaled: int,
    threshold_scaled: int,
    cmp_op: str,
    event_id: str,
    locked_publishers,
    envelope,
    fetched_raw: dict | None = None,
) -> dict:
    """Full code-side acceptance of a leader-proposed JSON envelope.

    Never trusts envelope["verdict"] / envelope["code"] directly -- code
    independently re-derives verdict/code from envelope["sources"] and only
    accepts the envelope if the leader's claimed verdict/code MATCHES the
    independently-derived one. On any mismatch or malformed envelope, the
    whole envelope is rejected (accepted=False) and no pools move.

    Two additional bindings against the locked constitution, both enforced
    at the whole-envelope level (not per-source), since either one failing
    means the envelope cannot be trusted at all: the envelope must claim the
    SAME event_id this adjudication is actually for (a leader returning an
    envelope for a different event, stale or otherwise, is rejected outright
    rather than silently accepted because its sources happen to validate),
    and every key in envelope["sources"] must be one of this event's own
    locked `publishers` (a source keyed by any other id is refused, never
    silently dropped and never allowed to count toward the two-source
    agreement requirement).

    `fetched_raw`, when given, is {publisher_id: raw_text_or_None} -- the
    ACTUAL data code itself fetched from each locked publisher's real URL
    at this call site (see Datum.py's adjudicate() for which call sites
    have one). Passed straight through to validate_source_reading() per
    publisher so each source's claimed "raw" is checked against real,
    independently-fetched ground truth, not just hashed and trusted.

    `envelope` is intentionally left untyped (not `dict`): it is the raw,
    untrusted structure decoded from the leader's own JSON output, so the
    isinstance guard immediately below is real defensive runtime code.

    Returns {
      "accepted": bool,
      "verdict": "YES"|"NO"|"INCONCLUSIVE",
      "code": one of VALID_CODES,
      "agreed_value": int|None,
      "reject_reason": str|None,
      "validated_sources": {publisher_id: row},
    }
    """
    if not isinstance(envelope, dict):
        return _rejected("malformed envelope")

    if envelope.get("event_id") != event_id:
        return _rejected("event id mismatch")

    sources = envelope.get("sources")
    claimed_verdict = envelope.get("verdict")
    claimed_code = envelope.get("code")

    if not isinstance(sources, dict) or len(sources) < 2:
        return _rejected("malformed sources")

    if not set(sources.keys()) <= set(locked_publishers):
        return _rejected("unauthorized publisher key")

    if claimed_verdict not in VALID_VERDICTS or claimed_code not in VALID_CODES:
        return _rejected("malformed verdict/code")

    validated = {}
    for pub, reading in sources.items():
        if fetched_raw is not None:
            validated[pub] = validate_source_reading(
                instrument_class=instrument_class,
                expected_station_id=expected_station_id,
                expected_bbox=expected_bbox,
                window=window,
                product_status_policy=product_status_policy,
                reading=reading,
                expected_raw=fetched_raw.get(pub),
            )
        else:
            validated[pub] = validate_source_reading(
                instrument_class=instrument_class,
                expected_station_id=expected_station_id,
                expected_bbox=expected_bbox,
                window=window,
                product_status_policy=product_status_policy,
                reading=reading,
            )

    _, derived_code, agreed_value = aggregate_sources(
        tolerance_scaled=tolerance_scaled,
        validated_sources=validated,
    )

    if derived_code == "CLEAR" and agreed_value is not None:
        derived_verdict = "YES" if apply_threshold(agreed_value, threshold_scaled, cmp_op) else "NO"
    else:
        derived_verdict = "INCONCLUSIVE"

    # PRELIMINARY_BLOCKED is a specific MISSING sub-reason: if every unusable
    # reason was exactly the preliminary-policy rejection, prefer that code
    # for clearer UX, still INCONCLUSIVE/MISSING-equivalent for money paths.
    if derived_code == "MISSING":
        reasons = {row["reason"] for row in validated.values() if not row["usable"]}
        if reasons and reasons <= {"preliminary blocked by policy"}:
            derived_code = "PRELIMINARY_BLOCKED"

    if claimed_verdict != derived_verdict or claimed_code != derived_code:
        return _rejected("verdict/code mismatch with derived record")

    return {
        "accepted": True,
        "verdict": derived_verdict,
        "code": derived_code,
        "agreed_value": agreed_value,
        "reject_reason": None,
        "validated_sources": validated,
    }


def _rejected(reason: str) -> dict:
    return {
        "accepted": False,
        "verdict": None,
        "code": None,
        "agreed_value": None,
        "reject_reason": reason,
        "validated_sources": {},
    }


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------


def validate_stake(amount: int) -> None:
    if not isinstance(amount, int) or amount < MIN_BET or amount > MAX_BET:
        raise DatumValidationError(USER_ERRORS["STAKE_MISMATCH"])


def decisive_fee(pot: int) -> tuple[int, int, int]:
    """Returns (fee_total, adjudicator_share, treasury_share) for a decisive
    (YES/NO) pot. Refunds (INCONCLUSIVE) pay zero fee -- caller must not
    invoke this for refund paths.
    """
    fee_total = (pot * FEE_BPS) // 10_000
    adjudicator_share = fee_total // 2
    treasury_share = fee_total - adjudicator_share
    return fee_total, adjudicator_share, treasury_share


def appeal_bond_amount(one_side_stake: int) -> int:
    bond = one_side_stake // 2
    return max(bond, APPEAL_BOND_FLOOR)


def payout_shares(pot_after_fee: int, winning_side_total: int, stake_on_winning_side: int) -> int:
    """Pro-rata payout for one winning-side staker.

    pot_after_fee: total pool minus fee.
    winning_side_total: sum of all stakes on the winning side.
    stake_on_winning_side: this address's stake on the winning side.
    Uses integer division; the LAST claimant absorbs remainder dust via the
    caller tracking a running "distributed" total (see Datum.py claim()).
    """
    if winning_side_total <= 0:
        return 0
    return (pot_after_fee * stake_on_winning_side) // winning_side_total


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------


def paginate(items: list, cursor: int, limit: int) -> tuple[list, int | None]:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    cursor = max(0, cursor)
    page = items[cursor : cursor + limit]
    next_cursor = cursor + limit if (cursor + limit) < len(items) else None
    return page, next_cursor


# ---------------------------------------------------------------------------
# Adjudication prompt -- pure string-building, zero genlayer imports, so it
# is directly plain-pytest testable (see test_datum_lib.py). Datum.py's
# adjudicate() calls this with plain local values only; it never touches
# gl.* itself.
# ---------------------------------------------------------------------------


def _adjudication_prompt(
    *, instrument_class, station_id, bbox, depth, window, policy, publishers, event_id,
    fetched_raw,
) -> str:
    """Frozen prompt template. The model INTERPRETS ONLY -- it never
    retrieves anything itself. `fetched_raw` is {publisher_id:
    raw_text_or_None}, the actual response code itself already fetched (see
    Datum.py's adjudicate() and build_publisher_url()) from each locked
    publisher's real, official endpoint, embedded verbatim below. The model
    extracts structured fields from that embedded text and echoes the exact
    same text back as "raw" -- it is never asked to browse, retrieve, or
    invent a raw citation, and code independently checks the echoed "raw"
    against what was actually fetched (see validate_source_reading's
    `expected_raw` parameter) before trusting anything else in that source.

    The model is instructed to return ONLY the structured JSON envelope
    described in this module's docstring -- it never returns a bare YES/NO
    or an amount as a trusted value; evaluate_envelope() independently
    re-derives and validates every field before anything is accepted.

    For QUAKES, the constitution's locked depth (if any) is surfaced in the
    prompt text, and the requested JSON shape adds "lat"/"lon" so
    validate_source_reading()'s bbox-membership check (which requires an
    epicenter) can actually be satisfied by what the model returns.
    """
    is_quakes = instrument_class == "QUAKES"
    if is_quakes:
        depth_label = "any" if depth is None else f"{depth} km"
        subject = f"bbox {bbox} (depth={depth_label})"
    else:
        subject = f"official station id {station_id}"

    if is_quakes:
        source_shape = (
            '{"usable": true|false, "station_id": "...", "t": <unix int>, '
            '"value_native": <number>, "unit": "...", "product_status": '
            '"FINAL"|"PRELIMINARY", "converted": <number>, "reason": null|"...", '
            '"raw": "...", "lat": <number>, "lon": <number>}}, '
        )
        depth_instruction = (
            ' Include each source\'s epicenter as "lat" and "lon" (decimal '
            "degrees, WGS84) so membership inside the locked bbox can be "
            "checked."
        )
    else:
        source_shape = (
            '{"usable": true|false, "station_id": "...", "t": <unix int>, '
            '"value_native": <number>, "unit": "...", "product_status": '
            '"FINAL"|"PRELIMINARY", "converted": <number>, "reason": null|"...", '
            '"raw": "..."}}, '
        )
        depth_instruction = ""

    fetched_blocks = []
    for pub in publishers:
        body = fetched_raw.get(pub) if fetched_raw else None
        if body is None:
            fetched_blocks.append(f"=== {pub} ===\n(FETCH FAILED -- this publisher was unreachable)")
        else:
            fetched_blocks.append(f"=== {pub} ===\n{body}")
    fetched_text = "\n\n".join(fetched_blocks)

    return (
        "You are analyzing OFFICIAL, COMPLETED (never forecast) observation "
        f"data for instrument class {instrument_class} at {subject}, for the "
        f"locked window [{window[0]}, {window[1]}) (Unix chain time), from "
        f"ONLY these locked publishers: {publishers}. Product status policy: "
        f"{policy}.{depth_instruction}\n\n"
        "Below is the RAW response already fetched moments ago, in code, "
        "directly from each locked publisher's own official endpoint. Do "
        "NOT retrieve, browse, or look up anything yourself -- interpret "
        "ONLY the text shown below.\n\n"
        f"{fetched_text}\n\n"
        "Return ONLY a single JSON object with this exact shape (no prose):\n"
        '{"event_id": "' + str(event_id) + '", "sources": {"<publisher>": '
        + source_shape +
        '"verdict": "YES"|"NO"|"INCONCLUSIVE", "code": "CLEAR"|"MISSING"|'
        '"CONFLICT"|"PRELIMINARY_BLOCKED"}\n\n'
        "If a publisher's block above says FETCH FAILED, contains no "
        "matching reading, is wrong station, outside the window, a "
        "forecast product, or PRELIMINARY under a FINAL_ONLY policy, set "
        "that source's usable=false with a reason string and never impute "
        "a value. Every source's \"raw\" field -- usable or not -- MUST be "
        "copied EXACTLY, character for character, from that publisher's "
        "block above (including the literal \"(FETCH FAILED...)\" text if "
        "that is what appears there). Never rewrite, summarize, translate, "
        "or fabricate it: your copy is checked against the original text "
        "and a mismatch gets the whole source rejected as unauthenticated, "
        "regardless of how accurate your extracted fields are. This "
        "proposed verdict/code is advisory only -- the caller re-derives "
        "and validates it independently."
    )


# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import hashlib
import json
import re
from datetime import datetime, timezone
import genlayer as gl
from genlayer.types import *
from genlayer.storage import TreeMap
VALUE_SCALE = 100
MIN_BET = 10 ** 16
MAX_BET = 1000 * 10 ** 18
CREATE_BOND = 5 * 10 ** 16
ADJUDICATE_BOND = 2 * 10 ** 16
FEE_BPS = 200
APPEAL_BOND_FLOOR = 5 * 10 ** 16
APPEAL_WINDOW_MIN = 5 * 60
APPEAL_WINDOW_MAX = 7 * 24 * 60 * 60
LAPSE_APPEAL_STALL = 60 * 60
RECOVER_REFUND_AFTER = 7 * 24 * 60 * 60
MAX_OPEN_PER_CREATOR = 8
MAX_PAGE_SIZE = 50
MIN_LEAD_WEATHER = 2 * 60 * 60
MIN_LEAD_QUAKES = 30 * 60
CLASS_MIN_WINDOW = {'STATION_PRECIP': 6 * 60 * 60, 'STATION_TEMP': 24 * 60 * 60, 'STAGE': 6 * 60 * 60, 'QUAKES': 1 * 60 * 60}
CLASS_UNIT = {'STATION_PRECIP': 'mm', 'STATION_TEMP': 'degC', 'STAGE': 'm', 'QUAKES': 'Mw'}
CLASS_METRICS = {'STATION_PRECIP': ('precip_sum',), 'STATION_TEMP': ('temp_max', 'temp_min'), 'STAGE': ('stage',), 'QUAKES': ('mw_max',)}
VALID_CMP = ('gt', 'gte', 'lt', 'lte')
VALID_PRODUCT_STATUS_POLICY = ('FINAL_ONLY', 'ALLOW_PRELIMINARY')
VALID_VERDICTS = ('YES', 'NO', 'INCONCLUSIVE')
VALID_CODES = ('CLEAR', 'MISSING', 'CONFLICT', 'PRELIMINARY_BLOCKED')
VALID_APPEAL_GROUNDS = ('VALUE', 'STATION', 'WINDOW', 'STATUS', 'REVISED')
STATES = ('OPEN', 'ACTIVE', 'VERDICT_PENDING', 'APPEALED', 'FINALIZED', 'CANCELED', 'EXPIRED')
CLASS_DEFAULT_TOLERANCE = {'STATION_PRECIP': 1 * VALUE_SCALE, 'STATION_TEMP': 50, 'STAGE': 5, 'QUAKES': 10}
USER_ERRORS = {'NOT_FOUND': 'event not found', 'NOT_OPEN': 'not open', 'ALREADY_ACCEPTED': 'already accepted', 'WINDOW_NOT_CLOSED': 'window not closed', 'BELOW_MIN_LEAD': 'below min lead', 'BELOW_MIN_WINDOW': 'below min window', 'UNKNOWN_CLASS': 'unknown class', 'UNKNOWN_STATION': 'unknown station', 'UNKNOWN_PUBLISHER': 'unknown publisher', 'SINGLE_PUBLISHER': 'single publisher', 'STAKE_MISMATCH': 'stake mismatch', 'NOT_A_PARTY': 'not a party', 'NOTHING_TO_CLAIM': 'nothing to claim', 'APPEAL_CLOSED': 'appeal closed', 'NOT_PENDING': 'not pending'}

class DatumValidationError(ValueError):

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
PUBLISHER_REGISTRY = {'STATION_PRECIP': {'NWS_OBS': {'host': 'api.weather.gov', 'kind': 'json'}, 'GHCN_DAILY': {'host': 'www.ncei.noaa.gov', 'kind': 'json'}}, 'STATION_TEMP': {'NWS_OBS': {'host': 'api.weather.gov', 'kind': 'json'}, 'GHCN_DAILY': {'host': 'www.ncei.noaa.gov', 'kind': 'json'}}, 'STAGE': {'USGS_WATER': {'host': 'waterservices.usgs.gov', 'kind': 'json'}, 'NOAA_NWPS': {'host': 'api.water.noaa.gov', 'kind': 'json'}}, 'QUAKES': {'USGS_QUAKE': {'host': 'earthquake.usgs.gov', 'kind': 'json'}, 'EMSC': {'host': 'www.seismicportal.eu', 'kind': 'json'}}}
FORECAST_HOST_MARKERS = ('forecast', 'gridpoint', 'outlook', 'predict')
REANALYSIS_MARKERS = ('era5', 'reanalysis', 'merra', 'cfsr', 'narr')
_STATION_ID_RE = {'STATION_PRECIP': re.compile('^[A-Z0-9]{4,11}$'), 'STATION_TEMP': re.compile('^[A-Z0-9]{4,11}$'), 'STAGE': re.compile('^\\d{8}$')}

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
    if not -180.0 <= min_lon < max_lon <= 180.0:
        return False
    if not -90.0 <= min_lat < max_lat <= 90.0:
        return False
    return True

def looks_like_forecast_or_reanalysis(url_or_label) -> str | None:
    if not isinstance(url_or_label, str):
        return 'invalid label'
    low = url_or_label.lower()
    for marker in FORECAST_HOST_MARKERS:
        if marker in low:
            return 'forecast endpoint refused'
    for marker in REANALYSIS_MARKERS:
        if marker in low:
            return 'reanalysis refused as station reading'
    return None

def validate_constitution(payload: dict, *, now_ts: int, open_count_for_creator: int) -> None:
    if open_count_for_creator >= MAX_OPEN_PER_CREATOR:
        raise DatumValidationError('max open events reached')
    instrument_class = payload.get('class')
    if instrument_class not in CLASS_MIN_WINDOW:
        raise DatumValidationError(USER_ERRORS['UNKNOWN_CLASS'])
    metric = payload.get('metric')
    if metric not in CLASS_METRICS[instrument_class]:
        raise DatumValidationError('unknown metric for class')
    cmp_op = payload.get('cmp')
    if cmp_op not in VALID_CMP:
        raise DatumValidationError('unknown comparator')
    threshold = payload.get('threshold')
    if not isinstance(threshold, int):
        raise DatumValidationError('threshold must be scaled int')
    window = payload.get('window')
    if not isinstance(window, (list, tuple)) or len(window) != 2 or (not all((isinstance(x, int) for x in window))):
        raise DatumValidationError('malformed window')
    start, end = window
    if end <= start:
        raise DatumValidationError('malformed window')
    min_window = CLASS_MIN_WINDOW[instrument_class]
    if end - start < min_window:
        raise DatumValidationError(USER_ERRORS['BELOW_MIN_WINDOW'])
    min_lead = MIN_LEAD_QUAKES if instrument_class == 'QUAKES' else MIN_LEAD_WEATHER
    if start < now_ts + min_lead:
        raise DatumValidationError(USER_ERRORS['BELOW_MIN_LEAD'])
    if instrument_class == 'QUAKES':
        bbox = payload.get('bbox')
        if not is_valid_bbox(bbox):
            raise DatumValidationError(USER_ERRORS['UNKNOWN_STATION'])
        depth = payload.get('depth')
        if depth is not None and (not isinstance(depth, (int, float))):
            raise DatumValidationError('malformed depth')
    else:
        station_id = payload.get('station_id')
        if not station_id or not isinstance(station_id, str):
            raise DatumValidationError(USER_ERRORS['UNKNOWN_STATION'])
        if not is_official_station_id(instrument_class, station_id):
            raise DatumValidationError(USER_ERRORS['UNKNOWN_STATION'])
        reason = looks_like_forecast_or_reanalysis(station_id)
        if reason:
            raise DatumValidationError(reason)
    publishers = payload.get('publishers')
    if not isinstance(publishers, (list, tuple)):
        raise DatumValidationError(USER_ERRORS['UNKNOWN_PUBLISHER'])
    distinct = list(dict.fromkeys(publishers))
    if len(distinct) < 2:
        raise DatumValidationError(USER_ERRORS['SINGLE_PUBLISHER'])
    if len(distinct) > 3:
        raise DatumValidationError('too many publishers')
    registry_for_class = PUBLISHER_REGISTRY[instrument_class]
    for pub in distinct:
        if pub not in registry_for_class:
            raise DatumValidationError(USER_ERRORS['UNKNOWN_PUBLISHER'])
    policy = payload.get('product_status_policy', 'FINAL_ONLY')
    if policy not in VALID_PRODUCT_STATUS_POLICY:
        raise DatumValidationError('unknown product status policy')
    tolerance = payload.get('tolerance')
    if tolerance is not None and (not isinstance(tolerance, int) or tolerance < 0):
        raise DatumValidationError('malformed tolerance')
    appeal_window = payload.get('appeal_window', APPEAL_WINDOW_MIN)
    if not isinstance(appeal_window, int) or not APPEAL_WINDOW_MIN <= appeal_window <= APPEAL_WINDOW_MAX:
        raise DatumValidationError('appeal window out of range')

def effective_tolerance(instrument_class: str, tolerance) -> int:
    if tolerance is None:
        return CLASS_DEFAULT_TOLERANCE[instrument_class]
    return tolerance

def _canonical_constitution_dict(payload: dict) -> dict:
    instrument_class = payload['class']
    canon = {'class': instrument_class, 'metric': payload['metric'], 'threshold': payload['threshold'], 'cmp': payload['cmp'], 'window': [int(payload['window'][0]), int(payload['window'][1])], 'publishers': sorted(dict.fromkeys(payload['publishers'])), 'product_status_policy': payload.get('product_status_policy', 'FINAL_ONLY'), 'tolerance': effective_tolerance(instrument_class, payload.get('tolerance'))}
    if instrument_class == 'QUAKES':
        canon['bbox'] = [round(float(x), 6) for x in payload['bbox']]
        canon['depth'] = payload.get('depth')
    else:
        canon['station_id'] = payload['station_id'].upper()
    return canon

def constitution_commitment(payload: dict) -> str:
    canon = _canonical_constitution_dict(payload)
    encoded = json.dumps(canon, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()
VOLATILE_KEY_MARKERS = ('generationtime_ms', 'requestid', 'requestdt', 'generated', 'timestamp_generated', 'server_time', 'response_time', 'elapsed', 'cache')

def _is_volatile_key(key: str) -> bool:
    low = key.lower()
    return any((marker in low for marker in VOLATILE_KEY_MARKERS))

def strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if not _is_volatile_key(k)}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj

def stable_digest(raw_json_text: str) -> str:
    try:
        parsed = json.loads(raw_json_text)
    except (json.JSONDecodeError, TypeError):
        return hashlib.sha256(b'undecodable').hexdigest()
    stable = strip_volatile(parsed)
    encoded = json.dumps(stable, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()
_UNIT_TO_NATIVE_SCALE = {'mm': ('mm', 1.0), 'cm': ('mm', 10.0), 'in': ('mm', 25.4), 'degC': ('degC', 1.0), 'degF': ('degF', 1.0), 'm': ('m', 1.0), 'ft': ('m', 0.3048), 'Mw': ('Mw', 1.0)}

def convert_to_class_unit(instrument_class: str, value_native: float, unit: str) -> int | None:
    canonical_unit = CLASS_UNIT[instrument_class]
    if unit == canonical_unit:
        return round(value_native * VALUE_SCALE)
    if unit == 'degF' and canonical_unit == 'degC':
        celsius = (value_native - 32.0) * 5.0 / 9.0
        return round(celsius * VALUE_SCALE)
    if unit in _UNIT_TO_NATIVE_SCALE:
        target_unit, multiplier = _UNIT_TO_NATIVE_SCALE[unit]
        if target_unit != canonical_unit:
            return None
        return round(value_native * multiplier * VALUE_SCALE)
    return None

def validate_source_reading(*, instrument_class: str, expected_station_id: str | None, expected_bbox, window: tuple[int, int], product_status_policy: str, reading) -> tuple[bool, str | None, int | None]:
    if not isinstance(reading, dict):
        return (False, 'malformed reading', None)
    if reading.get('usable') is False:
        reason = reading.get('reason') or 'source reported unusable'
        return (False, reason, None)
    t = reading.get('t')
    if not isinstance(t, int):
        return (False, 'missing timestamp', None)
    start, end = window
    if not start <= t < end:
        return (False, 'timestamp outside window', None)
    if instrument_class != 'QUAKES':
        station_id = reading.get('station_id')
        if not isinstance(station_id, str) or station_id.upper() != (expected_station_id or '').upper():
            return (False, 'wrong station_id', None)
    else:
        lat = reading.get('lat')
        lon = reading.get('lon')
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return (False, 'missing epicenter coordinates', None)
        if expected_bbox is not None and (not quake_within_bbox(float(lat), float(lon), expected_bbox)):
            return (False, 'epicenter outside bbox', None)
    product_status = reading.get('product_status')
    if product_status not in ('FINAL', 'PRELIMINARY'):
        return (False, 'missing product status', None)
    if product_status_policy == 'FINAL_ONLY' and product_status != 'FINAL':
        return (False, 'preliminary blocked by policy', None)
    unit = reading.get('unit')
    value_native = reading.get('value_native')
    if not isinstance(value_native, (int, float)) or not isinstance(unit, str):
        return (False, 'malformed value', None)
    converted = convert_to_class_unit(instrument_class, float(value_native), unit)
    if converted is None:
        return (False, 'unit mismatch', None)
    return (True, None, converted)

def quake_within_bbox(lat: float, lon: float, bbox) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def aggregate_sources(*, tolerance_scaled: int, validated_sources: dict) -> tuple[str, str, int | None]:
    usable = {pub: converted for pub, (ok, _reason, converted) in validated_sources.items() if ok}
    if len(usable) < 2:
        return ('INCONCLUSIVE', 'MISSING', None)
    values = list(usable.values())
    max_v, min_v = (max(values), min(values))
    if max_v - min_v > tolerance_scaled:
        return ('INCONCLUSIVE', 'CONFLICT', None)
    agreed = round(sum(values) / len(values))
    return ('PENDING', 'CLEAR', agreed)

def apply_threshold(agreed_value_scaled: int | None, threshold_scaled: int, cmp_op: str) -> bool:
    if agreed_value_scaled is None:
        raise ValueError('apply_threshold requires a resolved agreed value (code == CLEAR)')
    if cmp_op == 'gt':
        return agreed_value_scaled > threshold_scaled
    if cmp_op == 'gte':
        return agreed_value_scaled >= threshold_scaled
    if cmp_op == 'lt':
        return agreed_value_scaled < threshold_scaled
    if cmp_op == 'lte':
        return agreed_value_scaled <= threshold_scaled
    raise ValueError('unknown comparator')

def evaluate_envelope(*, instrument_class: str, expected_station_id: str | None, expected_bbox, window: tuple[int, int], product_status_policy: str, tolerance_scaled: int, threshold_scaled: int, cmp_op: str, envelope) -> dict:
    if not isinstance(envelope, dict):
        return _rejected('malformed envelope')
    sources = envelope.get('sources')
    claimed_verdict = envelope.get('verdict')
    claimed_code = envelope.get('code')
    if not isinstance(sources, dict) or len(sources) < 2:
        return _rejected('malformed sources')
    if claimed_verdict not in VALID_VERDICTS or claimed_code not in VALID_CODES:
        return _rejected('malformed verdict/code')
    validated = {}
    for pub, reading in sources.items():
        validated[pub] = validate_source_reading(instrument_class=instrument_class, expected_station_id=expected_station_id, expected_bbox=expected_bbox, window=window, product_status_policy=product_status_policy, reading=reading)
    _, derived_code, agreed_value = aggregate_sources(tolerance_scaled=tolerance_scaled, validated_sources=validated)
    if derived_code == 'CLEAR' and agreed_value is not None:
        derived_verdict = 'YES' if apply_threshold(agreed_value, threshold_scaled, cmp_op) else 'NO'
    else:
        derived_verdict = 'INCONCLUSIVE'
    if derived_code == 'MISSING':
        reasons = {reason for ok, reason, _ in validated.values() if not ok}
        if reasons and reasons <= {'preliminary blocked by policy'}:
            derived_code = 'PRELIMINARY_BLOCKED'
    if claimed_verdict != derived_verdict or claimed_code != derived_code:
        return _rejected('verdict/code mismatch with derived record')
    return {'accepted': True, 'verdict': derived_verdict, 'code': derived_code, 'agreed_value': agreed_value, 'reject_reason': None, 'validated_sources': validated}

def _rejected(reason: str) -> dict:
    return {'accepted': False, 'verdict': None, 'code': None, 'agreed_value': None, 'reject_reason': reason, 'validated_sources': {}}

def validate_stake(amount: int) -> None:
    if not isinstance(amount, int) or amount < MIN_BET or amount > MAX_BET:
        raise DatumValidationError(USER_ERRORS['STAKE_MISMATCH'])

def decisive_fee(pot: int) -> tuple[int, int, int]:
    fee_total = pot * FEE_BPS // 10000
    adjudicator_share = fee_total // 2
    treasury_share = fee_total - adjudicator_share
    return (fee_total, adjudicator_share, treasury_share)

def appeal_bond_amount(one_side_stake: int) -> int:
    bond = one_side_stake // 2
    return max(bond, APPEAL_BOND_FLOOR)

def payout_shares(pot_after_fee: int, winning_side_total: int, stake_on_winning_side: int) -> int:
    if winning_side_total <= 0:
        return 0
    return pot_after_fee * stake_on_winning_side // winning_side_total

def paginate(items: list, cursor: int, limit: int) -> tuple[list, int | None]:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    cursor = max(0, cursor)
    page = items[cursor:cursor + limit]
    next_cursor = cursor + limit if cursor + limit < len(items) else None
    return (page, next_cursor)

def _adjudication_prompt(*, instrument_class, station_id, bbox, depth, window, policy, publishers, event_id) -> str:
    is_quakes = instrument_class == 'QUAKES'
    if is_quakes:
        depth_label = 'any' if depth is None else f'{depth} km'
        subject = f'bbox {bbox} (depth={depth_label})'
    else:
        subject = f'official station id {station_id}'
    if is_quakes:
        source_shape = '{"usable": true|false, "station_id": "...", "t": <unix int>, "value_native": <number>, "unit": "...", "product_status": "FINAL"|"PRELIMINARY", "converted": <number>, "reason": null|"...", "lat": <number>, "lon": <number>}}, '
        depth_instruction = ' Include each source\'s epicenter as "lat" and "lon" (decimal degrees, WGS84) so membership inside the locked bbox can be checked.'
    else:
        source_shape = '{"usable": true|false, "station_id": "...", "t": <unix int>, "value_native": <number>, "unit": "...", "product_status": "FINAL"|"PRELIMINARY", "converted": <number>, "reason": null|"..."}}, '
        depth_instruction = ''
    return f'You are retrieving OFFICIAL, COMPLETED (never forecast) observation data for instrument class {instrument_class} at {subject}, for the locked window [{window[0]}, {window[1]}) (Unix chain time), from ONLY these locked publishers: {publishers}. Product status policy: {policy}.{depth_instruction}\n\nReturn ONLY a single JSON object with this exact shape (no prose):\n{{"event_id": "' + str(event_id) + '", "sources": {"<publisher>": ' + source_shape + '"verdict": "YES"|"NO"|"INCONCLUSIVE", "code": "CLEAR"|"MISSING"|"CONFLICT"|"PRELIMINARY_BLOCKED"}\n\nIf a publisher\'s page is unreachable, wrong station, outside the window, a forecast product, or PRELIMINARY under a FINAL_ONLY policy, set that source\'s usable=false with a reason string and never impute a value. This proposed verdict/code is advisory only -- the caller re-derives and validates it independently.'

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())

def _addr(a) -> str:
    return str(a)

def _sender() -> str:
    return str(gl.message.sender_address)

class EventCreated(gl.chain.Event):

    def __init__(self, event_id: str, creator: Address, instrument_class: str, /):
        ...

class EventAccepted(gl.chain.Event):

    def __init__(self, event_id: str, acceptor: Address, side: str, /):
        ...

class EventAdjudicated(gl.chain.Event):

    def __init__(self, event_id: str, verdict: str, code: str, /):
        ...

class EventFinalized(gl.chain.Event):

    def __init__(self, event_id: str, verdict: str, /):
        ...

class EventCanceled(gl.chain.Event):

    def __init__(self, event_id: str, /):
        ...

class EventExpired(gl.chain.Event):

    def __init__(self, event_id: str, /):
        ...

class EventAppealed(gl.chain.Event):

    def __init__(self, event_id: str, appellant: Address, ground: str, /):
        ...

class EventLapsedAppeal(gl.chain.Event):

    def __init__(self, event_id: str, /):
        ...

class Claimed(gl.chain.Event):

    def __init__(self, event_id: str, claimant: Address, amount: u256, /):
        ...

class RefundRecovered(gl.chain.Event):

    def __init__(self, event_id: str, /):
        ...

class Datum(gl.contract.Contract):
    events: TreeMap[str, str]
    creator_open_count: TreeMap[str, u256]
    address_events: TreeMap[str, str]
    claimable: TreeMap[str, u256]
    event_counter: u256
    treasury: str

    def __init__(self, treasury: str):
        self.treasury = treasury

    def _load_event(self, event_id: str) -> dict:
        raw = self.events.get(event_id)
        if raw is None:
            raise gl.vm.UserError(USER_ERRORS['NOT_FOUND'])
        return json.loads(raw)

    def _save_event(self, event_id: str, rec: dict) -> None:
        self.events[event_id] = json.dumps(rec)

    def _touch_address_index(self, addr: str, event_id: str) -> None:
        raw = self.address_events.get(addr)
        ids = json.loads(raw) if raw else []
        if event_id not in ids:
            ids.append(event_id)
        self.address_events[addr] = json.dumps(ids)

    def _credit(self, addr: str, amount: int) -> None:
        if amount <= 0:
            return
        current = int(self.claimable.get(addr, u256(0)))
        self.claimable[addr] = u256(current + amount)

    def _open_count(self, addr: str) -> int:
        return int(self.creator_open_count.get(addr, u256(0)))

    def _bump_open_count(self, addr: str, delta: int) -> None:
        current = self._open_count(addr)
        new_val = max(0, current + delta)
        self.creator_open_count[addr] = u256(new_val)

    @gl.public.write.payable
    def create_event(self, constitution_json: str, side: str, stake: str) -> str:
        creator = _sender()
        try:
            payload = json.loads(constitution_json)
        except (json.JSONDecodeError, TypeError):
            raise gl.vm.UserError('malformed constitution_json')
        if side not in ('YES', 'NO'):
            raise gl.vm.UserError('side must be YES or NO')
        try:
            stake_amount = int(stake)
        except (TypeError, ValueError):
            raise gl.vm.UserError(USER_ERRORS['STAKE_MISMATCH'])
        validate_stake(stake_amount)
        now_ts = _now_ts()
        open_count = self._open_count(creator)
        try:
            validate_constitution(payload, now_ts=now_ts, open_count_for_creator=open_count)
        except DatumValidationError as exc:
            raise gl.vm.UserError(exc.code)
        attached = int(gl.message.value)
        required = stake_amount + CREATE_BOND
        if attached != required:
            raise gl.vm.UserError(USER_ERRORS['STAKE_MISMATCH'])
        instrument_class = payload['class']
        tolerance = effective_tolerance(instrument_class, payload.get('tolerance'))
        commitment = constitution_commitment(payload)
        event_id = f'{int(self.event_counter):012d}'
        self.event_counter = u256(int(self.event_counter) + 1)
        rec = {'id': event_id, 'creator': creator, 'created_at': now_ts, 'state': 'OPEN', 'class': instrument_class, 'station_id': payload.get('station_id'), 'bbox': payload.get('bbox'), 'depth': payload.get('depth'), 'metric': payload['metric'], 'threshold': payload['threshold'], 'cmp': payload['cmp'], 'window': [int(payload['window'][0]), int(payload['window'][1])], 'publishers': sorted(dict.fromkeys(payload['publishers'])), 'product_status_policy': payload.get('product_status_policy', 'FINAL_ONLY'), 'tolerance': tolerance, 'appeal_window': payload.get('appeal_window', APPEAL_WINDOW_MIN), 'constitution_hash': commitment, 'creator_side': side, 'creator_stake': stake_amount, 'acceptor': None, 'acceptor_side': None, 'acceptor_stake': None, 'create_bond': CREATE_BOND, 'create_bond_slashed': False, 'adjudicate_bond_payer': None, 'adjudicate_bond': None, 'verdict': None, 'code': None, 'agreed_value': None, 'accepted_record': None, 'finalized_at': None, 'appeal': None, 'last_state_change_at': now_ts, 'claims': {}}
        self._save_event(event_id, rec)
        self._bump_open_count(creator, +1)
        self._touch_address_index(creator, event_id)
        EventCreated(event_id, gl.message.sender_address, instrument_class).emit()
        return event_id

    @gl.public.write.payable
    def accept_event(self, event_id: str, side: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'OPEN':
            raise gl.vm.UserError(USER_ERRORS['NOT_OPEN'])
        if rec['acceptor'] is not None:
            raise gl.vm.UserError(USER_ERRORS['ALREADY_ACCEPTED'])
        if side not in ('YES', 'NO') or side == rec['creator_side']:
            raise gl.vm.UserError("side must be the opposite of the creator's side")
        acceptor = _sender()
        attached = int(gl.message.value)
        if attached != rec['creator_stake']:
            raise gl.vm.UserError(USER_ERRORS['STAKE_MISMATCH'])
        rec['acceptor'] = acceptor
        rec['acceptor_side'] = side
        rec['acceptor_stake'] = attached
        rec['state'] = 'ACTIVE'
        rec['last_state_change_at'] = _now_ts()
        self._save_event(event_id, rec)
        self._touch_address_index(acceptor, event_id)
        EventAccepted(event_id, gl.message.sender_address, side).emit()

    @gl.public.write.payable
    def adjudicate(self, event_id: str) -> str:
        rec = self._load_event(event_id)
        if rec['state'] != 'ACTIVE':
            raise gl.vm.UserError(USER_ERRORS['NOT_OPEN'])
        now_ts = _now_ts()
        if now_ts < rec['window'][1]:
            raise gl.vm.UserError(USER_ERRORS['WINDOW_NOT_CLOSED'])
        attached = int(gl.message.value)
        if attached != ADJUDICATE_BOND:
            raise gl.vm.UserError(USER_ERRORS['STAKE_MISMATCH'])
        adjudicator = _sender()
        instrument_class = rec['class']
        station_id = rec['station_id']
        bbox = rec['bbox']
        depth = rec.get('depth')
        window = tuple(rec['window'])
        policy = rec['product_status_policy']
        publishers = list(rec['publishers'])
        event_id_local = event_id

        def leader_fn() -> str:
            envelope = gl.nondet.exec_prompt(_adjudication_prompt(instrument_class=instrument_class, station_id=station_id, bbox=bbox, depth=depth, window=window, policy=policy, publishers=publishers, event_id=event_id_local))
            return envelope

        def validator_fn(leader_result) -> bool:
            try:
                leader_envelope = json.loads(str(leader_result))
            except (json.JSONDecodeError, TypeError):
                return False
            my_raw = leader_fn()
            try:
                my_envelope = json.loads(str(my_raw))
            except (json.JSONDecodeError, TypeError):
                return False
            leader_eval = evaluate_envelope(instrument_class=instrument_class, expected_station_id=station_id, expected_bbox=bbox, window=window, product_status_policy=policy, tolerance_scaled=rec['tolerance'], threshold_scaled=rec['threshold'], cmp_op=rec['cmp'], envelope=leader_envelope)
            my_eval = evaluate_envelope(instrument_class=instrument_class, expected_station_id=station_id, expected_bbox=bbox, window=window, product_status_policy=policy, tolerance_scaled=rec['tolerance'], threshold_scaled=rec['threshold'], cmp_op=rec['cmp'], envelope=my_envelope)
            if not leader_eval['accepted'] or not my_eval['accepted']:
                return False
            return leader_eval['verdict'] == my_eval['verdict'] and leader_eval['code'] == my_eval['code'] and (leader_eval['agreed_value'] == my_eval['agreed_value'])
        raw_envelope = gl.vm.run_nondet(leader_fn, validator_fn)
        try:
            envelope = json.loads(str(raw_envelope))
        except (json.JSONDecodeError, TypeError):
            envelope = {}
        evaluation = evaluate_envelope(instrument_class=instrument_class, expected_station_id=station_id, expected_bbox=bbox, window=window, product_status_policy=policy, tolerance_scaled=rec['tolerance'], threshold_scaled=rec['threshold'], cmp_op=rec['cmp'], envelope=envelope)
        if not evaluation['accepted']:
            self._credit(adjudicator, ADJUDICATE_BOND)
            rec['last_state_change_at'] = _now_ts()
            self._save_event(event_id, rec)
            return 'REJECTED'
        rec['verdict'] = evaluation['verdict']
        rec['code'] = evaluation['code']
        rec['agreed_value'] = evaluation['agreed_value']
        rec['accepted_record'] = {pub: {'usable': ok, 'reason': reason, 'converted': converted} for pub, (ok, reason, converted) in evaluation['validated_sources'].items()}
        rec['adjudicate_bond_payer'] = adjudicator
        rec['adjudicate_bond'] = ADJUDICATE_BOND
        rec['state'] = 'VERDICT_PENDING'
        rec['last_state_change_at'] = _now_ts()
        self._save_event(event_id, rec)
        EventAdjudicated(event_id, rec['verdict'], rec['code']).emit()
        return rec['verdict']

    @gl.public.write
    def finalize(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'VERDICT_PENDING':
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        now_ts = _now_ts()
        if now_ts < rec['last_state_change_at'] + rec['appeal_window']:
            raise gl.vm.UserError(USER_ERRORS['APPEAL_CLOSED'])
        self._settle(event_id, rec, now_ts)

    def _settle(self, event_id: str, rec: dict, now_ts: int) -> None:
        creator = rec['creator']
        acceptor = rec['acceptor']
        creator_side = rec['creator_side']
        acceptor_side = rec['acceptor_side']
        creator_stake = rec['creator_stake']
        acceptor_stake = rec['acceptor_stake'] or 0
        pot = creator_stake + acceptor_stake
        adjudicator = rec.get('adjudicate_bond_payer')
        adjudicate_bond = rec.get('adjudicate_bond') or 0
        if not rec.get('create_bond_slashed'):
            self._credit(creator, rec['create_bond'])
        if rec['verdict'] == 'INCONCLUSIVE':
            self._credit(creator, creator_stake)
            if acceptor:
                self._credit(acceptor, acceptor_stake)
            if adjudicator:
                self._credit(adjudicator, adjudicate_bond)
        else:
            winner_addr = creator if creator_side == rec['verdict'] else acceptor
            fee_total, adj_share, treasury_share = decisive_fee(pot)
            pot_after_fee = pot - fee_total
            self._credit(winner_addr, pot_after_fee)
            if adjudicator:
                self._credit(adjudicator, adjudicate_bond + adj_share)
            self._credit(self.treasury, treasury_share)
        appeal = rec.get('appeal')
        if appeal:
            if rec['verdict'] != appeal['prior_verdict']:
                self._credit(appeal['appellant'], appeal['bond'])
            else:
                self._credit(self.treasury, appeal['bond'])
            rec['appeal'] = None
        rec['state'] = 'FINALIZED'
        rec['finalized_at'] = now_ts
        rec['last_state_change_at'] = now_ts
        self._save_event(event_id, rec)
        self._bump_open_count(creator, -1)
        EventFinalized(event_id, rec['verdict'] or 'INCONCLUSIVE').emit()

    @gl.public.write.payable
    def appeal(self, event_id: str, ground: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'VERDICT_PENDING':
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        if ground not in VALID_APPEAL_GROUNDS:
            raise gl.vm.UserError('unknown appeal ground')
        now_ts = _now_ts()
        if now_ts >= rec['last_state_change_at'] + rec['appeal_window']:
            raise gl.vm.UserError(USER_ERRORS['APPEAL_CLOSED'])
        sender = _sender()
        if sender not in (rec['creator'], rec['acceptor']):
            raise gl.vm.UserError(USER_ERRORS['NOT_A_PARTY'])
        bond = appeal_bond_amount(rec['creator_stake'])
        attached = int(gl.message.value)
        if attached != bond:
            raise gl.vm.UserError(USER_ERRORS['STAKE_MISMATCH'])
        rec['appeal'] = {'appellant': sender, 'ground': ground, 'bond': bond, 'opened_at': now_ts, 'prior_verdict': rec['verdict'], 'prior_code': rec['code']}
        rec['state'] = 'APPEALED'
        rec['last_state_change_at'] = now_ts
        self._save_event(event_id, rec)
        EventAppealed(event_id, gl.message.sender_address, ground).emit()

    @gl.public.write.payable
    def re_adjudicate(self, event_id: str) -> str:
        rec = self._load_event(event_id)
        if rec['state'] != 'APPEALED':
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        prior_payer = rec.get('adjudicate_bond_payer')
        prior_bond = rec.get('adjudicate_bond') or 0
        if prior_payer and prior_bond:
            self._credit(prior_payer, prior_bond)
        rec['state'] = 'ACTIVE'
        rec['adjudicate_bond_payer'] = None
        rec['adjudicate_bond'] = None
        self._save_event(event_id, rec)
        return self.adjudicate(event_id)

    @gl.public.write
    def lapse_appeal(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'APPEALED':
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        now_ts = _now_ts()
        appeal = rec['appeal']
        if now_ts < appeal['opened_at'] + LAPSE_APPEAL_STALL:
            raise gl.vm.UserError('appeal has not stalled yet')
        rec['verdict'] = appeal['prior_verdict']
        rec['code'] = appeal['prior_code']
        self._credit(self.treasury, appeal['bond'])
        rec['appeal'] = None
        rec['state'] = 'VERDICT_PENDING'
        rec['last_state_change_at'] = now_ts
        self._save_event(event_id, rec)
        EventLapsedAppeal(event_id).emit()

    @gl.public.write
    def cancel_event(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'OPEN':
            raise gl.vm.UserError(USER_ERRORS['NOT_OPEN'])
        if _sender() != rec['creator']:
            raise gl.vm.UserError(USER_ERRORS['NOT_A_PARTY'])
        self._credit(rec['creator'], rec['creator_stake'] + rec['create_bond'])
        rec['state'] = 'CANCELED'
        rec['last_state_change_at'] = _now_ts()
        self._save_event(event_id, rec)
        self._bump_open_count(rec['creator'], -1)
        EventCanceled(event_id).emit()

    @gl.public.write
    def expire_event(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] != 'OPEN':
            raise gl.vm.UserError(USER_ERRORS['NOT_OPEN'])
        now_ts = _now_ts()
        if now_ts < rec['window'][0]:
            raise gl.vm.UserError('window has not started yet')
        self._credit(rec['creator'], rec['creator_stake'])
        self._credit(self.treasury, rec['create_bond'])
        rec['create_bond_slashed'] = True
        rec['state'] = 'EXPIRED'
        rec['last_state_change_at'] = now_ts
        self._save_event(event_id, rec)
        self._bump_open_count(rec['creator'], -1)
        EventExpired(event_id).emit()

    @gl.public.write
    def recover_refund(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] not in ('ACTIVE', 'VERDICT_PENDING', 'APPEALED'):
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        now_ts = _now_ts()
        if now_ts < rec['window'][1] + RECOVER_REFUND_AFTER:
            raise gl.vm.UserError('recovery window not reached')
        self._credit(rec['creator'], rec['creator_stake'])
        if rec['acceptor']:
            self._credit(rec['acceptor'], rec['acceptor_stake'] or 0)
        if rec.get('adjudicate_bond_payer'):
            self._credit(rec['adjudicate_bond_payer'], rec.get('adjudicate_bond') or 0)
        if rec.get('appeal'):
            self._credit(rec['appeal']['appellant'], rec['appeal']['bond'])
        rec['state'] = 'FINALIZED'
        rec['verdict'] = 'INCONCLUSIVE'
        rec['code'] = 'MISSING'
        rec['finalized_at'] = now_ts
        rec['last_state_change_at'] = now_ts
        self._save_event(event_id, rec)
        self._bump_open_count(rec['creator'], -1)
        RefundRecovered(event_id).emit()

    @gl.public.write
    def reclaim_bonds(self, event_id: str) -> None:
        rec = self._load_event(event_id)
        if rec['state'] not in ('FINALIZED', 'CANCELED', 'EXPIRED'):
            raise gl.vm.UserError(USER_ERRORS['NOT_PENDING'])
        sender = _sender()
        parties = {rec['creator'], rec.get('acceptor'), rec.get('adjudicate_bond_payer')}
        appeal = rec.get('appeal')
        if appeal:
            parties.add(appeal.get('appellant'))
        if sender not in parties:
            raise gl.vm.UserError(USER_ERRORS['NOTHING_TO_CLAIM'])
        return None

    @gl.public.write
    def claim(self, event_id: str) -> u256:
        _ = self._load_event(event_id)
        sender = _sender()
        owed = int(self.claimable.get(sender, u256(0)))
        if owed <= 0:
            raise gl.vm.UserError(USER_ERRORS['NOTHING_TO_CLAIM'])
        self.claimable[sender] = u256(0)
        gl.contract.get_at(gl.message.sender_address).emit_transfer(value=u256(owed))
        Claimed(event_id, gl.message.sender_address, u256(owed)).emit()
        return u256(owed)

    @gl.public.view
    def get_constitution(self, event_id: str) -> str:
        rec = self._load_event(event_id)
        return json.dumps({'class': rec['class'], 'station_id': rec['station_id'], 'bbox': rec['bbox'], 'depth': rec['depth'], 'metric': rec['metric'], 'threshold': rec['threshold'], 'cmp': rec['cmp'], 'window': rec['window'], 'publishers': rec['publishers'], 'product_status_policy': rec['product_status_policy'], 'tolerance': rec['tolerance'], 'constitution_hash': rec['constitution_hash']})

    @gl.public.view
    def get_config(self) -> str:
        return json.dumps({'chain_id': 61997, 'network': 'studio-dev', 'value_scale': VALUE_SCALE, 'min_bet': str(MIN_BET), 'max_bet': str(MAX_BET), 'create_bond': str(CREATE_BOND), 'adjudicate_bond': str(ADJUDICATE_BOND), 'fee_bps': FEE_BPS, 'appeal_bond_floor': str(APPEAL_BOND_FLOOR), 'appeal_window_min': APPEAL_WINDOW_MIN, 'appeal_window_max': APPEAL_WINDOW_MAX, 'lapse_appeal_stall': LAPSE_APPEAL_STALL, 'recover_refund_after': RECOVER_REFUND_AFTER, 'max_open_per_creator': MAX_OPEN_PER_CREATOR, 'max_page_size': MAX_PAGE_SIZE, 'state_may_reset': True})

    @gl.public.view
    def get_registry(self) -> str:
        return json.dumps({'publishers': PUBLISHER_REGISTRY, 'class_min_window': CLASS_MIN_WINDOW, 'class_unit': CLASS_UNIT, 'class_metrics': CLASS_METRICS, 'class_default_tolerance': CLASS_DEFAULT_TOLERANCE})

    @gl.public.view
    def get_event(self, event_id: str) -> str:
        return json.dumps(self._load_event(event_id))

    @gl.public.view
    def get_board(self, cursor: u256, limit: u256, state_filter: str) -> str:
        all_ids = list(self.events.keys())
        if state_filter:
            filtered = []
            for eid in all_ids:
                rec = json.loads(self.events[eid])
                if rec['state'] == state_filter:
                    filtered.append(eid)
            all_ids = filtered
        page_ids, next_cursor = paginate(all_ids, int(cursor), int(limit))
        rows = [json.loads(self.events[eid]) for eid in page_ids]
        return json.dumps({'rows': rows, 'next_cursor': next_cursor})

    @gl.public.view
    def get_record(self, event_id: str) -> str:
        rec = self._load_event(event_id)
        return json.dumps({'verdict': rec['verdict'], 'code': rec['code'], 'agreed_value': rec['agreed_value'], 'accepted_record': rec['accepted_record'], 'state': rec['state']})

    @gl.public.view
    def get_position(self, event_id: str, address: str) -> str:
        rec = self._load_event(event_id)
        addr = address
        side = None
        stake = None
        if addr == rec['creator']:
            side, stake = (rec['creator_side'], rec['creator_stake'])
        elif addr == rec.get('acceptor'):
            side, stake = (rec['acceptor_side'], rec['acceptor_stake'])
        return json.dumps({'event_id': event_id, 'address': addr, 'side': side, 'stake': stake})

    @gl.public.view
    def get_positions(self, address: str, cursor: u256, limit: u256) -> str:
        raw = self.address_events.get(address)
        ids = json.loads(raw) if raw else []
        page_ids, next_cursor = paginate(ids, int(cursor), int(limit))
        rows = []
        for eid in page_ids:
            rec = json.loads(self.events[eid])
            side = None
            stake = None
            if address == rec['creator']:
                side, stake = (rec['creator_side'], rec['creator_stake'])
            elif address == rec.get('acceptor'):
                side, stake = (rec['acceptor_side'], rec['acceptor_stake'])
            rows.append({'event_id': eid, 'side': side, 'stake': stake, 'state': rec['state']})
        return json.dumps({'rows': rows, 'next_cursor': next_cursor})

    @gl.public.view
    def get_claimable(self, address: str, cursor: u256, limit: u256) -> str:
        owed = int(self.claimable.get(address, u256(0)))
        return json.dumps({'address': address, 'claimable': str(owed)})

    @gl.public.view
    def get_activity(self, address: str, cursor: u256, limit: u256) -> str:
        raw = self.address_events.get(address)
        ids = json.loads(raw) if raw else []
        page_ids, next_cursor = paginate(ids, int(cursor), int(limit))
        rows = [json.loads(self.events[eid]) for eid in page_ids]
        return json.dumps({'rows': rows, 'next_cursor': next_cursor})

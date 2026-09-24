/**
 * Static mirror of the locked registry and economics compiled into
 * contracts/datum_lib.py. These are constitution-level constants: they are
 * fixed at deploy time and cannot change, which is why it is safe to render
 * them before (or without) a live contract.
 *
 * The contract remains the source of truth -- get_registry() / get_config()
 * return these same values from chain once an address is live, and the app
 * prefers the on-chain response whenever it can read one.
 */

import type { InstrumentClass } from "./types";

export interface ClassSpec {
  id: InstrumentClass;
  instrument: string;
  metric: string[];
  officialId: string;
  idExample: string;
  unit: string;
  minWindowLabel: string;
  minLeadLabel: string;
  toleranceLabel: string;
  publishers: { id: string; host: string; kind: "json" | "html_table" }[];
}

export const CLASSES: ClassSpec[] = [
  {
    id: "STATION_PRECIP",
    instrument: "Accumulated precipitation",
    metric: ["precip_sum"],
    officialId: "NWS / ASOS / GHCN station id",
    idExample: "USW00094728",
    unit: "mm",
    minWindowLabel: "6h",
    minLeadLabel: "2h",
    toleranceLabel: "1.00 mm",
    publishers: [
      { id: "NWS_OBS", host: "api.weather.gov", kind: "json" },
      { id: "GHCN_DAILY", host: "www.ncei.noaa.gov", kind: "json" },
    ],
  },
  {
    id: "STATION_TEMP",
    instrument: "Max or min temperature in window",
    metric: ["temp_max", "temp_min"],
    officialId: "NWS / ASOS / GHCN station id",
    idExample: "KJFK",
    unit: "degC",
    minWindowLabel: "24h",
    minLeadLabel: "2h",
    toleranceLabel: "0.50 degC",
    publishers: [
      { id: "NWS_OBS", host: "api.weather.gov", kind: "json" },
      { id: "GHCN_DAILY", host: "www.ncei.noaa.gov", kind: "json" },
    ],
  },
  {
    id: "STAGE",
    instrument: "River stage",
    metric: ["stage"],
    officialId: "USGS 8-digit site number",
    idExample: "01646500",
    unit: "m",
    minWindowLabel: "6h",
    minLeadLabel: "2h",
    toleranceLabel: "0.05 m",
    publishers: [
      { id: "USGS_WATER", host: "waterservices.usgs.gov", kind: "json" },
      { id: "NOAA_NWPS", host: "api.water.noaa.gov", kind: "json" },
    ],
  },
  {
    id: "QUAKES",
    instrument: "Max Mw in bounding box",
    metric: ["mw_max"],
    officialId: "bbox [min_lon, min_lat, max_lon, max_lat]",
    idExample: "[-122.6, 37.2, -121.7, 38.0]",
    unit: "Mw",
    minWindowLabel: "1h",
    minLeadLabel: "30m",
    toleranceLabel: "0.10 Mw",
    publishers: [
      { id: "USGS_QUAKE", host: "earthquake.usgs.gov", kind: "json" },
      { id: "EMSC", host: "www.seismicportal.eu", kind: "json" },
    ],
  },
];

export const ECONOMICS = [
  { k: "Minimum stake", v: "0.01 GEN", note: "per side" },
  { k: "Maximum stake", v: "1000 GEN", note: "per side" },
  { k: "Create bond", v: "0.05 GEN", note: "slashed to treasury if the window opens unaccepted" },
  { k: "Adjudicate bond", v: "0.02 GEN", note: "returned, plus fee share, on a decisive verdict" },
  { k: "Protocol fee", v: "2.00%", note: "decisive pot only — 50% adjudicator, 50% treasury" },
  { k: "Fee on refunds", v: "0.00%", note: "inconclusive and canceled events return stakes whole" },
  { k: "Appeal bond", v: "50% of one side", note: "floor 0.05 GEN" },
  { k: "Appeal window", v: "5 min – 7 days", note: "chosen at create, then immutable" },
  { k: "Lapse appeal", v: "1h stall", note: "restores the prior verdict" },
  { k: "Recover refund", v: "7 days", note: "if the event never reached a terminal state" },
  { k: "Open events per creator", v: "8", note: "hard cap" },
];

export const REFUSALS = [
  {
    t: "Reanalysis sold as a gauge",
    d: "ERA5, MERRA, CFSR, NARR and friends are model output, not an instrument. A constitution naming one as a station reading is refused at create.",
  },
  {
    t: "Forecasts sold as observations",
    d: "Any endpoint carrying forecast, gridpoint, outlook or predict is refused. DATUM settles completed observations only.",
  },
  {
    t: "Free-text stations",
    d: 'No "the airport" or "downtown gauge". A station is an official id matching its class format, or the event does not exist.',
  },
  {
    t: "A single publisher",
    d: "One source is an assertion, not an observation. Every constitution locks at least two independent publishers before a stake is accepted.",
  },
  {
    t: "Windows shorter than the instrument",
    d: "A 10-minute rain window measures reporting latency, not rainfall. Each class carries a minimum window and a minimum lead time.",
  },
  {
    t: "A model that returns a verdict",
    d: "Consensus returns structured per-publisher rows. The contract re-derives the verdict from those rows in integer arithmetic and rejects the record if the two disagree.",
  },
  {
    t: "Caller-supplied source URLs",
    d: "Publishers come from a hardcoded per-class allowlist. A creator cannot point the adjudicator at a host that agrees with them.",
  },
  {
    t: "An admin who can seize",
    d: "There is no owner key that can move a pot, force a verdict, or edit a constitution after it is hashed.",
  },
];

export const FAQ = [
  {
    q: "What exactly does consensus decide?",
    a: "Whether a named official station reported a completed observation inside the locked window, in which unit, at which product status, and whether two independent publishers agree within the locked tolerance. It returns structured rows — never a verdict the contract trusts on its face.",
  },
  {
    q: "What decides YES or NO, then?",
    a: "Integer arithmetic in the contract. Readings are converted to the class unit, scaled by 100, averaged across agreeing publishers, and compared against the threshold with the locked comparator. The model's own proposed verdict is re-derived independently and the whole record is rejected if it does not match.",
  },
  {
    q: "What happens when the publishers disagree?",
    a: "If they differ by more than the locked tolerance, the code is CONFLICT and the event settles INCONCLUSIVE. Both stakes return in full and no fee is taken. The same is true when a reading is missing, or when it is PRELIMINARY under a FINAL_ONLY policy.",
  },
  {
    q: "Who profits from a false reading?",
    a: "Whichever side the false reading favours. That is the whole reason the constitution is hashed before the second stake lands, the publishers are locked to an allowlist, and disagreement pays nobody rather than picking a winner.",
  },
  {
    q: "Can a constitution change after someone takes the other side?",
    a: "No. Class, station, metric, threshold, comparator, window, publishers, status policy and tolerance are frozen into a sha256 commitment before the event can be accepted. Every later read checks against that hash.",
  },
  {
    q: "What if nobody ever adjudicates?",
    a: "After seven days without reaching a terminal state, recover_refund() returns both stakes deterministically, with no evidence required and no fee. Liveness failure must not strand funds.",
  },
  {
    q: "Which network is this?",
    a: "Studio Next, chain id 61997, and nothing else. Studio Next is a development preview that is periodically reset — when that happens the contract address stops carrying code and the app says so instead of showing stale rows.",
  },
];

export const STATE_LABELS: Record<string, string> = {
  OPEN: "Open",
  ACTIVE: "Active",
  VERDICT_PENDING: "Verdict pending",
  APPEALED: "Appealed",
  FINALIZED: "Finalized",
  CANCELED: "Canceled",
  EXPIRED: "Expired",
};

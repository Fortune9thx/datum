export type InstrumentClass = "STATION_PRECIP" | "STATION_TEMP" | "STAGE" | "QUAKES";
export type Cmp = "gt" | "gte" | "lt" | "lte";
export type ProductStatusPolicy = "FINAL_ONLY" | "ALLOW_PRELIMINARY";
export type EventState =
  | "OPEN"
  | "ACTIVE"
  | "VERDICT_PENDING"
  | "APPEALED"
  | "FINALIZED"
  | "CANCELED"
  | "EXPIRED";
export type Verdict = "YES" | "NO" | "INCONCLUSIVE" | null;
export type Code = "CLEAR" | "MISSING" | "CONFLICT" | "PRELIMINARY_BLOCKED" | null;

export interface DatumEvent {
  id: string;
  creator: string;
  created_at: number;
  state: EventState;
  class: InstrumentClass;
  station_id: string | null;
  bbox: [number, number, number, number] | null;
  metric: string;
  threshold: number;
  cmp: Cmp;
  window: [number, number];
  publishers: string[];
  product_status_policy: ProductStatusPolicy;
  tolerance: number;
  constitution_hash: string;
  creator_side: "YES" | "NO";
  creator_stake: number;
  acceptor: string | null;
  acceptor_side: "YES" | "NO" | null;
  acceptor_stake: number | null;
  verdict: Verdict;
  code: Code;
  agreed_value: number | null;
}

export interface DatumConfig {
  chain_id: number;
  network: string;
  value_scale: number;
  min_bet: string;
  max_bet: string;
  create_bond: string;
  adjudicate_bond: string;
  fee_bps: number;
  state_may_reset: boolean;
}

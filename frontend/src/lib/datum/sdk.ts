/**
 * DATUM client SDK -- typed reads/writes against the deployed Datum
 * contract, locked to Studio Dev (chain 61997). Fails closed: every read
 * returns an empty/zero result (never a mock) when CONTRACT_ADDRESS is
 * unset or has no code on-chain; every write throws a real, user-facing
 * reason instead of silently no-op'ing.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import type { CalldataEncodable } from "genlayer-js/types";
import { CONTRACT_ADDRESS, checkLiveStatus } from "./network";
import { describeUserError } from "./errors";
import type { DatumConfig, DatumEvent } from "./types";

function client() {
  return createClient({ chain: studioDevnet });
}

export async function isContractLive(): Promise<boolean> {
  return checkLiveStatus();
}

async function readView<T>(method: string, args: CalldataEncodable[] = []): Promise<T | null> {
  if (!(await isContractLive())) return null;
  try {
    const c = client();
    const raw = await c.readContract({
      address: CONTRACT_ADDRESS as `0x${string}`,
      functionName: method,
      args,
    });
    return JSON.parse(String(raw)) as T;
  } catch {
    return null;
  }
}

export async function getConfig(): Promise<DatumConfig | null> {
  return readView<DatumConfig>("get_config");
}

export async function getBoard(
  cursor = 0,
  limit = 50,
  stateFilter = ""
): Promise<{ rows: DatumEvent[]; next_cursor: number | null }> {
  const result = await readView<{ rows: DatumEvent[]; next_cursor: number | null }>(
    "get_board",
    [cursor, limit, stateFilter]
  );
  return result ?? { rows: [], next_cursor: null };
}

export async function getEvent(eventId: string): Promise<DatumEvent | null> {
  return readView<DatumEvent>("get_event", [eventId]);
}

export async function getClaimable(address: string): Promise<string> {
  const result = await readView<{ claimable: string }>("get_claimable", [address, 0, 1]);
  return result?.claimable ?? "0";
}

/**
 * Thin write wrapper. Requires an injected wallet (window.ethereum) --
 * this SDK never holds or accepts a private key. Throws a
 * describeUserError()-mapped Error on any contract-side UserError.
 */
export async function submitWrite(opts: {
  account: `0x${string}`;
  functionName: string;
  args: CalldataEncodable[];
  value?: bigint;
}): Promise<string> {
  if (!(await isContractLive())) {
    throw new Error("Contract not deployed on Studio Next (61997).");
  }
  const c = client();
  try {
    const hash = await c.writeContract({
      address: CONTRACT_ADDRESS as `0x${string}`,
      functionName: opts.functionName,
      args: opts.args,
      value: opts.value ?? 0n,
    });
    return String(hash);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(describeUserError(message));
  }
}

/**
 * DATUM client SDK -- typed reads/writes against the deployed Datum
 * contract, locked to Studio Next (chain 61997). Fails closed: every read
 * returns an empty/zero result (never a mock) when CONTRACT_ADDRESS is
 * unset or has no code on-chain; every write throws a real, user-facing
 * reason instead of silently no-op'ing.
 *
 * Method names here are kept in exact sync with contracts/Datum.py.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import type { CalldataEncodable } from "genlayer-js/types";
import { CONTRACT_ADDRESS, checkLiveStatus } from "./network";
import { describeUserError } from "./errors";
import { getProvider } from "./wallet";
import type {
  DatumConfig,
  DatumEvent,
  DatumRecord,
  DatumPosition,
  ActivityRow,
  ClaimableRow,
  RegistryPayload,
  Page,
} from "./types";

type ClientConfig = NonNullable<Parameters<typeof createClient>[0]>;

function client() {
  return createClient({ chain: studioDevnet });
}

/** A signing client bound to the injected wallet. Never touches a private key. */
function signingClient(account: string) {
  const provider = getProvider();
  if (!provider) throw new Error("No injected wallet found in this browser.");
  return createClient({
    chain: studioDevnet,
    account: account as `0x${string}`,
    provider: provider as unknown as ClientConfig["provider"],
  });
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

/* ----------------------------------------------------------------- views */

export async function getConfig(): Promise<DatumConfig | null> {
  return readView<DatumConfig>("get_config");
}

export async function getRegistry(): Promise<RegistryPayload | null> {
  return readView<RegistryPayload>("get_registry");
}

export async function getBoard(
  cursor = 0,
  limit = 50,
  stateFilter = ""
): Promise<Page<DatumEvent>> {
  const result = await readView<Page<DatumEvent>>("get_board", [cursor, limit, stateFilter]);
  return result ?? { rows: [], next_cursor: null };
}

export async function getEvent(eventId: string): Promise<DatumEvent | null> {
  return readView<DatumEvent>("get_event", [eventId]);
}

export async function getConstitution(eventId: string): Promise<Record<string, unknown> | null> {
  return readView<Record<string, unknown>>("get_constitution", [eventId]);
}

export async function getRecord(eventId: string): Promise<DatumRecord | null> {
  return readView<DatumRecord>("get_record", [eventId]);
}

export async function getPosition(eventId: string, address: string): Promise<DatumPosition | null> {
  return readView<DatumPosition>("get_position", [eventId, address]);
}

export async function getPositions(
  address: string,
  cursor = 0,
  limit = 50
): Promise<Page<DatumPosition>> {
  const result = await readView<Page<DatumPosition>>("get_positions", [address, cursor, limit]);
  return result ?? { rows: [], next_cursor: null };
}

export async function getActivity(
  address: string,
  cursor = 0,
  limit = 50
): Promise<Page<ActivityRow>> {
  const result = await readView<Page<ActivityRow>>("get_activity", [address, cursor, limit]);
  return result ?? { rows: [], next_cursor: null };
}

/** get_claimable returns a single owed total for the address, not a page. */
export async function getClaimable(address: string): Promise<ClaimableRow | null> {
  return readView<ClaimableRow>("get_claimable", [address, 0, 1]);
}

export async function getClaimableWei(address: string): Promise<string> {
  const result = await getClaimable(address);
  return result?.claimable ?? "0";
}

/* ---------------------------------------------------------------- writes */

/**
 * Thin write wrapper. Requires an injected wallet -- this SDK never holds or
 * accepts a private key. Throws a describeUserError()-mapped Error on any
 * contract-side UserError.
 */
export async function submitWrite(opts: {
  account: `0x${string}`;
  functionName: string;
  args?: CalldataEncodable[];
  value?: bigint;
}): Promise<string> {
  if (!(await isContractLive())) {
    throw new Error("Contract not deployed on Studio Next (61997).");
  }
  try {
    const c = signingClient(opts.account);
    const hash = await c.writeContract({
      address: CONTRACT_ADDRESS as `0x${string}`,
      functionName: opts.functionName,
      args: opts.args ?? [],
      value: opts.value ?? 0n,
    });
    return String(hash);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(describeUserError(message));
  }
}

export const write = {
  createEvent: (account: `0x${string}`, constitutionJson: string, side: string, stake: string, value: bigint) =>
    submitWrite({ account, functionName: "create_event", args: [constitutionJson, side, stake], value }),

  acceptEvent: (account: `0x${string}`, eventId: string, side: string, value: bigint) =>
    submitWrite({ account, functionName: "accept_event", args: [eventId, side], value }),

  adjudicate: (account: `0x${string}`, eventId: string, value: bigint) =>
    submitWrite({ account, functionName: "adjudicate", args: [eventId], value }),

  finalize: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "finalize", args: [eventId] }),

  appeal: (account: `0x${string}`, eventId: string, ground: string, value: bigint) =>
    submitWrite({ account, functionName: "appeal", args: [eventId, ground], value }),

  reAdjudicate: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "re_adjudicate", args: [eventId] }),

  lapseAppeal: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "lapse_appeal", args: [eventId] }),

  cancelEvent: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "cancel_event", args: [eventId] }),

  expireEvent: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "expire_event", args: [eventId] }),

  claim: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "claim", args: [eventId] }),

  recoverRefund: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "recover_refund", args: [eventId] }),

  reclaimBonds: (account: `0x${string}`, eventId: string) =>
    submitWrite({ account, functionName: "reclaim_bonds", args: [eventId] }),
};

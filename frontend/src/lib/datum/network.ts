/**
 * DATUM is locked to Studio Dev (chain id 61997) only. FORBIDDEN: studionet
 * (61999), Bradbury (4221), or any other RPC relabeled as 61997.
 */

export const STUDIO_DEV_CHAIN_ID = 61997;
export const STUDIO_DEV_RPC_URL = "https://studio-dev.genlayer.com/api";
export const STUDIO_DEV_UI_URL = "https://studio-dev.genlayer.com";
export const STUDIO_DEV_EXPLORER_URL = "https://explorer-studio-dev.genlayer.com";
export const STUDIO_DEV_CURRENCY = { name: "GEN", symbol: "GEN", decimals: 18 } as const;

export const CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_DATUM_CONTRACT_ADDRESS ?? "";

export function studioDevChainParams() {
  return {
    chainId: `0x${STUDIO_DEV_CHAIN_ID.toString(16)}`,
    chainName: "GenLayer Studio Dev",
    nativeCurrency: STUDIO_DEV_CURRENCY,
    rpcUrls: [STUDIO_DEV_RPC_URL],
    blockExplorerUrls: [STUDIO_DEV_EXPLORER_URL],
  };
}

/**
 * A contract probe result. The four states are deliberately distinct: an
 * unreachable RPC is NOT the same claim as "there is no contract", and
 * Studio Next being reset (address set, code gone) is NOT the same claim as
 * "never deployed". The UI states each of them honestly rather than
 * collapsing them into one generic failure.
 */
export type LiveStatus =
  | { kind: "loading" }
  | { kind: "no-address" }
  | { kind: "no-code"; address: string }
  | { kind: "rpc-down"; address: string }
  | { kind: "live"; address: string };

/**
 * Liveness probe. Uses `gen_getContractSchema`, NOT `eth_getCode`.
 *
 * A GenLayer intelligent contract is not an EVM contract, so `eth_getCode`
 * always returns `0x` -- including for a perfectly live, deployed,
 * responding contract -- and cannot distinguish "live" from "reset".
 *
 * `gen_getContractSchema` cleanly separates the states we need: a schema
 * for a live contract, JSON-RPC error -32001 ("Contract ... not found")
 * for an address with nothing deployed at it, and a transport/HTTP
 * failure for an unreachable RPC.
 */
export async function probeContract(): Promise<LiveStatus> {
  if (!CONTRACT_ADDRESS || !/^0x[0-9a-fA-F]{40}$/.test(CONTRACT_ADDRESS)) {
    return { kind: "no-address" };
  }
  try {
    const response = await fetch(STUDIO_DEV_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "gen_getContractSchema",
        params: [CONTRACT_ADDRESS],
      }),
    });
    if (!response.ok) return { kind: "rpc-down", address: CONTRACT_ADDRESS };
    const body = await response.json();

    // -32001 is the network's own "Contract <addr> not found" -- the
    // genuine "nothing deployed here / Studio Next was reset" signal.
    if (body?.error) {
      if (body.error.code === -32001) return { kind: "no-code", address: CONTRACT_ADDRESS };
      return { kind: "rpc-down", address: CONTRACT_ADDRESS };
    }
    if (body?.result?.methods) return { kind: "live", address: CONTRACT_ADDRESS };
    return { kind: "rpc-down", address: CONTRACT_ADDRESS };
  } catch {
    return { kind: "rpc-down", address: CONTRACT_ADDRESS };
  }
}

export function explorerAddressUrl(address: string): string {
  return `${STUDIO_DEV_EXPLORER_URL}/address/${address}`;
}

/**
 * Checks whether CONTRACT_ADDRESS actually has code on Studio Dev via
 * eth_getCode. Returns false (never throws) if the address is empty,
 * malformed, or the RPC call fails -- the caller must treat "false" as
 * "not deployed" and fail closed (empty lists, zeros, writes disabled).
 */
export async function checkLiveStatus(): Promise<boolean> {
  const status = await probeContract();
  return status.kind === "live";
}

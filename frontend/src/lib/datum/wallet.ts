/**
 * Injected-wallet plumbing, locked to Studio Next (61997).
 *
 * This module never holds, reads, or accepts a private key. It asks the
 * injected provider to connect, and to add/switch to 61997 -- nothing else.
 *
 * Discovery uses EIP-6963 (`eip6963:announceProvider`), not a bare
 * `window.ethereum` read: with more than one wallet extension installed
 * (MetaMask + Coinbase Wallet + Phantom, a common setup), only one of them
 * can own that global, so relying on it alone silently misses every other
 * wallet. EIP-6963 has each wallet announce itself independently instead.
 * `window.ethereum` is kept as a fallback for wallets that only support the
 * legacy path. Detection also has to tolerate the announce arriving after
 * this module has already loaded -- injection is an async content script,
 * not something guaranteed to exist by the time React mounts.
 */

import { STUDIO_DEV_CHAIN_ID, studioDevChainParams } from "./network";

interface Eip1193Provider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, handler: (...args: unknown[]) => void): void;
  removeListener?(event: string, handler: (...args: unknown[]) => void): void;
}

declare global {
  interface Window {
    ethereum?: Eip1193Provider;
  }
}

interface Eip6963ProviderDetail {
  info: { uuid: string; name: string };
  provider: Eip1193Provider;
}

const discovered = new Map<string, Eip1193Provider>();
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

if (typeof window !== "undefined") {
  window.addEventListener("eip6963:announceProvider", ((event: CustomEvent<Eip6963ProviderDetail>) => {
    const { info, provider } = event.detail ?? {};
    if (!info?.uuid || !provider) return;
    const isNew = !discovered.has(info.uuid);
    discovered.set(info.uuid, provider);
    if (isNew) notify();
  }) as EventListener);
  window.dispatchEvent(new Event("eip6963:requestProvider"));
}

/** Re-runs `fn` whenever a new wallet is discovered after this call (e.g. a
 * late EIP-6963 announce). Returns an unsubscribe function. */
export function onWalletDiscovered(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getProvider(): Eip1193Provider | null {
  if (typeof window === "undefined") return null;
  const first = discovered.values().next();
  if (!first.done) return first.value;
  return window.ethereum ?? null;
}

export function hasWallet(): boolean {
  return getProvider() !== null;
}

export async function getChainId(): Promise<number | null> {
  const provider = getProvider();
  if (!provider) return null;
  try {
    const hex = (await provider.request({ method: "eth_chainId" })) as string;
    return parseInt(hex, 16);
  } catch {
    return null;
  }
}

export async function getAccounts(): Promise<string[]> {
  const provider = getProvider();
  if (!provider) return [];
  try {
    return ((await provider.request({ method: "eth_accounts" })) as string[]) ?? [];
  } catch {
    return [];
  }
}

export async function connect(): Promise<string | null> {
  const provider = getProvider();
  if (!provider) throw new Error("No injected wallet found in this browser.");
  const accounts = (await provider.request({ method: "eth_requestAccounts" })) as string[];
  return accounts?.[0] ?? null;
}

/** Switches to Studio Next, adding the chain first if the wallet lacks it. */
export async function switchToStudioNext(): Promise<void> {
  const provider = getProvider();
  if (!provider) throw new Error("No injected wallet found in this browser.");
  const chainIdHex = `0x${STUDIO_DEV_CHAIN_ID.toString(16)}`;
  try {
    await provider.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: chainIdHex }],
    });
  } catch (err: unknown) {
    const code = (err as { code?: number })?.code;
    // 4902 = chain not added yet. Anything else is a real failure.
    if (code === 4902) {
      await provider.request({
        method: "wallet_addEthereumChain",
        params: [studioDevChainParams()],
      });
      return;
    }
    throw err;
  }
}

export async function getBalanceWei(address: string): Promise<string> {
  const provider = getProvider();
  if (!provider) return "0";
  try {
    const hex = (await provider.request({
      method: "eth_getBalance",
      params: [address, "latest"],
    })) as string;
    return BigInt(hex).toString();
  } catch {
    return "0";
  }
}

export function shortAddress(address: string | null | undefined): string {
  if (!address || address.length < 10) return "--";
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Injected-wallet plumbing, locked to Studio Next (61997).
 *
 * This module never holds, reads, or accepts a private key. It asks the
 * injected provider to connect, and to add/switch to 61997 -- nothing else.
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

export function getProvider(): Eip1193Provider | null {
  if (typeof window === "undefined") return null;
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

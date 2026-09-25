"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  connect as connectWallet,
  getAccounts,
  getBalanceWei,
  getChainId,
  getProvider,
  hasWallet,
  onWalletDiscovered,
  shortAddress,
  switchToStudioNext,
} from "@/src/lib/datum/wallet";
import { STUDIO_DEV_CHAIN_ID } from "@/src/lib/datum/network";
import { formatGen } from "@/src/lib/datum/format";

interface WalletState {
  available: boolean;
  account: string | null;
  chainId: number | null;
  balanceWei: string;
  onRightChain: boolean;
  error: string | null;
  connect: () => Promise<void>;
  switchChain: () => Promise<void>;
}

const Ctx = createContext<WalletState | null>(null);

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [available, setAvailable] = useState(false);
  const [account, setAccount] = useState<string | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [balanceWei, setBalanceWei] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const accounts = await getAccounts();
    const next = accounts[0] ?? null;
    setAccount(next);
    setChainId(await getChainId());
    setBalanceWei(next ? await getBalanceWei(next) : "0");
  }, []);

  useEffect(() => {
    let cancelled = false;
    let attached = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    let provider: ReturnType<typeof getProvider> = null;
    let onAccounts: (() => void) | null = null;
    let onChain: (() => void) | null = null;

    function attach() {
      if (attached || cancelled) return;
      const found = hasWallet();
      setAvailable(found);
      if (!found) return;
      attached = true;
      if (timer) clearInterval(timer);
      void refresh();

      provider = getProvider();
      onAccounts = () => void refresh();
      onChain = () => void refresh();
      provider?.on?.("accountsChanged", onAccounts);
      provider?.on?.("chainChanged", onChain);
    }

    // Injection is an async content script -- a wallet extension can
    // announce itself after this effect first runs. Retry briefly instead
    // of deciding "no wallet" from a single synchronous check.
    attach();
    let attempts = 0;
    timer = setInterval(() => {
      if (attached || cancelled || attempts >= 20) {
        if (timer) clearInterval(timer);
        return;
      }
      attempts += 1;
      attach();
    }, 150);

    const unsubscribe = onWalletDiscovered(attach);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      unsubscribe();
      provider?.removeListener?.("accountsChanged", onAccounts!);
      provider?.removeListener?.("chainChanged", onChain!);
    };
  }, [refresh]);

  const connect = useCallback(async () => {
    setError(null);
    try {
      await connectWallet();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [refresh]);

  const switchChain = useCallback(async () => {
    setError(null);
    try {
      await switchToStudioNext();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [refresh]);

  const value = useMemo<WalletState>(
    () => ({
      available,
      account,
      chainId,
      balanceWei,
      onRightChain: chainId === STUDIO_DEV_CHAIN_ID,
      error,
      connect,
      switchChain,
    }),
    [available, account, chainId, balanceWei, error, connect, switchChain]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWallet(): WalletState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWallet must be used inside <WalletProvider>");
  return ctx;
}

export function ConnectButton() {
  const w = useWallet();

  if (!w.available) {
    return (
      <span className="pill" title="No injected wallet detected in this browser">
        No wallet
      </span>
    );
  }

  if (!w.account) {
    return (
      <button className="btn btn-sm" onClick={() => void w.connect()}>
        Connect
      </button>
    );
  }

  if (!w.onRightChain) {
    return (
      <button className="btn btn-sm" onClick={() => void w.switchChain()}>
        Switch to 61997
      </button>
    );
  }

  return (
    <span className="pill mono" title={w.account}>
      {formatGen(w.balanceWei)} GEN &middot; {shortAddress(w.account)}
    </span>
  );
}

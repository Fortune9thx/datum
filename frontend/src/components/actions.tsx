"use client";

import { useState } from "react";
import { useWallet } from "./Wallet";
import type { LiveStatus } from "@/src/lib/datum/network";

/**
 * The single source of truth for "can this address write right now".
 * Returns a specific, honest reason string, or null when writes are allowed.
 * Buttons never silently no-op: they carry the real reason.
 */
export function useWriteGate(status: LiveStatus): string | null {
  const w = useWallet();
  if (status.kind === "loading") return "checking contract status";
  if (status.kind === "no-address") return "contract not deployed";
  if (status.kind === "no-code") return "no code at this address — Studio Next was reset";
  if (status.kind === "rpc-down") return "cannot reach studio-dev.genlayer.com";
  if (!w.available) return "no injected wallet in this browser";
  if (!w.account) return "wallet not connected";
  if (!w.onRightChain) return "wrong network — switch to Studio Next (61997)";
  return null;
}

export function WriteNote({ reason }: { reason: string | null }) {
  if (!reason) return null;
  return (
    <p className="mono muted" style={{ fontSize: 11, marginTop: 10 }}>
      writes disabled — {reason}
    </p>
  );
}

/** A write button that reports the real outcome, never a fake success. */
export function ActionButton({
  label,
  reason,
  run,
  ghost = false,
}: {
  label: string;
  reason: string | null;
  run: () => Promise<string>;
  ghost?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  async function onClick() {
    setBusy(true);
    setResult(null);
    try {
      const hash = await run();
      setResult({ ok: true, text: `submitted: ${hash}` });
    } catch (err) {
      setResult({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <span style={{ display: "inline-flex", flexDirection: "column", gap: 6 }}>
      <button
        className={ghost ? "btn btn-ghost btn-sm" : "btn btn-sm"}
        disabled={!!reason || busy}
        title={reason ?? label}
        onClick={() => void onClick()}
      >
        {busy ? "submitting…" : label}
      </button>
      {result ? (
        <span
          className="mono"
          style={{ fontSize: 10.5, color: result.ok ? "var(--up)" : "var(--down)" }}
        >
          {result.text}
        </span>
      ) : null}
    </span>
  );
}

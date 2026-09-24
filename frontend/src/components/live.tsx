"use client";

import { useEffect, useState } from "react";
import {
  probeContract,
  explorerAddressUrl,
  STUDIO_DEV_EXPLORER_URL,
  type LiveStatus,
} from "@/src/lib/datum/network";

/**
 * Probes the contract once on mount. Until it resolves the app shows
 * skeletons -- never rows, never zeros presented as settled facts.
 */
export function useLive(): LiveStatus {
  const [status, setStatus] = useState<LiveStatus>({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    probeContract().then((next) => {
      if (alive) setStatus(next);
    });
    return () => {
      alive = false;
    };
  }, []);

  return status;
}

/**
 * Each state says exactly what is true. "Cannot reach the RPC" is never
 * dressed up as "no events", and a Studio Next reset is named as a reset.
 */
export function StatusBanner({ status }: { status: LiveStatus }) {
  if (status.kind === "loading") return null;

  if (status.kind === "no-address") {
    return (
      <div className="banner banner-warn">
        <span className="mono" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
          NOT DEPLOYED
        </span>
        <span>
          Contract not deployed on Studio Next (61997). Reads return nothing and writes are
          disabled — this app shows no placeholder or demo data in place of a live contract.
        </span>
      </div>
    );
  }

  if (status.kind === "no-code") {
    return (
      <div className="banner banner-warn">
        <span className="mono" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
          NO CODE
        </span>
        <span>
          No code at this address. Studio Next was reset. Redeploy.{" "}
          <span className="mono muted">{status.address}</span>
        </span>
      </div>
    );
  }

  if (status.kind === "rpc-down") {
    return (
      <div className="banner banner-down">
        <span className="mono" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
          RPC DOWN
        </span>
        <span>
          Cannot reach studio-dev.genlayer.com. Nothing below is current — this is a read
          failure, not an empty board.
        </span>
      </div>
    );
  }

  return (
    <div className="banner banner-up">
      <span className="mono" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
        LIVE
      </span>
      <span>
        <span className="mono">{status.address}</span>{" "}
        <a
          className="mono"
          style={{ textDecoration: "underline" }}
          href={explorerAddressUrl(status.address)}
          target="_blank"
          rel="noreferrer"
        >
          explorer
        </a>
      </span>
    </div>
  );
}

export function ExplorerLink() {
  return (
    <a href={STUDIO_DEV_EXPLORER_URL} target="_blank" rel="noreferrer" className="mono small">
      explorer
    </a>
  );
}

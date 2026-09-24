"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBanner, useLive } from "@/src/components/live";
import { PageHead, Stat, Empty, Skeleton } from "@/src/components/ui";
import { ActionButton, WriteNote, useWriteGate } from "@/src/components/actions";
import { useWallet } from "@/src/components/Wallet";
import { getPositions, getClaimableWei, write } from "@/src/lib/datum/sdk";
import { STATE_LABELS } from "@/src/lib/datum/registry";
import { formatGen } from "@/src/lib/datum/format";
import type { DatumPosition } from "@/src/lib/datum/types";

export default function PortfolioPage() {
  const status = useLive();
  const wallet = useWallet();
  const reason = useWriteGate(status);

  const [rows, setRows] = useState<DatumPosition[]>([]);
  const [claimable, setClaimable] = useState("0");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status.kind === "loading") return;
    if (status.kind !== "live" || !wallet.account) {
      setRows([]);
      setClaimable("0");
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    Promise.all([getPositions(wallet.account), getClaimableWei(wallet.account)]).then(
      ([page, owed]) => {
        if (!alive) return;
        setRows(page.rows);
        setClaimable(owed);
        setLoading(false);
      }
    );
    return () => {
      alive = false;
    };
  }, [status, wallet.account]);

  const pending = status.kind === "loading" || loading;
  const account = (wallet.account ?? "0x") as `0x${string}`;
  const staked = rows
    .reduce((acc, r) => acc + BigInt(String(r.stake ?? 0)), 0n)
    .toString();

  return (
    <>
      <PageHead
        title="Portfolio"
        sub="Your side of every event you are bonded to, and anything the internal ledger currently owes you."
      />

      <div style={{ marginBottom: 24 }}>
        <StatusBanner status={status} />
      </div>

      <div className="grid-3" style={{ marginBottom: 24 }}>
        <Stat value={pending ? "--" : rows.length} label="Positions" />
        <Stat value={pending ? "--" : `${formatGen(staked)} GEN`} label="At stake" />
        <Stat value={pending ? "--" : `${formatGen(claimable)} GEN`} label="Claimable" />
      </div>

      <div className="card" style={{ minHeight: 480 }}>
        <div className="card-head">
          <div className="h3">Positions</div>
          {!wallet.account ? (
            <span className="pill">wallet not connected</span>
          ) : (
            <span className="pill mono">{wallet.account}</span>
          )}
        </div>

        {pending ? (
          <Skeleton rows={6} />
        ) : rows.length === 0 ? (
          <Empty
            title="No positions"
            body={
              !wallet.account
                ? "Connect a wallet to read the positions held by that address. Nothing is assumed about who you are."
                : status.kind === "live"
                  ? "This address is not bonded to any event on this contract."
                  : "There is no live contract to read positions from."
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Side</th>
                  <th>Stake</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.event_id}>
                    <td className="mono">
                      <Link href={`/app/e/${r.event_id}`} style={{ textDecoration: "underline" }}>
                        {r.event_id}
                      </Link>
                    </td>
                    <td className="mono">{r.side ?? "--"}</td>
                    <td className="mono">{formatGen(String(r.stake ?? 0))} GEN</td>
                    <td>
                      <span className="pill">
                        {r.state ? STATE_LABELS[r.state] ?? r.state : "--"}
                      </span>
                    </td>
                    <td>
                      <ActionButton
                        label="Claim"
                        reason={reason}
                        ghost
                        run={() => write.claim(account, r.event_id)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <WriteNote reason={reason} />
    </>
  );
}

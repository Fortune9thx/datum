"use client";

import { useEffect, useState } from "react";
import { StatusBanner, useLive } from "@/src/components/live";
import { PageHead, KV, Empty, Skeleton } from "@/src/components/ui";
import { useWallet } from "@/src/components/Wallet";
import { getActivity } from "@/src/lib/datum/sdk";
import { CLASSES, STATE_LABELS } from "@/src/lib/datum/registry";
import { formatGen, formatScaledValue, formatWindowCompact } from "@/src/lib/datum/format";
import type { ActivityRow } from "@/src/lib/datum/types";

export default function ActivityPage() {
  const status = useLive();
  const wallet = useWallet();

  const [rows, setRows] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ActivityRow | null>(null);

  useEffect(() => {
    if (status.kind === "loading") return;
    if (status.kind !== "live" || !wallet.account) {
      setRows([]);
      setSelected(null);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    getActivity(wallet.account).then((page) => {
      if (!alive) return;
      setRows(page.rows);
      setSelected(page.rows[0] ?? null);
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [status, wallet.account]);

  const pending = status.kind === "loading" || loading;
  const unit = CLASSES.find((c) => c.id === selected?.class)?.unit ?? "";

  return (
    <>
      <PageHead
        title="Activity"
        sub="Every event this address has touched, and the stored record behind the one you select."
      />

      <div style={{ marginBottom: 24 }}>
        <StatusBanner status={status} />
      </div>

      <div className="split-62">
        <div className="card" style={{ minHeight: 480 }}>
          <div className="card-head">
            <div className="h3">Ledger</div>
            {!wallet.account ? (
              <span className="pill">wallet not connected</span>
            ) : (
              <span className="pill mono">{rows.length} events</span>
            )}
          </div>

          {pending ? (
            <Skeleton rows={6} />
          ) : rows.length === 0 ? (
            <Empty
              title="No activity"
              body={
                !wallet.account
                  ? "Connect a wallet to read the events that address has taken part in."
                  : status.kind === "live"
                    ? "This address has not taken part in any event on this contract."
                    : "There is no live contract to read activity from."
              }
            />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Class</th>
                    <th>Window (UTC)</th>
                    <th>Verdict</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.id}
                      onClick={() => setSelected(r)}
                      style={{
                        cursor: "pointer",
                        background: selected?.id === r.id ? "var(--paper)" : undefined,
                      }}
                    >
                      <td className="mono">{r.id}</td>
                      <td className="mono">{r.class}</td>
                      <td className="mono muted">{formatWindowCompact(r.window)}</td>
                      <td className="mono">{r.verdict ?? "--"}</td>
                      <td>
                        <span className="pill">{STATE_LABELS[r.state] ?? r.state}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Inspector is always on -- it states its own emptiness rather than hiding. */}
        <div className="card">
          <div className="card-head">
            <div className="h3">Inspector</div>
            <span className="pill">{selected ? `event ${selected.id}` : "nothing selected"}</span>
          </div>
          <div className="card-p">
            {!selected ? (
              <p className="lead small">
                Select a row to read its stored constitution and settled record. Nothing is
                shown here until there is something real to show.
              </p>
            ) : (
              <>
                <KV k="state" v={STATE_LABELS[selected.state] ?? selected.state} />
                <KV k="class" v={selected.class} />
                <KV
                  k="station id"
                  v={selected.station_id ?? (selected.bbox ? String(selected.bbox) : "--")}
                />
                <KV k="metric" v={selected.metric} />
                <KV
                  k="threshold"
                  v={`${selected.cmp} ${formatScaledValue(selected.threshold)} ${unit}`}
                />
                <KV k="window" v={formatWindowCompact(selected.window)} />
                <KV k="publishers" v={selected.publishers.join(" · ")} />
                <KV k="status policy" v={selected.product_status_policy} />
                <KV k="verdict" v={selected.verdict ?? "--"} />
                <KV k="code" v={selected.code ?? "--"} />
                <KV
                  k="agreed value"
                  v={
                    selected.agreed_value !== null && selected.agreed_value !== undefined
                      ? `${formatScaledValue(selected.agreed_value)} ${unit}`
                      : "--"
                  }
                />
                <KV k="creator stake" v={`${formatGen(String(selected.creator_stake ?? 0))} GEN`} />
                <KV
                  k="acceptor stake"
                  v={`${formatGen(String(selected.acceptor_stake ?? 0))} GEN`}
                />
                <KV
                  k="constitution hash"
                  v={<span style={{ fontSize: 11 }}>{selected.constitution_hash}</span>}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

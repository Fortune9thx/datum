"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBanner, useLive } from "@/src/components/live";
import { PageHead, Stat, Empty, Skeleton } from "@/src/components/ui";
import { getBoard } from "@/src/lib/datum/sdk";
import { CLASSES, STATE_LABELS } from "@/src/lib/datum/registry";
import { formatGen, formatScaledValue, formatWindowCompact } from "@/src/lib/datum/format";
import type { DatumEvent } from "@/src/lib/datum/types";

const STATE_FILTERS = ["", "OPEN", "ACTIVE", "VERDICT_PENDING", "FINALIZED"] as const;

function unitFor(cls: string): string {
  return CLASSES.find((c) => c.id === cls)?.unit ?? "";
}

function potOf(e: DatumEvent): string {
  const creator = BigInt(e.creator_stake ?? 0);
  const acceptor = BigInt(e.acceptor_stake ?? 0);
  return (creator + acceptor).toString();
}

export default function BoardPage() {
  const status = useLive();
  const [rows, setRows] = useState<DatumEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    if (status.kind === "loading") return;
    if (status.kind !== "live") {
      setRows([]);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    getBoard(0, 50, filter).then((page) => {
      if (!alive) return;
      setRows(page.rows);
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [status, filter]);

  const pending = status.kind === "loading" || loading;

  const openCount = rows.filter((r) => r.state === "OPEN").length;
  const activeCount = rows.filter((r) => r.state === "ACTIVE").length;
  const settledCount = rows.filter((r) => r.state === "FINALIZED").length;
  const totalPot = rows.reduce((acc, r) => acc + BigInt(potOf(r)), 0n).toString();

  return (
    <>
      <PageHead
        title="Board"
        sub="Official station observation at locked publishers for this window."
        action={
          <Link href="/app/create" className="btn">
            Create an event
          </Link>
        }
      />

      <div style={{ marginBottom: 24 }}>
        <StatusBanner status={status} />
      </div>

      <div className="grid-4" style={{ marginBottom: 24 }}>
        <Stat value={pending ? "--" : openCount} label="Open" />
        <Stat value={pending ? "--" : activeCount} label="Active" />
        <Stat value={pending ? "--" : settledCount} label="Finalized" />
        <Stat value={pending ? "--" : `${formatGen(totalPot)} GEN`} label="Total pot" />
      </div>

      <div className="card" style={{ minHeight: 480 }}>
        <div className="tabs">
          {STATE_FILTERS.map((s) => (
            <button
              key={s || "ALL"}
              className="tab"
              data-on={filter === s ? "1" : "0"}
              onClick={() => setFilter(s)}
            >
              {s ? STATE_LABELS[s] ?? s : "All"}
            </button>
          ))}
        </div>

        {pending ? (
          <Skeleton rows={6} />
        ) : rows.length === 0 ? (
          <Empty
            title="No events to show"
            body={
              status.kind === "live"
                ? "This contract is live and currently holds no events matching that filter."
                : "There is no contract to read from yet, so there is nothing to list. This board never shows placeholder or demo rows."
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Station id</th>
                  <th>Window (UTC)</th>
                  <th>Threshold</th>
                  <th>Pot</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id}>
                    <td className="mono">
                      <Link href={`/app/e/${e.id}`} style={{ textDecoration: "underline" }}>
                        {e.class}
                      </Link>
                    </td>
                    <td className="mono">{e.station_id ?? (e.bbox ? "bbox" : "--")}</td>
                    <td className="mono muted">{formatWindowCompact(e.window)}</td>
                    <td className="mono">
                      {e.cmp} {formatScaledValue(e.threshold)} {unitFor(e.class)}
                    </td>
                    <td className="mono">{formatGen(potOf(e))} GEN</td>
                    <td>
                      <span className="pill">{STATE_LABELS[e.state] ?? e.state}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

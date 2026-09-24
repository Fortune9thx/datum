"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBanner, useLive } from "@/src/components/live";
import { PageHead, KV, Empty, Skeleton } from "@/src/components/ui";
import { ActionButton, WriteNote, useWriteGate } from "@/src/components/actions";
import { useWallet } from "@/src/components/Wallet";
import { getEvent, getRecord, write } from "@/src/lib/datum/sdk";
import { CLASSES, STATE_LABELS } from "@/src/lib/datum/registry";
import { formatGen, formatScaledValue, formatWindowCompact } from "@/src/lib/datum/format";
import type { DatumEvent, DatumRecord, SourceRow } from "@/src/lib/datum/types";

export default function TicketPage() {
  const params = useParams<{ id: string }>();
  const eventId = String(params?.id ?? "");
  const status = useLive();
  const wallet = useWallet();
  const reason = useWriteGate(status);

  const [event, setEvent] = useState<DatumEvent | null>(null);
  const [record, setRecord] = useState<DatumRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);

  useEffect(() => {
    if (status.kind === "loading") return;
    if (status.kind !== "live") {
      setEvent(null);
      setRecord(null);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    Promise.all([getEvent(eventId), getRecord(eventId)]).then(([e, r]) => {
      if (!alive) return;
      setEvent(e);
      setRecord(r);
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [status, eventId]);

  const pending = status.kind === "loading" || loading;
  const unit = CLASSES.find((c) => c.id === event?.class)?.unit ?? "";
  const sources = record?.accepted_record?.sources ?? null;
  const publisherIds = sources ? Object.keys(sources) : event?.publishers ?? [];
  const account = (wallet.account ?? "0x") as `0x${string}`;

  return (
    <>
      <PageHead
        title={`Event ${eventId}`}
        sub="One claim, one locked constitution, one settled number."
        action={
          <Link href="/app" className="btn btn-ghost">
            Back to board
          </Link>
        }
      />

      <div style={{ marginBottom: 24 }}>
        <StatusBanner status={status} />
      </div>

      {pending ? (
        <div className="card">
          <Skeleton rows={8} />
        </div>
      ) : !event ? (
        <div className="card" style={{ minHeight: 420 }}>
          <Empty
            title="No such event to read"
            body={
              status.kind === "live"
                ? "This contract is live but holds no event with that id."
                : "There is no live contract to read this event from. Nothing is shown rather than a placeholder ticket."
            }
          />
        </div>
      ) : (
        <div className="split">
          {/* ------------------------------------------------ sides + stake */}
          <div className="card">
            <div className="card-head">
              <div className="h3">Sides and stake</div>
              <span className="pill">{STATE_LABELS[event.state] ?? event.state}</span>
            </div>
            <div className="card-p">
              <div className="grid-3" style={{ gap: 12, marginBottom: 20 }}>
                <div className="stat">
                  <div className="stat-v mono">{event.creator_side}</div>
                  <div className="stat-k">Creator</div>
                </div>
                <div className="stat">
                  <div className="stat-v mono">{event.acceptor_side ?? "--"}</div>
                  <div className="stat-k">Acceptor</div>
                </div>
                <div className="stat">
                  <div className="stat-v mono">{record?.verdict ?? "--"}</div>
                  <div className="stat-k">Verdict</div>
                </div>
              </div>

              <KV k="creator" v={<span className="mono">{event.creator}</span>} />
              <KV k="creator stake" v={`${formatGen(String(event.creator_stake ?? 0))} GEN`} />
              <KV k="acceptor" v={<span className="mono">{event.acceptor ?? "--"}</span>} />
              <KV
                k="acceptor stake"
                v={`${formatGen(String(event.acceptor_stake ?? 0))} GEN`}
              />
              <KV k="class" v={event.class} />
              <KV k="station id" v={event.station_id ?? (event.bbox ? String(event.bbox) : "--")} />
              <KV k="metric" v={event.metric} />
              <KV
                k="threshold"
                v={`${event.cmp} ${formatScaledValue(event.threshold)} ${unit}`}
              />
              <KV k="window" v={formatWindowCompact(event.window)} />
              <KV k="publishers" v={event.publishers.join(" · ")} />
              <KV k="status policy" v={event.product_status_policy} />
              <KV k="tolerance" v={`${formatScaledValue(event.tolerance)} ${unit}`} />
              <KV k="code" v={record?.code ?? "--"} />
              <KV
                k="agreed value"
                v={
                  record?.agreed_value !== null && record?.agreed_value !== undefined
                    ? `${formatScaledValue(record.agreed_value)} ${unit}`
                    : "--"
                }
              />
              <KV
                k="constitution hash"
                v={<span style={{ fontSize: 11 }}>{event.constitution_hash}</span>}
              />

              <div
                style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 20 }}
              >
                <ActionButton
                  label="Accept YES"
                  reason={reason}
                  run={() => write.acceptEvent(account, eventId, "YES", 0n)}
                />
                <ActionButton
                  label="Accept NO"
                  reason={reason}
                  ghost
                  run={() => write.acceptEvent(account, eventId, "NO", 0n)}
                />
                <ActionButton
                  label="Adjudicate"
                  reason={reason}
                  ghost
                  run={() => write.adjudicate(account, eventId, 0n)}
                />
                <ActionButton
                  label="Finalize"
                  reason={reason}
                  ghost
                  run={() => write.finalize(account, eventId)}
                />
                <ActionButton
                  label="Claim"
                  reason={reason}
                  ghost
                  run={() => write.claim(account, eventId)}
                />
                <ActionButton
                  label="Recover refund"
                  reason={reason}
                  ghost
                  run={() => write.recoverRefund(account, eventId)}
                />
              </div>
              <WriteNote reason={reason} />
            </div>
          </div>

          {/* ---------------------------------------------------- evidence */}
          <div className="card">
            <div className="card-head">
              <div className="h3">Evidence</div>
              <span className="pill">one row per publisher</span>
            </div>

            {publisherIds.length === 0 ? (
              <Empty
                title="No evidence yet"
                body="Evidence appears only after the window closes and an adjudication record is accepted."
              />
            ) : (
              <>
                <div className="tabs">
                  {publisherIds.map((p, i) => (
                    <button
                      key={p}
                      className="tab"
                      data-on={tab === i ? "1" : "0"}
                      onClick={() => setTab(i)}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                <div className="card-p">
                  <EvidencePane row={sources?.[publisherIds[tab]] ?? null} unit={unit} />
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function EvidencePane({ row, unit }: { row: SourceRow | null; unit: string }) {
  if (!row) {
    return (
      <p className="lead small">
        No accepted row for this publisher yet. A publisher with no accepted row never counts
        as agreement, and never counts as a zero reading.
      </p>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <span className={row.usable ? "pill pill-up" : "pill pill-down"}>
          {row.usable ? "usable" : "unusable"}
        </span>
      </div>
      <KV k="station_id" v={row.station_id ?? "--"} />
      <KV k="t" v={row.t ? new Date(row.t * 1000).toISOString() : "--"} />
      <KV
        k="value_native"
        v={row.value_native !== null && row.value_native !== undefined ? String(row.value_native) : "--"}
      />
      <KV k="unit" v={row.unit ?? "--"} />
      <KV k="product_status" v={row.product_status ?? "--"} />
      <KV
        k="converted"
        v={
          row.converted !== null && row.converted !== undefined
            ? `${formatScaledValue(row.converted)} ${unit}`
            : "--"
        }
      />
      <KV k="reason" v={row.reason ?? "--"} />
      <KV
        k="digest"
        v={<span style={{ fontSize: 11 }}>{row.digest ?? "--"}</span>}
      />
    </div>
  );
}

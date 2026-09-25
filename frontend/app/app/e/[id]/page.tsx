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
import {
  appealBondWei,
  formatGen,
  formatScaledValue,
  formatWindowCompact,
  parseGenToWei,
} from "@/src/lib/datum/format";
import type { AppealInfo, DatumEvent, DatumRecord, SourceRow } from "@/src/lib/datum/types";

// Immutable economics, must match contracts/datum_lib.py exactly --
// ADJUDICATE_BOND = 2 * 10**16 (0.02 GEN). accept_event's required value
// is the event's own creator_stake, read from the loaded record instead
// (it varies per event, unlike the bond). Appeal bond is computed from
// the event's own creator_stake via appealBondWei(), since it scales
// with the wager, not a fixed constant like the other two.
const ADJUDICATE_BOND_GEN = "0.02";

const APPEAL_GROUNDS: AppealInfo["ground"][] = ["VALUE", "STATION", "WINDOW", "STATUS", "REVISED"];

const LAPSE_APPEAL_STALL_SECONDS = 60 * 60; // must match datum_lib.LAPSE_APPEAL_STALL

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
  const [ground, setGround] = useState<AppealInfo["ground"]>("VALUE");

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

  // Best-effort client-side gating so irrelevant buttons don't clutter the
  // page -- the contract's own checks remain authoritative regardless of
  // what renders here; a stale client clock or state read never grants a
  // write that the contract would otherwise refuse.
  const nowSec = Math.floor(Date.now() / 1000);
  const isCreator = !!wallet.account && !!event && wallet.account.toLowerCase() === event.creator.toLowerCase();
  const isAcceptor = !!wallet.account && !!event?.acceptor && wallet.account.toLowerCase() === event.acceptor.toLowerCase();
  const isParty = isCreator || isAcceptor;
  const appealBond = event ? appealBondWei(event.creator_stake) : 0n;
  const appealWindowOpen =
    !!event && nowSec < event.last_state_change_at + event.appeal_window;
  const appealStalled =
    !!event?.appeal && nowSec >= event.appeal.opened_at + LAPSE_APPEAL_STALL_SECONDS;

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
                  run={() =>
                    write.acceptEvent(account, eventId, "YES", BigInt(event.creator_stake))
                  }
                />
                <ActionButton
                  label="Accept NO"
                  reason={reason}
                  ghost
                  run={() =>
                    write.acceptEvent(account, eventId, "NO", BigInt(event.creator_stake))
                  }
                />
                <ActionButton
                  label="Adjudicate"
                  reason={reason}
                  ghost
                  run={() =>
                    write.adjudicate(account, eventId, BigInt(parseGenToWei(ADJUDICATE_BOND_GEN)))
                  }
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

                {event.state === "OPEN" && (
                  <ActionButton
                    label="Cancel"
                    reason={reason ?? (isCreator ? null : "only the creator can cancel")}
                    ghost
                    run={() => write.cancelEvent(account, eventId)}
                  />
                )}

                {event.state === "OPEN" && (
                  <ActionButton
                    label="Expire (slash create bond)"
                    reason={reason}
                    ghost
                    run={() => write.expireEvent(account, eventId)}
                  />
                )}

                {event.state === "VERDICT_PENDING" && (
                  <ActionButton
                    label={`Appeal (${ground}) · ${formatGen(appealBond.toString())} GEN`}
                    reason={
                      reason ??
                      (!isParty
                        ? "only a bonded party can appeal"
                        : !appealWindowOpen
                          ? "appeal window has closed"
                          : null)
                    }
                    ghost
                    run={() => write.appeal(account, eventId, ground, appealBond)}
                  />
                )}

                {event.state === "APPEALED" && (
                  <ActionButton
                    label={`Re-adjudicate · ${ADJUDICATE_BOND_GEN} GEN`}
                    reason={reason}
                    ghost
                    run={() =>
                      write.reAdjudicate(
                        account,
                        eventId,
                        BigInt(parseGenToWei(ADJUDICATE_BOND_GEN))
                      )
                    }
                  />
                )}

                {event.state === "APPEALED" && (
                  <ActionButton
                    label="Lapse appeal (restore prior verdict)"
                    reason={
                      reason ?? (appealStalled ? null : "appeal has not stalled yet (1h)")
                    }
                    ghost
                    run={() => write.lapseAppeal(account, eventId)}
                  />
                )}

                {(event.state === "FINALIZED" ||
                  event.state === "CANCELED" ||
                  event.state === "EXPIRED") && (
                  <ActionButton
                    label="Reclaim bonds (receipt)"
                    reason={reason}
                    ghost
                    run={() => write.reclaimBonds(account, eventId)}
                  />
                )}
              </div>

              {event.state === "VERDICT_PENDING" && isParty && (
                <div className="field" style={{ maxWidth: 220, marginTop: 4 }}>
                  <label className="field-label">Appeal ground</label>
                  <select
                    className="select"
                    value={ground}
                    onChange={(e) => setGround(e.target.value as AppealInfo["ground"])}
                  >
                    {APPEAL_GROUNDS.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {event.appeal && (
                <div style={{ marginTop: 16 }}>
                  <div className="label" style={{ marginBottom: 8 }}>
                    <span>OPEN APPEAL</span>
                  </div>
                  <KV k="appellant" v={<span className="mono">{event.appeal.appellant}</span>} />
                  <KV k="ground" v={event.appeal.ground} />
                  <KV k="bond" v={`${formatGen(String(event.appeal.bond))} GEN`} />
                  <KV k="prior verdict" v={event.appeal.prior_verdict ?? "--"} />
                </div>
              )}

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

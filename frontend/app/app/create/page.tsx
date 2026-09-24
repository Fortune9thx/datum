"use client";

import { useMemo, useState } from "react";
import { StatusBanner, useLive } from "@/src/components/live";
import { PageHead } from "@/src/components/ui";
import { ActionButton, WriteNote, useWriteGate } from "@/src/components/actions";
import { useWallet } from "@/src/components/Wallet";
import { write } from "@/src/lib/datum/sdk";
import { CLASSES } from "@/src/lib/datum/registry";
import { parseGenToWei } from "@/src/lib/datum/format";
import type { InstrumentClass } from "@/src/lib/datum/types";

/**
 * Client-side mirror of contracts/datum_lib.py's create-time refusals. This
 * is a courtesy pre-check so the form can explain a refusal before costing
 * gas -- the contract remains authoritative and re-checks every rule.
 */
const STATION_RE: Partial<Record<InstrumentClass, RegExp>> = {
  STATION_PRECIP: /^[A-Z0-9]{4,11}$/,
  STATION_TEMP: /^[A-Z0-9]{4,11}$/,
  STAGE: /^\d{8}$/,
};

const MIN_WINDOW_S: Record<InstrumentClass, number> = {
  STATION_PRECIP: 6 * 3600,
  STATION_TEMP: 24 * 3600,
  STAGE: 6 * 3600,
  QUAKES: 3600,
};

const MIN_LEAD_S: Record<InstrumentClass, number> = {
  STATION_PRECIP: 2 * 3600,
  STATION_TEMP: 2 * 3600,
  STAGE: 2 * 3600,
  QUAKES: 30 * 60,
};

const CREATE_BOND_GEN = "0.05";

function toUnix(local: string): number | null {
  if (!local) return null;
  const ms = Date.parse(`${local}:00Z`);
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

export default function CreatePage() {
  const status = useLive();
  const wallet = useWallet();
  const reason = useWriteGate(status);

  const [cls, setCls] = useState<InstrumentClass>("STAGE");
  const [stationId, setStationId] = useState("01646500");
  const [bbox, setBbox] = useState("-122.6, 37.2, -121.7, 38.0");
  const [metric, setMetric] = useState("stage");
  const [threshold, setThreshold] = useState("3.50");
  const [cmp, setCmp] = useState("gte");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [policy, setPolicy] = useState("FINAL_ONLY");
  const [side, setSide] = useState("YES");
  const [stake, setStake] = useState("0.10");

  const spec = CLASSES.find((c) => c.id === cls)!;

  function onClassChange(next: InstrumentClass) {
    setCls(next);
    const nextSpec = CLASSES.find((c) => c.id === next)!;
    setMetric(nextSpec.metric[0]);
    if (next !== "QUAKES") setStationId(nextSpec.idExample);
  }

  const { payload, problems } = useMemo(() => {
    const issues: string[] = [];
    const startTs = toUnix(start);
    const endTs = toUnix(end);
    const now = Math.floor(Date.now() / 1000);

    if (cls === "QUAKES") {
      const parts = bbox.split(",").map((p) => Number(p.trim()));
      if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n))) {
        issues.push("bbox must be four numbers: min_lon, min_lat, max_lon, max_lat");
      } else if (!(parts[0] < parts[2] && parts[1] < parts[3])) {
        issues.push("bbox min values must be strictly less than max values");
      }
    } else {
      const re = STATION_RE[cls];
      if (!re || !re.test(stationId.trim().toUpperCase())) {
        issues.push(`station id does not match the ${cls} format (${spec.officialId})`);
      }
    }

    if (!spec.metric.includes(metric)) issues.push(`metric must be one of ${spec.metric.join(", ")}`);
    if (!Number.isFinite(Number(threshold))) issues.push("threshold must be a number");

    if (startTs === null || endTs === null) {
      issues.push("window start and end are required");
    } else {
      if (endTs - startTs < MIN_WINDOW_S[cls]) {
        issues.push(`window is below the ${cls} minimum of ${spec.minWindowLabel}`);
      }
      if (startTs < now + MIN_LEAD_S[cls]) {
        issues.push(`window starts below the ${cls} minimum lead of ${spec.minLeadLabel}`);
      }
    }

    if (!Number.isFinite(Number(stake)) || Number(stake) < 0.01) {
      issues.push("stake must be at least 0.01 GEN");
    }

    const body: Record<string, unknown> = {
      class: cls,
      metric,
      threshold: Math.round(Number(threshold || 0) * 100),
      cmp,
      window: [startTs ?? 0, endTs ?? 0],
      publishers: spec.publishers.map((p) => p.id),
      product_status_policy: policy,
    };
    if (cls === "QUAKES") {
      body.bbox = bbox.split(",").map((p) => Number(p.trim()));
    } else {
      body.station_id = stationId.trim().toUpperCase();
    }

    return { payload: body, problems: issues };
  }, [cls, stationId, bbox, metric, threshold, cmp, start, end, policy, stake, spec]);

  const constitutionJson = JSON.stringify(payload, null, 2);
  const account = (wallet.account ?? "0x") as `0x${string}`;
  const blocked = reason ?? (problems.length ? "constitution is not valid yet" : null);

  return (
    <>
      <PageHead
        title="Create an event"
        sub="The constitution below is hashed before anyone can take the other side. After that, nothing in it can move."
      />

      <div style={{ marginBottom: 24 }}>
        <StatusBanner status={status} />
      </div>

      <div className="split">
        <div className="card card-p">
          <div className="field">
            <label className="field-label">Instrument class</label>
            <select
              className="select"
              value={cls}
              onChange={(e) => onClassChange(e.target.value as InstrumentClass)}
            >
              {CLASSES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} — {c.instrument}
                </option>
              ))}
            </select>
          </div>

          {cls === "QUAKES" ? (
            <div className="field">
              <label className="field-label">Bounding box (min_lon, min_lat, max_lon, max_lat)</label>
              <input className="input" value={bbox} onChange={(e) => setBbox(e.target.value)} />
            </div>
          ) : (
            <div className="field">
              <label className="field-label">Official station id — {spec.officialId}</label>
              <input
                className="input"
                value={stationId}
                onChange={(e) => setStationId(e.target.value)}
              />
            </div>
          )}

          <div className="field">
            <label className="field-label">Metric</label>
            <select className="select" value={metric} onChange={(e) => setMetric(e.target.value)}>
              {spec.metric.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label className="field-label">Comparator</label>
              <select className="select" value={cmp} onChange={(e) => setCmp(e.target.value)}>
                {["gt", "gte", "lt", "lte"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label">Threshold ({spec.unit})</label>
              <input
                className="input"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label className="field-label">Window start (UTC)</label>
              <input
                className="input"
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div className="field">
              <label className="field-label">Window end (UTC)</label>
              <input
                className="input"
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label className="field-label">Product status policy</label>
              <select className="select" value={policy} onChange={(e) => setPolicy(e.target.value)}>
                <option value="FINAL_ONLY">FINAL_ONLY</option>
                <option value="ALLOW_PRELIMINARY">ALLOW_PRELIMINARY</option>
              </select>
            </div>
            <div className="field">
              <label className="field-label">Your side</label>
              <select className="select" value={side} onChange={(e) => setSide(e.target.value)}>
                <option value="YES">YES</option>
                <option value="NO">NO</option>
              </select>
            </div>
          </div>

          <div className="field">
            <label className="field-label">Your stake (GEN)</label>
            <input className="input" value={stake} onChange={(e) => setStake(e.target.value)} />
          </div>

          <div style={{ marginTop: 20 }}>
            <ActionButton
              label={`Create · ${stake} GEN + ${CREATE_BOND_GEN} bond`}
              reason={blocked}
              run={() =>
                write.createEvent(
                  account,
                  JSON.stringify(payload),
                  side,
                  parseGenToWei(stake),
                  BigInt(parseGenToWei(stake)) + BigInt(parseGenToWei(CREATE_BOND_GEN))
                )
              }
            />
            <WriteNote reason={blocked} />
          </div>
        </div>

        {/* ------------------------------------------------------ preview */}
        <div className="card">
          <div className="card-head">
            <div className="h3">Preview</div>
            <span className={problems.length ? "pill pill-down" : "pill pill-up"}>
              {problems.length ? `${problems.length} refusal${problems.length > 1 ? "s" : ""}` : "passes pre-check"}
            </span>
          </div>
          <div className="card-p">
            {problems.length > 0 ? (
              <ul
                className="small"
                style={{ margin: "0 0 18px", paddingLeft: 18, color: "var(--down)" }}
              >
                {problems.map((p) => (
                  <li key={p} style={{ marginBottom: 6 }}>
                    {p}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="lead small" style={{ marginBottom: 18 }}>
                This constitution satisfies the client-side checks. The contract re-checks
                every rule and remains authoritative.
              </p>
            )}

            <div className="label" style={{ marginBottom: 10 }}>
              <span>CONSTITUTION JSON</span>
            </div>
            <pre
              className="mono"
              style={{
                margin: 0,
                padding: 16,
                background: "var(--paper)",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius)",
                fontSize: 11.5,
                lineHeight: 1.6,
                overflowX: "auto",
              }}
            >
              {constitutionJson}
            </pre>

            <p className="mono muted" style={{ fontSize: 11, marginTop: 14 }}>
              publishers are fixed by class and cannot be edited: {spec.publishers.map((p) => p.host).join(" · ")}
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

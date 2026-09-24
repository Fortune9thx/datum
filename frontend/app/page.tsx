import Link from "next/link";
import { PixelMosaic } from "@/src/components/PixelMosaic";
import { MarketingNav, MarketingFooter } from "@/src/components/chrome";
import { Brk, SectionLabel, KV } from "@/src/components/ui";
import { Faq } from "@/src/components/Faq";
import { CLASSES, ECONOMICS, REFUSALS } from "@/src/lib/datum/registry";

export default function Home() {
  return (
    <>
      {/* ------------------------------------------------- dark top strip */}
      <div className="band">
        <MarketingNav />
        <div className="rule" />
        <div className="container" style={{ paddingTop: 28 }}>
          <div
            className="mono"
            style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--mute-inv)" }}
          >
            STUDIO NEXT &nbsp;/&nbsp; CHAIN 61997 &nbsp;/&nbsp; GEN &nbsp;/&nbsp; STATE MAY RESET
          </div>
        </div>
        <PixelMosaic rows={12} cols={92} cell={12} seed={19} height={150} />
      </div>

      {/* -------------------------------------------------------- hero */}
      <section className="section">
        <div className="container">
          <SectionLabel n="01">THE QUESTION</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h1 className="h1">
              Official <Brk>station</Brk>.
              <br />
              Locked <Brk>window</Brk>.
              <br />
              Then the publishers speak.
            </h1>
            <div>
              <p className="lead">
                Two independent agencies. One threshold. Integer comparison. Inconclusive
                returns both stakes.
              </p>
              <div style={{ display: "flex", gap: 12, marginTop: 28, flexWrap: "wrap" }}>
                <Link href="/app" className="btn">
                  Open the board
                </Link>
                <Link href="/app/docs" className="btn btn-ghost">
                  Read the constitution
                </Link>
              </div>
            </div>
          </div>

          {/* ------------------------------------------ product stage */}
          <div className="card">
            <div className="card-head">
              <div className="h3">Anatomy of a settled event</div>
              <span className="pill">Illustration &middot; not live data</span>
            </div>

            <div className="split" style={{ gap: 0 }}>
              <div style={{ padding: 24, borderRight: "1px solid var(--line)" }}>
                <div className="label" style={{ marginBottom: 14 }}>
                  <span>CONSTITUTION</span>
                  <span className="label-dash" />
                  <span>HASHED BEFORE THE SECOND STAKE</span>
                </div>
                <KV k="class" v="STAGE" />
                <KV k="station id" v="01646500" />
                <KV k="metric" v="stage" />
                <KV k="threshold" v="3.50 m" />
                <KV k="comparator" v="gte" />
                <KV k="window" v="[ start, end )" />
                <KV k="publishers" v="USGS_WATER · NOAA_NWPS" />
                <KV k="status policy" v="FINAL_ONLY" />
                <KV k="tolerance" v="0.05 m" />
              </div>

              <div style={{ padding: 24 }}>
                <div className="label" style={{ marginBottom: 14 }}>
                  <span>EVIDENCE</span>
                  <span className="label-dash" />
                  <span>ONE ROW PER PUBLISHER</span>
                </div>
                <div className="stack-16">
                  {[
                    { p: "USGS_WATER", v: "3.62", u: "m", s: "FINAL" },
                    { p: "NOAA_NWPS", v: "3.60", u: "m", s: "FINAL" },
                  ].map((row) => (
                    <div
                      key={row.p}
                      style={{
                        border: "1px solid var(--line)",
                        borderRadius: "var(--radius)",
                        padding: 14,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: 8,
                        }}
                      >
                        <span className="mono" style={{ fontSize: 12 }}>
                          {row.p}
                        </span>
                        <span className="pill pill-up">usable</span>
                      </div>
                      <div className="mono muted" style={{ fontSize: 11.5, lineHeight: 1.7 }}>
                        station_id 01646500 &middot; unit {row.u} &middot; {row.s}
                        <br />
                        converted {row.v} m &middot; t inside window
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="rule" />
            <div
              style={{
                padding: "18px 24px",
                display: "flex",
                gap: 10,
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <span className="mono small muted">spread 0.02 m ≤ tolerance 0.05 m</span>
              <span className="muted">→</span>
              <span className="mono small muted">agreed 3.61 m</span>
              <span className="muted">→</span>
              <span className="mono small muted">3.61 ≥ 3.50</span>
              <span className="muted">→</span>
              <span className="pill pill-up">verdict YES &middot; code CLEAR</span>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ 3-up cards */}
      <section className="section-tight">
        <div className="container">
          <SectionLabel n="02">DIVISION OF LABOUR</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Judgment where it belongs.
              <br />
              Arithmetic where it belongs.
            </h2>
            <p className="lead">
              The contested part of the question is read by consensus. The part that decides
              money is integer code that anyone can re-run.
            </p>
          </div>

          <div className="grid-3">
            {[
              {
                t: "What consensus decides",
                b: "Which official station reported, whether the reading is a completed observation, its product status, its unit, its timestamp, and whether two independent publishers agree within tolerance.",
              },
              {
                t: "What code decides",
                b: "Everything that moves GEN. Readings are converted, scaled by 100, averaged across agreeing publishers and compared to the threshold in integer arithmetic. No float touches consensus.",
              },
              {
                t: "What neither may do",
                b: "The model's proposed verdict is re-derived from its own structured rows and the record is rejected outright on any mismatch. No admin key can force a verdict or move a pot.",
              },
            ].map((c) => (
              <div key={c.t} className="card card-p">
                <div className="h3" style={{ marginBottom: 12 }}>
                  {c.t}
                </div>
                <p className="lead small">{c.b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------- dark layers band */}
      <section className="band section">
        <div className="container">
          <SectionLabel n="03">ARCHITECTURE</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Three locked layers.
              <br />
              One settled number.
            </h2>
            <p className="lead">
              Each layer refuses a different lie: a station that is not a station, a source
              nobody agreed to, and a comparison nobody can reproduce.
            </p>
          </div>

          <div className="card" style={{ padding: 28, marginBottom: 28 }}>
            <Schematic />
          </div>

          <div className="grid-3">
            {[
              {
                n: "01",
                t: "Station registry",
                b: "Official ids only, matched against a per-class format. USGS eight-digit sites, NWS/ASOS/GHCN ids, or a validated bounding box. No free-text nicknames.",
              },
              {
                n: "02",
                t: "Publisher fetch",
                b: "Two independent publishers from a hardcoded per-class allowlist. Forecast and reanalysis products are refused by marker. Volatile keys are stripped before digest.",
              },
              {
                n: "03",
                t: "Integer compare",
                b: "Convert, scale, check agreement against tolerance, average, compare. Missing or conflicting readings settle INCONCLUSIVE and return both stakes whole.",
              },
            ].map((c) => (
              <div key={c.n} className="card card-p">
                <div className="flow-n" style={{ marginBottom: 12 }}>
                  [ {c.n} ]
                </div>
                <div className="h3" style={{ marginBottom: 10 }}>
                  {c.t}
                </div>
                <p className="lead small">{c.b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- flow */}
      <section className="section">
        <div className="container">
          <SectionLabel n="04">LIFECYCLE</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Understand the flow.
              <br />
              See how a claim settles.
            </h2>
            <p className="lead">
              Four steps, and a refund path out of every one of them. Nothing strands funds if
              the other side simply walks away.
            </p>
          </div>

          <div className="grid-4">
            {[
              {
                n: "01",
                t: "Create",
                b: "Post a constitution and one side of the claim with a 0.05 GEN bond. If the window opens with nobody opposite, the bond is slashed and the stake returns.",
              },
              {
                n: "02",
                t: "Accept",
                b: "A second address takes the other side at a matching stake. The constitution is hashed at this moment and cannot move again.",
              },
              {
                n: "03",
                t: "Observe",
                b: "The window closes. Only then can anyone adjudicate — the contract refuses to read an instrument that has not finished reporting.",
              },
              {
                n: "04",
                t: "Adjudicate",
                b: "Publishers are read, rows are validated, the verdict is re-derived and the pot resolves. Appeal re-reads the stored bytes; lapse restores the prior verdict.",
              },
            ].map((c) => (
              <div key={c.n} className="card card-p">
                <div className="flow-n" style={{ marginBottom: 12 }}>
                  [ {c.n} ]
                </div>
                <div className="h3" style={{ marginBottom: 10 }}>
                  {c.t}
                </div>
                <p className="lead small">{c.b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- classes */}
      <section className="section-tight">
        <div className="container">
          <SectionLabel n="05">INSTRUMENT CLASSES</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Four instruments.
              <br />
              No mixing.
            </h2>
            <p className="lead">
              A constitution names one class and stays inside it. Publishers from different
              product families cannot be combined in a single event.
            </p>
          </div>

          <div className="card table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Instrument</th>
                  <th>Official id</th>
                  <th>Unit</th>
                  <th>Min window</th>
                  <th>Min lead</th>
                  <th>Publishers</th>
                </tr>
              </thead>
              <tbody>
                {CLASSES.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{c.id}</td>
                    <td>{c.instrument}</td>
                    <td className="muted">{c.officialId}</td>
                    <td className="mono">{c.unit}</td>
                    <td className="mono">{c.minWindowLabel}</td>
                    <td className="mono">{c.minLeadLabel}</td>
                    <td className="mono muted">{c.publishers.map((p) => p.id).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------- economics */}
      <section className="section-tight">
        <div className="container">
          <SectionLabel n="06">ECONOMICS</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Fixed at deploy.
              <br />
              Quoted before you sign.
            </h2>
            <p className="lead">
              The fee is taken from decisive pots only. An event that settles INCONCLUSIVE
              returns both stakes in full and takes nothing.
            </p>
          </div>

          <div className="card" style={{ padding: "8px 24px" }}>
            {ECONOMICS.map((e) => (
              <div
                key={e.k}
                className="kv"
                style={{ alignItems: "baseline", gap: 24, flexWrap: "wrap" }}
              >
                <span className="kv-k" style={{ minWidth: 190 }}>
                  {e.k}
                </span>
                <span className="muted small" style={{ flex: 1, minWidth: 180 }}>
                  {e.note}
                </span>
                <span className="kv-v">{e.v}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --------------------------------------------------- refusals */}
      <section className="section-tight">
        <div className="container">
          <SectionLabel n="07">WHAT WE REFUSED</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              The refusals are
              <br />
              the product.
            </h2>
            <p className="lead">
              Anything below is rejected at create time or at adjudication time, not argued
              about afterwards.
            </p>
          </div>

          <div className="grid-3">
            {REFUSALS.map((r) => (
              <div key={r.t} className="card card-p">
                <div
                  className="mono"
                  style={{ fontSize: 11, color: "var(--down)", marginBottom: 10 }}
                >
                  [ REFUSED ]
                </div>
                <div className="h3" style={{ marginBottom: 10 }}>
                  {r.t}
                </div>
                <p className="lead small">{r.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------- faq */}
      <section className="section-tight">
        <div className="container">
          <SectionLabel n="08">QUESTIONS</SectionLabel>
          <div className="head-split" style={{ marginTop: 28 }}>
            <h2 className="h2">
              Have questions?
              <br />
              These come up first.
            </h2>
            <p className="lead">
              If something here contradicts the contract, the contract is right. Read it at
              contracts/Datum.py.
            </p>
          </div>
          <Faq />
        </div>
      </section>

      {/* ------------------------------------------------- final CTA */}
      <section className="band">
        <PixelMosaic rows={10} cols={92} cell={12} seed={73} height={120} />
        <div className="container" style={{ padding: "56px 0 72px" }}>
          <h2 className="h1" style={{ marginBottom: 28 }}>
            Observation. <Brk>settled.</Brk>
          </h2>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Link href="/app" className="btn">
              Open the board
            </Link>
            <Link href="/app/create" className="btn btn-ghost">
              Create an event
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </>
  );
}

/** Hairline schematic of the adjudication path. Decorative but accurate. */
function Schematic() {
  const box = (x: number, y: number, w: number, h: number, label: string, mono = true) => (
    <g key={`${label}-${x}-${y}`}>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill="none"
        stroke="var(--line-inv)"
        strokeWidth="1"
        rx="2"
      />
      <text
        x={x + w / 2}
        y={y + h / 2 + 4}
        textAnchor="middle"
        fill="var(--mute-inv)"
        fontSize="11"
        fontFamily={mono ? "var(--font-mono), monospace" : "inherit"}
      >
        {label}
      </text>
    </g>
  );

  const arrow = (x1: number, y1: number, x2: number, y2: number) => (
    <line
      key={`${x1}-${y1}-${x2}-${y2}`}
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke="var(--line-inv)"
      strokeWidth="1"
    />
  );

  return (
    <svg viewBox="0 0 980 190" width="100%" role="img" aria-label="Adjudication path">
      {box(0, 74, 150, 42, "constitution")}
      {arrow(150, 95, 200, 95)}

      {box(200, 28, 160, 42, "USGS_WATER")}
      {box(200, 120, 160, 42, "NOAA_NWPS")}
      {arrow(175, 95, 175, 49)}
      {arrow(175, 49, 200, 49)}
      {arrow(175, 95, 175, 141)}
      {arrow(175, 141, 200, 141)}

      {arrow(360, 49, 400, 49)}
      {arrow(360, 141, 400, 141)}
      {box(400, 28, 150, 42, "validate row")}
      {box(400, 120, 150, 42, "validate row")}

      {arrow(550, 49, 585, 49)}
      {arrow(550, 141, 585, 141)}
      {arrow(585, 49, 585, 141)}
      {arrow(585, 95, 620, 95)}
      {box(620, 74, 150, 42, "tolerance")}

      {arrow(770, 95, 810, 95)}
      <rect
        x={810}
        y={74}
        width={168}
        height={42}
        fill="none"
        stroke="var(--pixel)"
        strokeWidth="1"
        rx="2"
      />
      <text
        x={894}
        y={100}
        textAnchor="middle"
        fill="var(--pixel)"
        fontSize="11"
        fontFamily="var(--font-mono), monospace"
      >
        verdict + code
      </text>

      <text
        x={894}
        y={140}
        textAnchor="middle"
        fill="var(--mute-inv)"
        fontSize="10"
        fontFamily="var(--font-mono), monospace"
      >
        re-derived, not trusted
      </text>
    </svg>
  );
}

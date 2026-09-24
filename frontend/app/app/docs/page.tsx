import { PageHead, SectionLabel } from "@/src/components/ui";
import { ECONOMICS } from "@/src/lib/datum/registry";

export const metadata = { title: "Constitution · DATUM" };

const MUST_AGREE = [
  "station_id, character for character",
  "product_status (FINAL / PRELIMINARY)",
  "unit, before conversion",
  "converted value, within the locked tolerance",
  "timestamp falls inside the locked window",
  "usable / unusable, per publisher",
  "the derived verdict and code",
];

const MAY_DIFFER = [
  "raw response bytes and formatting",
  "key ordering in the JSON body",
  "volatile fields: generationtime_ms, requestId, requestDT, generated",
  "transport metadata and headers",
  "the order publishers were read in",
];

const WRITES = [
  ["create_event", "constitution_json, side, stake", "Post a constitution and one side. Costs stake + 0.05 GEN bond."],
  ["accept_event", "event_id, side", "Take the other side at a matching stake. Freezes the constitution hash."],
  ["adjudicate", "event_id", "After the window closes, read publishers and settle. Costs a 0.02 GEN bond."],
  ["finalize", "event_id", "Close out a pending verdict once its appeal window has elapsed."],
  ["appeal", "event_id, ground", "Challenge a pending verdict on one of five grounds."],
  ["re_adjudicate", "event_id", "Re-run adjudication for an appealed event."],
  ["lapse_appeal", "event_id", "After a 1h stall, restore the verdict that was appealed."],
  ["cancel_event", "event_id", "Creator only, and only before anyone has accepted."],
  ["expire_event", "event_id", "Slash the create bond of an event whose window opened unaccepted."],
  ["claim", "event_id", "The only path that moves GEN out of the contract."],
  ["recover_refund", "event_id", "After 7 days without a terminal state, return both stakes."],
  ["reclaim_bonds", "event_id", "Return adjudication and appeal bonds once settled."],
];

const VIEWS = [
  ["get_config", "Immutable economics and network facts."],
  ["get_registry", "Locked classes, station formats and publisher allowlists."],
  ["get_constitution", "The hashed constitution for one event."],
  ["get_event", "One event record."],
  ["get_board", "Paginated event board, optionally filtered by state."],
  ["get_record", "The accepted adjudication record: verdict, code, agreed value, sources."],
  ["get_position", "One address's side and stake on one event."],
  ["get_positions", "Paginated positions for an address."],
  ["get_claimable", "What the internal ledger currently owes an address."],
  ["get_activity", "Paginated events an address has taken part in."],
];

export default function DocsPage() {
  return (
    <>
      <PageHead
        title="The constitution"
        sub="What is frozen, what must agree, and what the contract refuses to do. If anything here contradicts contracts/Datum.py, the contract is right."
      />

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="01">FROZEN AT ACCEPT</SectionLabel>
        <div className="card card-p" style={{ marginTop: 16 }}>
          <p className="lead small" style={{ marginBottom: 16 }}>
            These fields are hashed into a sha256 commitment before a second address can take
            the other side. Every later read is checked against that hash, so the terms that
            were agreed to are the terms that settle.
          </p>
          <div className="grid-3">
            {[
              "class",
              "station_id or bbox",
              "metric",
              "threshold (scaled by 100)",
              "comparator",
              "window [start, end)",
              "publishers",
              "product status policy",
              "tolerance",
            ].map((f) => (
              <div key={f} className="mono small" style={{ padding: "6px 0" }}>
                · {f}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="02">EQUIVALENCE</SectionLabel>
        <div className="split" style={{ marginTop: 16 }}>
          <div className="card card-p">
            <div className="h3" style={{ marginBottom: 12 }}>
              Must agree
            </div>
            <p className="lead small" style={{ marginBottom: 14 }}>
              Validators compare the derived record, not the raw bytes. Any disagreement here
              rejects the whole envelope and moves no funds.
            </p>
            {MUST_AGREE.map((m) => (
              <div key={m} className="mono small" style={{ padding: "5px 0" }}>
                · {m}
              </div>
            ))}
          </div>
          <div className="card card-p">
            <div className="h3" style={{ marginBottom: 12 }}>
              May differ
            </div>
            <p className="lead small" style={{ marginBottom: 14 }}>
              Two validators reading the same instrument at different moments see different
              bytes. That is expected and is not a conflict.
            </p>
            {MAY_DIFFER.map((m) => (
              <div key={m} className="mono small muted" style={{ padding: "5px 0" }}>
                · {m}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="03">OUTCOME CODES</SectionLabel>
        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Verdict</th>
                <th>Meaning</th>
                <th>Money</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="mono">CLEAR</td>
                <td className="mono">YES / NO</td>
                <td>Publishers agreed within tolerance and the threshold was compared.</td>
                <td>Decisive. 2% fee on the pot.</td>
              </tr>
              <tr>
                <td className="mono">MISSING</td>
                <td className="mono">INCONCLUSIVE</td>
                <td>Fewer than two usable readings. A missing reading is never imputed as zero.</td>
                <td>Both stakes returned. No fee.</td>
              </tr>
              <tr>
                <td className="mono">CONFLICT</td>
                <td className="mono">INCONCLUSIVE</td>
                <td>Usable readings differed by more than the locked tolerance.</td>
                <td>Both stakes returned. No fee.</td>
              </tr>
              <tr>
                <td className="mono">PRELIMINARY_BLOCKED</td>
                <td className="mono">INCONCLUSIVE</td>
                <td>Readings existed but were PRELIMINARY under a FINAL_ONLY policy.</td>
                <td>Both stakes returned. No fee.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="04">APPEAL GROUNDS</SectionLabel>
        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <tbody>
              {[
                ["VALUE", "The converted value or the aggregation was wrong.", "Re-reads stored bytes"],
                ["STATION", "The record used a station the constitution did not name.", "Re-reads stored bytes"],
                ["WINDOW", "A reading was timestamped outside the locked window.", "Re-reads stored bytes"],
                ["STATUS", "Product status was misread against the locked policy.", "Re-reads stored bytes"],
                ["REVISED", "The publisher has since revised the observation.", "May refresh live"],
              ].map(([g, d, mode]) => (
                <tr key={g}>
                  <td className="mono" style={{ width: 130 }}>
                    {g}
                  </td>
                  <td>{d}</td>
                  <td className="mono muted" style={{ width: 200 }}>
                    {mode}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="lead small" style={{ marginTop: 12 }}>
          A REVISED appeal may refresh from the publisher, but it cannot blur the rows that were
          already stored — the original record stays readable.
        </p>
      </section>

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="05">ECONOMICS</SectionLabel>
        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <tbody>
              {ECONOMICS.map((e) => (
                <tr key={e.k}>
                  <td style={{ width: 220 }}>{e.k}</td>
                  <td className="mono" style={{ width: 160 }}>
                    {e.v}
                  </td>
                  <td className="muted">{e.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginBottom: 40 }}>
        <SectionLabel n="06">METHODS</SectionLabel>
        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Write</th>
                <th>Arguments</th>
                <th>Effect</th>
              </tr>
            </thead>
            <tbody>
              {WRITES.map(([m, a, d]) => (
                <tr key={m}>
                  <td className="mono">{m}</td>
                  <td className="mono muted">{a}</td>
                  <td>{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <thead>
              <tr>
                <th>View</th>
                <th>Returns</th>
              </tr>
            </thead>
            <tbody>
              {VIEWS.map(([m, d]) => (
                <tr key={m}>
                  <td className="mono">{m}</td>
                  <td>{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <SectionLabel n="07">NETWORK</SectionLabel>
        <div className="card table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <tbody>
              <tr>
                <td style={{ width: 200 }}>Network</td>
                <td className="mono">Studio Next (Studio Dev)</td>
              </tr>
              <tr>
                <td>Chain id</td>
                <td className="mono">61997</td>
              </tr>
              <tr>
                <td>RPC</td>
                <td className="mono">https://studio-dev.genlayer.com/api</td>
              </tr>
              <tr>
                <td>Explorer</td>
                <td className="mono">https://explorer-studio-dev.genlayer.com</td>
              </tr>
              <tr>
                <td>Currency</td>
                <td className="mono">GEN, 18 decimals</td>
              </tr>
              <tr>
                <td>State</td>
                <td>
                  Studio Next is a development preview and is periodically reset. When that
                  happens the contract address stops carrying code, and this app says so rather
                  than showing stale rows.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

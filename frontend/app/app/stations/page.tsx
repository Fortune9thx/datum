import { PageHead } from "@/src/components/ui";
import { CLASSES } from "@/src/lib/datum/registry";

export const metadata = { title: "Stations · DATUM" };

export default function StationsPage() {
  return (
    <>
      <PageHead
        title="Stations and publishers"
        sub="A station is an official identifier issued by the agency that runs the instrument. There are no nicknames here — “the airport gauge” is not a station, and a constitution naming one is refused at create."
      />

      <div className="card table-wrap" style={{ marginBottom: 24 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Id format</th>
              <th>Example</th>
              <th>Unit</th>
              <th>Min window</th>
              <th>Min lead</th>
              <th>Default tolerance</th>
            </tr>
          </thead>
          <tbody>
            {CLASSES.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id}</td>
                <td className="muted">{c.officialId}</td>
                <td className="mono">{c.idExample}</td>
                <td className="mono">{c.unit}</td>
                <td className="mono">{c.minWindowLabel}</td>
                <td className="mono">{c.minLeadLabel}</td>
                <td className="mono">{c.toleranceLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid-4">
        {CLASSES.map((c) => (
          <div key={c.id} className="card card-p">
            <div className="mono" style={{ fontSize: 12, marginBottom: 12 }}>
              {c.id}
            </div>
            <div className="label" style={{ marginBottom: 10 }}>
              <span>LOCKED PUBLISHERS</span>
            </div>
            {c.publishers.map((p) => (
              <div key={p.id} style={{ marginBottom: 10 }}>
                <div className="mono" style={{ fontSize: 12.5 }}>
                  {p.id}
                </div>
                <div className="mono muted" style={{ fontSize: 11 }}>
                  {p.host} · {p.kind}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="banner" style={{ marginTop: 24 }}>
        <span className="mono" style={{ fontSize: 11, letterSpacing: "0.08em" }}>
          LOCKED
        </span>
        <span>
          Publisher hosts are compiled into the contract. A creator cannot supply a source URL,
          and a host carrying a forecast or reanalysis marker is refused even when its family is
          otherwise allowlisted.
        </span>
      </div>
    </>
  );
}

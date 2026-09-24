import Link from "next/link";
import { CONTRACT_ADDRESS, checkLiveStatus } from "@/src/lib/datum/network";

export default async function HomePage() {
  const isLive = await checkLiveStatus();

  return (
    <div>
      <h1>DATUM</h1>
      <p>
        Did a named instrument at a named official station, over a locked window,
        clear a locked threshold?
      </p>
      <p>
        <em>Official station observation at locked publishers for this window.</em>
      </p>

      {!isLive && (
        <div className="banner">
          {CONTRACT_ADDRESS
            ? "Contract not deployed on Studio Next (61997)."
            : "Contract not deployed on Studio Next (61997). No address is configured yet."}
        </div>
      )}

      <h2>Constitution (V1 instrument classes)</h2>
      <table>
        <thead>
          <tr>
            <th>Class</th>
            <th>Official id</th>
            <th>Unit</th>
            <th>Min window</th>
            <th>Publishers</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>STATION_PRECIP</td>
            <td>NWS/ASOS/GHCN id</td>
            <td>mm</td>
            <td>6h</td>
            <td>2 locked precip hosts</td>
          </tr>
          <tr>
            <td>STATION_TEMP</td>
            <td>same family</td>
            <td>&deg;C</td>
            <td>24h</td>
            <td>2 locked temp hosts</td>
          </tr>
          <tr>
            <td>STAGE</td>
            <td>USGS 8-digit site number</td>
            <td>m</td>
            <td>6h</td>
            <td>USGS Water + NOAA NWPS</td>
          </tr>
          <tr>
            <td>QUAKES</td>
            <td>bbox (+ optional depth)</td>
            <td>Mw</td>
            <td>1h</td>
            <td>USGS catalog + EMSC</td>
          </tr>
        </tbody>
      </table>

      <p>
        <Link href="/board">View the board</Link>
      </p>
    </div>
  );
}

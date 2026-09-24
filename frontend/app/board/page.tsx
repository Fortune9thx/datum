import Link from "next/link";
import { getBoard } from "@/src/lib/datum/sdk";
import { checkLiveStatus } from "@/src/lib/datum/network";

export default async function BoardPage() {
  const isLive = await checkLiveStatus();
  const { rows } = await getBoard();

  return (
    <div>
      <h1>Board</h1>
      {!isLive && <div className="banner">Contract not deployed on Studio Next (61997).</div>}

      {isLive && rows.length === 0 && <p>No events yet.</p>}

      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Id</th>
              <th>Class</th>
              <th>State</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/e/${row.id}`}>{row.id}</Link>
                </td>
                <td>{row.class}</td>
                <td>{row.state}</td>
                <td>{row.verdict ?? "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

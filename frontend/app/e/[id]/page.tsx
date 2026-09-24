import { getEvent } from "@/src/lib/datum/sdk";
import { checkLiveStatus } from "@/src/lib/datum/network";
import { formatScaledValue, formatUnixWindow } from "@/src/lib/datum/format";

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const isLive = await checkLiveStatus();
  const event = isLive ? await getEvent(id) : null;

  return (
    <div>
      <h1>Event {id}</h1>
      {!isLive && <div className="banner">Contract not deployed on Studio Next (61997).</div>}
      {isLive && !event && <div className="banner">Event not found.</div>}

      {event && (
        <>
          <h2>Ticket</h2>
          <table>
            <tbody>
              <tr>
                <td>Class</td>
                <td>{event.class}</td>
              </tr>
              <tr>
                <td>Station / bbox</td>
                <td>{event.station_id ?? JSON.stringify(event.bbox)}</td>
              </tr>
              <tr>
                <td>Window</td>
                <td>{formatUnixWindow(event.window)}</td>
              </tr>
              <tr>
                <td>Threshold</td>
                <td>
                  {event.cmp} {formatScaledValue(event.threshold)}
                </td>
              </tr>
              <tr>
                <td>Publishers</td>
                <td>{event.publishers.join(", ")}</td>
              </tr>
              <tr>
                <td>State</td>
                <td>{event.state}</td>
              </tr>
              <tr>
                <td>Verdict</td>
                <td>{event.verdict ?? "--"}</td>
              </tr>
            </tbody>
          </table>

          <h2>Evidence pane</h2>
          <p>
            Constitution hash: <code>{event.constitution_hash}</code>
          </p>
          <p>Agreed value: {formatScaledValue(event.agreed_value)}</p>
        </>
      )}
    </div>
  );
}

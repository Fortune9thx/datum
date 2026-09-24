import Link from "next/link";
import { CONTRACT_ADDRESS, STUDIO_DEV_CHAIN_ID } from "@/src/lib/datum/network";
import { ConnectButton } from "./Wallet";
import { PixelMosaic } from "./PixelMosaic";

const ADDRESS_LABEL = CONTRACT_ADDRESS || "0x… not deployed";

export function MarketingNav() {
  return (
    <div className="container">
      <nav className="nav">
        <Link href="/" className="wordmark">
          DATUM
        </Link>
        <div className="nav-links">
          <Link href="/app">Board</Link>
          <Link href="/app/stations">Stations</Link>
          <Link href="/app/docs">Docs</Link>
          <ConnectButton />
        </div>
      </nav>
    </div>
  );
}

export function AppNav() {
  return (
    <div style={{ borderBottom: "1px solid var(--line)", background: "var(--surface)" }}>
      <div className="container">
        <nav className="nav">
          <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
            <Link href="/" className="wordmark">
              DATUM
            </Link>
            <div className="nav-links">
              <Link href="/app">Board</Link>
              <Link href="/app/portfolio">Portfolio</Link>
              <Link href="/app/activity">Activity</Link>
            </div>
          </div>
          <div className="nav-links">
            <span className="pill">Studio Next &middot; {STUDIO_DEV_CHAIN_ID}</span>
            <ConnectButton />
          </div>
        </nav>
      </div>
    </div>
  );
}

/** Small, honest health line. Same facts everywhere in the app. */
export function HealthFooter() {
  return (
    <footer style={{ borderTop: "1px solid var(--line)", padding: "20px 0" }}>
      <div className="container">
        <div className="mono muted" style={{ fontSize: 11.5, letterSpacing: "0.04em" }}>
          DATUM &middot; Studio Next &middot; chain {STUDIO_DEV_CHAIN_ID} &middot; state may reset
          &middot; {ADDRESS_LABEL}
        </div>
      </div>
    </footer>
  );
}

export function MarketingFooter() {
  return (
    <footer className="band">
      <div className="container" style={{ paddingTop: 72 }}>
        <div className="grid-4" style={{ paddingBottom: 56 }}>
          <div>
            <div className="label" style={{ marginBottom: 16 }}>
              <span>NETWORK</span>
            </div>
            <div className="small" style={{ color: "var(--mute-inv)" }}>
              Studio Next
              <br />
              chain {STUDIO_DEV_CHAIN_ID}
              <br />
              GEN, 18 decimals
            </div>
          </div>
          <div>
            <div className="label" style={{ marginBottom: 16 }}>
              <span>APP</span>
            </div>
            <div className="small stack-8" style={{ display: "grid" }}>
              <Link href="/app">Board</Link>
              <Link href="/app/create">Create</Link>
              <Link href="/app/stations">Stations</Link>
              <Link href="/app/portfolio">Portfolio</Link>
            </div>
          </div>
          <div>
            <div className="label" style={{ marginBottom: 16 }}>
              <span>READ</span>
            </div>
            <div className="small stack-8" style={{ display: "grid" }}>
              <Link href="/app/docs">Constitution</Link>
              <Link href="/app/activity">Activity</Link>
              <a
                href="https://explorer-studio-dev.genlayer.com"
                target="_blank"
                rel="noreferrer"
              >
                Explorer
              </a>
            </div>
          </div>
          <div>
            <div className="label" style={{ marginBottom: 16 }}>
              <span>STATE</span>
            </div>
            <div className="small" style={{ color: "var(--mute-inv)" }}>
              Studio Next is a development preview and is periodically reset. When it is,
              the contract address stops carrying code and this app says so.
            </div>
          </div>
        </div>

        <div className="rule" />

        <div style={{ padding: "28px 0 12px" }}>
          <div
            className="mono"
            style={{ fontSize: 11.5, letterSpacing: "0.04em", color: "var(--mute-inv)" }}
          >
            DATUM &middot; Studio Next &middot; chain {STUDIO_DEV_CHAIN_ID} &middot; state may
            reset &middot; {ADDRESS_LABEL}
          </div>
        </div>

        <h2 className="foot-mark">DATUM</h2>
      </div>
      <PixelMosaic rows={8} cols={96} cell={12} seed={41} height={96} flip />
    </footer>
  );
}

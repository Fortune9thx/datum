import type { ReactNode } from "react";

/** Bracketed headline token: [ station ] */
export function Brk({ children }: { children: ReactNode }) {
  return (
    <span className="brk">
      <span className="brk-b">[</span>
      <span className="brk-t">{children}</span>
      <span className="brk-b">]</span>
    </span>
  );
}

export function SectionLabel({ n, children }: { n: string; children: ReactNode }) {
  return (
    <div className="label">
      <span>[ {n} ]</span>
      <span className="label-dash" />
      <span>{children}</span>
    </div>
  );
}

/** App page header: title left, one action right. */
export function PageHead({
  title,
  sub,
  action,
}: {
  title: string;
  sub?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: 24,
        flexWrap: "wrap",
        marginBottom: 24,
      }}
    >
      <div>
        <h1 className="h2">{title}</h1>
        {sub ? (
          <p className="lead small" style={{ marginTop: 8, maxWidth: "62ch" }}>
            {sub}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Stat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="stat">
      <div className="stat-v mono">{value}</div>
      <div className="stat-k">{label}</div>
    </div>
  );
}

export function KV({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="kv">
      <span className="kv-k">{k}</span>
      <span className="kv-v">{v}</span>
    </div>
  );
}

export function Card({
  title,
  action,
  children,
  pad = true,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  pad?: boolean;
}) {
  return (
    <div className="card">
      {title ? (
        <div className="card-head">
          <div className="h3">{title}</div>
          {action}
        </div>
      ) : null}
      <div className={pad ? "card-p" : undefined}>{children}</div>
    </div>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <div className="h3">{title}</div>
      <p className="lead small" style={{ maxWidth: "46ch" }}>
        {body}
      </p>
    </div>
  );
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ padding: 20 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skel"
          style={{ marginBottom: 14, width: `${100 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  );
}

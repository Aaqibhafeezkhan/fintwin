import type { ReactNode } from "react";
import { healthStatus } from "./format";

export function StatusPill({ health }: { health: number }) {
  const s = healthStatus(health);
  return (
    <span className="pill" title={`Health score ${health.toFixed(0)} / 100`}>
      <span aria-hidden style={{ color: `var(--${s.key})`, fontSize: 10 }}>{s.icon}</span>
      {s.label}
    </span>
  );
}

export function Stat({ label, value, foot, hint }: { label: ReactNode; value: ReactNode; foot?: ReactNode; hint?: string }) {
  return (
    <div className="card stat" title={hint}>
      <div className="label">{label}</div>
      <div className="value num">{value}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}

export function Card({ title, sub, right, children }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <p>{sub}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/** Delta text in text tokens (never the series color); sign carried by arrow + word. */
export function Delta({ value, fmt, goodIfPositive = true }: { value: number; fmt: (x: number) => string; goodIfPositive?: boolean }) {
  if (!Number.isFinite(value) || Math.abs(value) < 1e-9) return <span className="muted">no change vs baseline</span>;
  const good = value > 0 === goodIfPositive;
  return (
    <span style={{ color: good ? "var(--good-text)" : "var(--bad-text)" }}>
      {value > 0 ? "▲" : "▼"} {fmt(Math.abs(value))} vs baseline
    </span>
  );
}

export function HealthBar({ value }: { value: number }) {
  const s = healthStatus(value);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--grid)", minWidth: 40 }}>
        <div style={{ width: `${Math.max(2, value)}%`, height: 6, borderRadius: 3, background: `var(--${s.key})` }} />
      </div>
      <span className="num" style={{ width: 24, textAlign: "right" }}>{value.toFixed(0)}</span>
    </div>
  );
}

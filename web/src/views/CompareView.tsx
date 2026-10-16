import { useMemo, useState } from "react";
import type { Index } from "../data";
import { pct } from "../format";

/** Diverging fill around a health score of 50: red (distressed) ← gray → blue (healthy). */
function cellColor(h: number) {
  const t = Math.max(-1, Math.min(1, (h - 50) / 50));
  const pole = t < 0 ? "var(--div-lo)" : "var(--div-hi)";
  return `color-mix(in oklab, ${pole} ${Math.round(Math.abs(t) * 85)}%, var(--div-mid))`;
}

export function CompareView({ index, onOpen }: { index: Index; onOpen: (t: string) => void }) {
  const presets = Object.entries(index.meta.presets);
  const [sortKey, setSortKey] = useState("base");
  const [metric, setMetric] = useState<"health" | "p_breach">("health");
  const rows = useMemo(() => Object.entries(index.companies).sort((a, b) =>
    sortKey === "name" ? a[0].localeCompare(b[0]) : a[1].matrix[sortKey].health - b[1].matrix[sortKey].health), [index, sortKey]);

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3>Stress matrix — {rows.length} companies × {presets.length} scenarios</h3>
          <p>Each cell is a full Monte Carlo run (5,000 paths, 12 quarters) on that company's own calibrated twin. Click a column to sort, a row to open the company.</p>
        </div>
        <div className="chips">
          <button className="chip" aria-pressed={metric === "health"} onClick={() => setMetric("health")}>Health score</button>
          <button className="chip" aria-pressed={metric === "p_breach"} onClick={() => setMetric("p_breach")}>Breach probability</button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ cursor: "pointer" }} onClick={() => setSortKey("name")}>Company {sortKey === "name" ? "↓" : ""}</th>
              {presets.map(([k, v]) => (
                <th key={k} className="r" style={{ cursor: "pointer", minWidth: 78 }} onClick={() => setSortKey(k)} title={v.desc}>
                  {v.label} {sortKey === k ? "↑" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([t, e]) => (
              <tr key={t} className="clickable" onClick={() => onOpen(t)}>
                <td><b>{t}</b> <span className="muted">{e.sector}</span></td>
                {presets.map(([k]) => {
                  const m = e.matrix[k];
                  const shown = metric === "health" ? m.health.toFixed(0) : pct(m.p_breach);
                  const bg = metric === "health" ? cellColor(m.health) : cellColor(100 - m.p_breach * 100);
                  return (
                    <td key={k} className="r num" style={{ background: bg, borderBottom: "2px solid var(--surface)", borderRight: "2px solid var(--surface)" }}
                      title={`${t} · ${index.meta.presets[k].label}: health ${m.health.toFixed(0)}, P(breach) ${pct(m.p_breach, 1)}`}>
                      {shown}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="legend">
        <span><span className="sw" style={{ background: cellColor(5) }} />Distressed</span>
        <span><span className="sw" style={{ background: cellColor(50) }} />Middling (50)</span>
        <span><span className="sw" style={{ background: cellColor(95) }} />Healthy</span>
      </div>
    </section>
  );
}

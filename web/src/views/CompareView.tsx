import { useMemo, useState } from "react";
import type { Index } from "../data";
import { pct } from "../format";
import { Section } from "../ui";

type Metric = "health" | "p_breach";
type Mode = "level" | "change";

/** Quiet diverging tint around a neutral midpoint; the number in the cell carries the value. */
function tint(t: number) {
  const c = Math.max(-1, Math.min(1, t));
  const pole = c < 0 ? "var(--div-lo)" : "var(--div-hi)";
  return `color-mix(in oklab, ${pole} ${Math.round(Math.abs(c) * 46)}%, transparent)`;
}

export function CompareView({ index, onOpen }: { index: Index; onOpen: (t: string) => void }) {
  const presets = Object.entries(index.meta.presets);
  const [sortKey, setSortKey] = useState("pandemic");
  const [desc, setDesc] = useState(false);
  const [metric, setMetric] = useState<Metric>("health");
  const [mode, setMode] = useState<Mode>("level");
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("all");
  const sectors = useMemo(() => [...new Set(Object.values(index.companies).map((e) => e.sector))].filter(Boolean).sort(), [index]);

  const value = (t: string, k: string) => {
    const m = index.companies[t].matrix;
    const v = metric === "health" ? m[k].health : m[k].p_breach * 100;
    const b = metric === "health" ? m.base.health : m.base.p_breach * 100;
    return mode === "change" && k !== "base" ? v - b : v;
  };
  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    return Object.entries(index.companies)
      .filter(([t, e]) => (sector === "all" || e.sector === sector) && (!s || t.toLowerCase().includes(s) || e.name.toLowerCase().includes(s)))
      .sort((a, b) => {
        const d = sortKey === "name" ? a[0].localeCompare(b[0]) : value(a[0], sortKey) - value(b[0], sortKey);
        return desc ? -d : d;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, sortKey, desc, q, sector, metric, mode]);

  const sortBy = (k: string) => { if (k === sortKey) setDesc(!desc); else { setSortKey(k); setDesc(false); } };
  const cell = (t: string, k: string) => {
    const v = value(t, k);
    const isChange = mode === "change" && k !== "base";
    let bg: string, text: string;
    if (metric === "health") {
      bg = isChange ? tint(v / 50) : tint((v - 50) / 50);
      text = isChange ? (Math.round(v) === 0 ? "0" : `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(0)}`) : v.toFixed(0);
    } else {
      bg = isChange ? tint(-v / 50) : tint(-(v - 10) / 50);
      text = isChange ? (Math.abs(v) < 0.5 ? "0" : `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(0)}`) : `${v.toFixed(0)}%`;
    }
    return { bg, text };
  };

  return (
    <div className="fade-in">
      <Section>
        <div className="eyebrow">Matrix</div>
        <h1 className="display h-l" style={{ margin: "8px 0 10px" }}>{Object.keys(index.companies).length} companies, eight crises</h1>
        <p className="lede">Every cell is a full Monte Carlo run of 5,000 paths over 12 quarters on that company's own calibrated twin.
          Sort by any scenario to see who is most exposed to it.</p>
      </Section>

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", margin: "-6px 0 16px" }}>
        <input type="search" placeholder="Filter by ticker or name" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter companies" style={{ width: 220 }} />
        <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector">
          <option value="all">All sectors</option>
          {sectors.map((s) => <option key={s}>{s}</option>)}
        </select>
        <div className="segmented" role="group" aria-label="Metric">
          <button aria-pressed={metric === "health"} onClick={() => setMetric("health")}>Health score</button>
          <button aria-pressed={metric === "p_breach"} onClick={() => setMetric("p_breach")}>Runs out of cash</button>
        </div>
        <div className="segmented" role="group" aria-label="Values">
          <button aria-pressed={mode === "level"} onClick={() => setMode("level")}>Level</button>
          <button aria-pressed={mode === "change"} onClick={() => setMode("change")}>Change vs baseline</button>
        </div>
        <span className="muted" style={{ marginLeft: "auto" }}>{rows.length} shown</span>
      </div>

      <div className="table-wrap" style={{ maxHeight: "72vh", overflowY: "auto", border: "1px solid var(--rule)", borderRadius: 10, background: "var(--paper)" }}>
        <table style={{ borderCollapse: "separate", borderSpacing: 0 }}>
          <thead>
            <tr>
              <th onClick={() => sortBy("name")} style={{ cursor: "pointer", position: "sticky", top: 0, left: 0, zIndex: 3, background: "var(--paper)", paddingLeft: 14, minWidth: 220 }}>
                Company {sortKey === "name" ? (desc ? "↓" : "↑") : ""}
              </th>
              {presets.map(([k, v]) => (
                <th key={k} className="r" onClick={() => sortBy(k)} title={v.desc}
                  style={{ cursor: "pointer", position: "sticky", top: 0, zIndex: 2, background: "var(--paper)", minWidth: 92, color: sortKey === k ? "var(--ink)" : undefined }}>
                  {v.label} {sortKey === k ? (desc ? "↓" : "↑") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([t, e]) => (
              <tr key={t} className="clickable" onClick={() => onOpen(t)}>
                <td style={{ position: "sticky", left: 0, background: "var(--paper)", zIndex: 1, paddingLeft: 14, whiteSpace: "nowrap" }}>
                  <span className="tk-cell" style={{ display: "inline-block", width: 52 }}>{t}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{e.sector}</span>
                </td>
                {presets.map(([k]) => {
                  const { bg, text } = cell(t, k);
                  return (
                    <td key={k} className="r num" style={{ background: bg, borderBottom: "1px solid var(--paper)", borderLeft: "1px solid var(--paper)", padding: "7px 12px" }}
                      title={`${t} · ${index.meta.presets[k].label}: health ${e.matrix[k].health.toFixed(0)}, runs out of cash ${pct(e.matrix[k].p_breach, 1)}`}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="legend" style={{ marginTop: 12 }}>
        <span><span className="sw" style={{ background: tint(-1) }} />{metric === "health" ? "weaker" : "more likely to run out of cash"}</span>
        <span><span className="sw" style={{ background: "var(--wash)" }} />neutral</span>
        <span><span className="sw" style={{ background: tint(1) }} />{metric === "health" ? "stronger" : "safer"}</span>
        <span className="muted" style={{ marginLeft: "auto" }}>Leverage thresholds are not sector-adjusted, so regulated utilities read weaker than a credit analyst would rate them.</span>
      </div>
    </div>
  );
}

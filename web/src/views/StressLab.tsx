import { useMemo, useState } from "react";
import { Columns, ProbLine, Tornado } from "../charts/Bars";
import { FanChart } from "../charts/FanChart";
import type { Company, Meta } from "../data";
import { INVESTMENT_GRADE_MIN_RANK, RATINGS } from "../engine/ratings";
import { KNOB_DEFAULTS } from "../engine/scenario";
import type { Knobs, Levers } from "../engine/types";
import { fixed, futureQuarters, money, moneyTick, pct } from "../format";
import { useSimulation } from "../hooks";
import { Card, Delta, Stat, StatusPill } from "../ui";

type KnobKey = keyof Required<Knobs>;
const SLIDERS: { key: KnobKey; label: string; min: number; max: number; step: number; fmt: (v: number) => string }[] = [
  { key: "sales_depth", label: "Revenue shock", min: 0, max: 0.95, step: 0.01, fmt: (v) => (v ? `−${Math.round(v * 100)}%` : "none") },
  { key: "sales_duration", label: "…quarters at trough", min: 1, max: 8, step: 1, fmt: (v) => `${v}q` },
  { key: "sales_recovery", label: "…quarters to recover", min: 1, max: 12, step: 1, fmt: (v) => `${v}q` },
  { key: "rate_bp", label: "Interest rates", min: -300, max: 600, step: 25, fmt: (v) => `${v > 0 ? "+" : ""}${v}bp` },
  { key: "spread_bp", label: "Credit spreads", min: 0, max: 1000, step: 25, fmt: (v) => `+${v}bp` },
  { key: "cost_pp", label: "Variable costs", min: 0, max: 15, step: 0.5, fmt: (v) => `+${v}pp` },
  { key: "dio_days", label: "Inventory build-up", min: 0, max: 120, step: 5, fmt: (v) => `+${v} days` },
  { key: "refi_freeze", label: "Debt markets closed", min: 0, max: 8, step: 1, fmt: (v) => (v ? `${v}q` : "open") },
];
const LEVERS: { key: keyof Levers; label: string; desc: string }[] = [
  { key: "cut_payouts", label: "Suspend dividends & buybacks", desc: "when cash or coverage is stressed" },
  { key: "cut_capex", label: "Cut capex to maintenance", desc: "when stressed" },
  { key: "cut_costs", label: "Fixed-cost restructuring", desc: "after 2 quarters of margin squeeze" },
  { key: "issue_debt", label: "Raise new debt", desc: "if markets are open to this credit" },
  { key: "draw_revolver", label: "Draw the revolver", desc: "committed bank facility" },
  { key: "issue_equity", label: "Emergency equity raise", desc: "dilutive last resort" },
];

export function StressLab({ c, meta, preset, setPreset }: { c: Company; meta: Meta; preset: string; setPreset: (p: string) => void }) {
  const [knobs, setKnobs] = useState<Knobs>(() => ({ ...meta.presets[preset]?.knobs }));
  const [levers, setLevers] = useState<Levers>(meta.levers);
  const [nPaths, setNPaths] = useState(5000);
  const [showPaths, setShowPaths] = useState(false);
  const stress = useSimulation(c.params, knobs, levers, nPaths);
  const base = useSimulation(c.params, useMemo(() => ({}), []), levers, nPaths);
  const T = c.params.horizon;
  const fut = futureQuarters(c.params.last_quarter, T);
  const k = { ...KNOB_DEFAULTS, ...knobs };
  const isBase = Object.entries(k).every(([kk, v]) => v === KNOB_DEFAULTS[kk as KnobKey]);

  const choose = (key: string) => {
    setPreset(key);
    setKnobs({ ...meta.presets[key].knobs });
  };
  const s = stress.summary, b = base.summary;

  return (
    <div className="lab">
      <aside className="card" style={{ position: "sticky", top: 12 }}>
        <h3>Scenario</h3>
        <div className="chips" style={{ margin: "10px 0 6px" }}>
          {Object.entries(meta.presets).map(([key, v]) => (
            <button key={key} className="chip" aria-pressed={preset === key} onClick={() => choose(key)} title={v.desc}>{v.label}</button>
          ))}
        </div>
        <p className="muted" style={{ minHeight: 32 }}>{meta.presets[preset]?.desc ?? "Custom scenario"}</p>
        {SLIDERS.map((sl) => (
          <label className="slider" key={sl.key}>
            <span className="slider-top"><span>{sl.label}</span><span>{sl.fmt(k[sl.key])}</span></span>
            <input type="range" min={sl.min} max={sl.max} step={sl.step} value={k[sl.key]}
              onChange={(e) => { setPreset("custom"); setKnobs({ ...k, [sl.key]: +e.target.value }); }} />
          </label>
        ))}
        <h3 style={{ marginTop: 18 }}>Management response</h3>
        <p className="muted" style={{ marginBottom: 4 }}>What the CFO is allowed to do</p>
        {LEVERS.map((l) => (
          <label className="toggle" key={l.key} title={l.desc}>
            <span>{l.label}<div className="muted">{l.desc}</div></span>
            <input type="checkbox" checked={levers[l.key]} onChange={(e) => setLevers({ ...levers, [l.key]: e.target.checked })} />
          </label>
        ))}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12, gap: 8 }}>
          <label className="muted">Paths{" "}
            <select value={nPaths} onChange={(e) => setNPaths(+e.target.value)}>
              {[1000, 5000, 10000, 20000].map((n) => <option key={n} value={n}>{n.toLocaleString()}</option>)}
            </select>
          </label>
          <span className="badge-busy num">{stress.busy ? "simulating…" : `${stress.ms.toFixed(0)} ms in-browser`}</span>
        </div>
      </aside>

      <div className="grid" style={{ gap: 16 }}>
        {!s || !b ? <div className="card loading">Running Monte Carlo…</div> : (
          <>
            <div className="grid g4">
              <Stat label={<>Health score <StatusPill health={s.healthScore} /></>} value={s.healthScore.toFixed(0)}
                foot={isBase ? `P10 ${s.healthP10.toFixed(0)}` : <Delta value={s.healthScore - b.healthScore} fmt={(x) => x.toFixed(0)} />} />
              <Stat label="Liquidity breach probability" value={pct(s.pBreach, s.pBreach < 0.1 ? 1 : 0)}
                foot={isBase ? "within 3 years" : <Delta value={s.pBreach - b.pBreach} fmt={(x) => pct(x, 1)} goodIfPositive={false} />} />
              <Stat label="Falls below investment grade" value={pct(s.pSubIG)}
                foot={s.medianQuartersToBreach != null ? `median breach in quarter ${s.medianQuartersToBreach + 1}` : "rating at horizon"} />
              <Stat label="New debt raised (median)" value={money(s.debtIssuedMedian)}
                foot={levers.issue_equity ? `equity raised ${money(s.equityNeededMedian)}` : "to defend the cash buffer"} />
            </div>

            <div className="grid g2">
              <Card title="Cash" sub="After all management responses; below zero = liquidity breach"
                right={<button className="btn" onClick={() => setShowPaths(!showPaths)}>{showPaths ? "Hide" : "Show"} sample paths</button>}>
                <FanChart futureLabels={fut} history={[c.params.cash0]} histLabels={["Now"]}
                  layers={[...(isBase ? [] : [{ label: "Baseline", color: "var(--s1)", bands: b.bands.cash }]),
                    { label: isBase ? "Baseline" : "Stress", color: isBase ? "var(--s1)" : "var(--s2)", bands: s.bands.cash }]}
                  samplePaths={showPaths ? s.samplePaths.cash : undefined}
                  refLine={{ y: 0, label: "breach" }} format={(x) => money(x)} tick={moneyTick} />
              </Card>
              <Card title="Health score" sub="0–100 composite: liquidity, coverage, leverage, Altman Z''">
                <FanChart futureLabels={fut}
                  layers={[...(isBase ? [] : [{ label: "Baseline", color: "var(--s1)", bands: b.bands.health }]),
                    { label: isBase ? "Baseline" : "Stress", color: isBase ? "var(--s1)" : "var(--s2)", bands: s.bands.health }]}
                  samplePaths={showPaths ? s.samplePaths.health : undefined}
                  yMin={0} yMax={100} format={(x) => x.toFixed(0)} tick={(x) => `${x}`} />
              </Card>
              <Card title="Revenue" sub="Quarterly">
                <FanChart futureLabels={fut}
                  layers={[...(isBase ? [] : [{ label: "Baseline", color: "var(--s1)", bands: b.bands.revenue }]),
                    { label: isBase ? "Baseline" : "Stress", color: isBase ? "var(--s1)" : "var(--s2)", bands: s.bands.revenue }]}
                  format={(x) => money(x)} tick={moneyTick} />
              </Card>
              <Card title="Interest coverage (EBIT / interest, TTM)" sub="Drives the synthetic rating and the cost of new debt">
                <FanChart futureLabels={fut}
                  layers={[...(isBase ? [] : [{ label: "Baseline", color: "var(--s1)", bands: b.bands.icr.map((r) => r.map((v) => Math.max(Math.min(v, 30), -10))) }]),
                    { label: isBase ? "Baseline" : "Stress", color: isBase ? "var(--s1)" : "var(--s2)", bands: s.bands.icr.map((r) => r.map((v) => Math.max(Math.min(v, 30), -10))) }]}
                  refLine={{ y: 1.5, label: "1.5× junk threshold" }} format={(x) => `${fixed(x, 1)}×`} tick={(x) => `${x}×`} />
              </Card>
            </div>

            <div className="grid g2">
              <Card title="Cumulative probability of a liquidity breach" sub="Share of paths that have run out of cash by each quarter">
                <ProbLine labels={fut} values={s.pBreachByQ} />
              </Card>
              <Card title="Synthetic credit rating at horizon" sub="Damodaran coverage → rating map">
                <Columns labels={RATINGS} values={s.ratingDist} format={(x) => pct(x)}
                  highlight={(i) => (i >= INVESTMENT_GRADE_MIN_RANK ? "var(--s1)" : "var(--s2)")} />
                <div className="legend">
                  <span><span className="sw" style={{ background: "var(--s1)" }} />Investment grade (BBB and above)</span>
                  <span><span className="sw" style={{ background: "var(--s2)" }} />Speculative grade</span>
                </div>
              </Card>
            </div>
          </>
        )}

        <div className="grid g2">
          <Card title="Reverse stress test" sub="How large must a shock be to break this company? (50% breach probability)">
            <div className="grid" style={{ gap: 10 }}>
              {Object.entries(c.reverse_stress).map(([key, r]) => {
                const f = (v: number | null) => v == null ? "not reached" : r.unit === "pct" ? `−${pct(v)}` : r.unit === "bp" ? `+${v.toFixed(0)}bp` : `+${v.toFixed(1)}pp`;
                return (
                  <div key={key} style={{ display: "flex", justifyContent: "space-between", gap: 12, borderBottom: "1px solid var(--grid)", paddingBottom: 8 }}>
                    <div>{r.label}<div className="muted">10% breach chance at {f(r.p10)}</div></div>
                    <div className="num" style={{ fontSize: 20, fontWeight: 600, whiteSpace: "nowrap" }}>{r.p50 == null ? "survives" : f(r.p50)}</div>
                  </div>
                );
              })}
              <p className="muted">Solved by bisection with common random numbers. A breach means cash is exhausted after every funding source; "survives" means the company can still fund itself, often by borrowing at junk spreads, so check the rating outcome.</p>
            </div>
          </Card>
          <Card title="What hurts most" sub="Change in health score from each shock on its own, vs baseline">
            <Tornado rows={c.tornado.map((t) => ({ label: t.label, value: t.d_health, detail: `P(breach) ${t.d_p_breach >= 0 ? "+" : ""}${pct(t.d_p_breach, 1)}` }))}
              format={(x) => (x > 0 ? "+" : "") + x.toFixed(1)} />
          </Card>
        </div>
      </div>
    </div>
  );
}

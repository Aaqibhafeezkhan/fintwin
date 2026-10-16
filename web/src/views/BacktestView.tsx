import { useEffect, useState } from "react";
import { Columns } from "../charts/Bars";
import { FanChart } from "../charts/FanChart";
import { Scatter } from "../charts/Scatter";
import { loadBacktest, loadCalibration, type Backtest, type Calibration } from "../data";
import { fixed, money, moneyTick, pct, quarterLabel } from "../format";
import { Card, Stat } from "../ui";

const VARS: Record<string, string> = { revenue: "Revenue", cash_like: "Cash & ST investments", total_debt: "Total debt" };

export function BacktestView({ onOpen }: { onOpen: (t: string) => void }) {
  const [bt, setBt] = useState<Backtest | null>(null);
  const [cal, setCal] = useState<Calibration | null>(null);
  useEffect(() => { loadCalibration().then(setCal); }, []);
  const [err, setErr] = useState<string | null>(null);
  const [ticker, setTicker] = useState("CCL");
  const [cut, setCut] = useState("pre_covid");
  const [v, setV] = useState("revenue");
  useEffect(() => { loadBacktest().then(setBt).catch((e) => setErr(String(e))); }, []);
  if (err) return <div className="card loading">{err}</div>;
  if (!bt) return <div className="card loading">Loading backtests…</div>;

  const xs = cal ? { rows: cal.cross_section.rows, failed: {} as Record<string, string> } : bt.cross_section;
  const key = "health_stress__realized_min_cum_fcf_pct_rev";
  const st = cal ? { spearman: cal.cross_section.spearman, p_value: cal.cross_section.p_value, n: cal.cross_section.n } : bt.cross_section.stats[key];
  const pts = xs.rows.filter((r) => r.realized_min_cum_fcf_pct_rev != null && Number.isFinite(r.health_stress)).map((r) => ({
    id: r.ticker, x: r.health_stress, y: r.realized_min_cum_fcf_pct_rev as number, label: r.ticker,
    detail: `${r.name} · debt raised ${fixed(r.realized_debt_raise_pct_rev, 0)}% of revenue`,
  }));
  const tickers = [...new Set(Object.values(bt.forecast).map((f) => f.ticker))];
  const fb = bt.forecast[`${ticker}:${cut}`];
  const series = fb?.series[v];
  const sc = fb?.scores[v];
  const structural = fb && "dates" in fb.structural ? fb.structural : null;
  const agg = bt.aggregate;

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="callout">
        <b>Out-of-sample, point-in-time.</b> Each twin below is calibrated using only XBRL facts <i>filed</i> before the cutoff
        date (later restatements are invisible to it), then compared with what the companies actually reported afterwards.
        Nothing in these results was tuned on the outcomes.
      </div>

      <div className="grid g4">
        <Stat label="Pre-COVID vulnerability ranking" value={`ρ = ${fixed(st?.spearman, 2)}`}
          foot={`Spearman, n=${st?.n}, p=${st && st.p_value < 0.001 ? "<0.001" : fixed(st?.p_value, 3)}${cal ? ` · 95% CI ${fixed(cal.cross_section.ci95[0], 2)}–${fixed(cal.cross_section.ci95[1], 2)}` : ""}`}
          hint="Rank correlation between the twin's pre-COVID health score under the demand-freeze scenario and each company's realized worst cumulative free cash flow in 2020–21" />
        {cal ? (
          <>
            <Stat label="Out-of-sample forecasts" value={cal.n_forecasts.toLocaleString()}
              foot={`${cal.n_companies} companies · point-in-time cutoffs ${cal.origins[0].slice(0, 4)}–${cal.origins[cal.origins.length - 1].slice(0, 4)}`} />
            <Stat label="Revenue CRPS skill vs naive" value={pct(cal.vars.revenue.crps_skill_vs_naive)}
              foot={`twin wins in ${pct(cal.vars.revenue.share_cases_beating_naive)} of forecasts`} />
            <Stat label="90% coverage, raw → conformal" value={`${pct(cal.vars.revenue.raw.coverage90)} → ${pct(cal.vars.revenue.conformal.coverage90)}`}
              foot="revenue · conformal scale learned only from earlier years" />
          </>
        ) : (
          <>
            <Stat label="Revenue forecasts beating naive baseline" value={pct(agg.revenue?.share_beating_baseline)}
              foot={`median CRPS skill ${pct(agg.revenue?.median_crps_skill)} · ${agg.revenue?.cases} cases`} />
            <Stat label="Cash forecasts beating naive baseline" value={pct(agg.cash_like?.share_beating_baseline)}
              foot={`median CRPS skill ${pct(agg.cash_like?.median_crps_skill)}`} />
            <Stat label="90% interval coverage (revenue)" value={pct(agg.revenue?.coverage90)}
              foot="target 90% · lower = overconfident (two regime breaks)" />
          </>
        )}
      </div>

      <Card title={`Did the twin know who would bleed? — ${pts.length} companies, calibrated on pre-COVID filings`}
        sub="x: health score under the 'Demand freeze' scenario, computed in Feb 2020 · y: realized worst cumulative free cash flow, Q1 2020 – Q2 2021, % of pre-COVID revenue">
        <Scatter points={pts} xLabel="Twin's stress health score (Feb 2020)" yLabel="Realized worst cum. FCF, % of revenue"
          xFmt={(x) => x.toFixed(0)} yFmt={(y) => `${y.toFixed(0)}%`} labelIds={["CCL", "RCL", "NCLH", "BA", "AAL", "MSFT", "GOOGL", "WMT", "LVS", "EXPE"]}
          onClick={onOpen} />
        <p className="muted" style={{ marginTop: 8 }}>
          Every company gets the same generic shock, so this measures structural fragility, not who the pandemic actually hit.
          Walmart is the visible miss: fragile to a demand collapse it never suffered. {Object.keys(xs.failed).length > 0 && `Excluded (data): ${Object.keys(xs.failed).join(", ")}.`}
        </p>
      </Card>

      {cal && <CalibrationSection cal={cal} />}

      <Card title="Forecast vs reality" sub="Baseline fan (blue), the cutoff's stress scenario (orange) and what was actually reported (dots)"
        right={
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select value={ticker} onChange={(e) => setTicker(e.target.value)} aria-label="Company">
              {tickers.map((t) => <option key={t}>{t}</option>)}
            </select>
            <select value={cut} onChange={(e) => setCut(e.target.value)} aria-label="Cutoff">
              {Object.entries(bt.cutoffs).map(([k, c]) => <option key={k} value={k}>{c.label}</option>)}
            </select>
            <select value={v} onChange={(e) => setV(e.target.value)} aria-label="Variable">
              {Object.entries(VARS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </div>
        }>
        {series && sc ? (
          <>
            <FanChart histLabels={series.history.dates.map(quarterLabel)} history={series.history.values}
              futureLabels={series.realized.dates.map(quarterLabel)}
              layers={[{ label: "Baseline", color: "var(--s1)", bands: series.base_bands.map((r) => r.slice(0, series.realized.dates.length)) },
                { label: `Stress (${bt.cutoffs[cut].stress})`, color: "var(--s2)", bands: series.stress_bands.map((r) => r.slice(0, series.realized.dates.length)) }]}
              realized={series.realized.values} realizedLabel="Actually reported" format={(x) => money(x)} tick={moneyTick} height={280} />
            <div className="grid g4" style={{ marginTop: 12 }}>
              <div><div className="muted">Inside 50% band</div><b className="num">{pct(sc.coverage50)}</b></div>
              <div><div className="muted">Inside 90% band</div><b className="num">{pct(sc.coverage90)}</b></div>
              <div><div className="muted">Inside stress 90% band</div><b className="num">{pct(sc.stress_coverage90)}</b></div>
              <div><div className="muted">CRPS skill vs naive</div><b className="num" style={{ color: sc.crps_skill > 0 ? "var(--good-text)" : "var(--bad-text)" }}>{sc.crps_skill > 0 ? "▲ " : "▼ "}{pct(sc.crps_skill)}</b></div>
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              Pre-shock view: baseline health {fb.pre_shock.base.health_score.toFixed(0)}, stress health {fb.pre_shock.stress.health_score.toFixed(0)},
              P(breach | stress) {pct(fb.pre_shock.stress.p_breach)}. Last quarter visible to the twin: {fb.last_quarter_known}.
            </p>
          </>
        ) : <p className="muted">No realized data for this case.</p>}
      </Card>

      {structural && (
        <Card title="Structural test: given the realized revenue, does the machine burn cash like the real company?"
          sub="The twin is fed the actual revenue path; only its internal mechanics (costs, working capital, capex, financing) produce the cash flow">
          <FanChart futureLabels={structural.dates.map(quarterLabel)}
            layers={[{ label: "Twin, cumulative FCF", color: "var(--s1)", bands: structural.model_cum_fcf_bands }]}
            realized={structural.actual_cum_fcf} realizedLabel="Actual cumulative FCF" format={(x) => money(x)} tick={moneyTick} height={240} />
          <p className="muted" style={{ marginTop: 8 }}>
            End-of-window error {fixed(structural.final_error_pct, 0)}% · quarter-to-quarter correlation {fixed(structural.corr, 2)}.
          </p>
        </Card>
      )}

      <Card title="Honest limitations">
        <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }} className="sub">
          <li>Unconditional fans cannot foresee regime breaks: CCL's 2020 revenue fell ~99%, beyond even the twin's −70% stress preset.</li>
          <li>Balance-sheet forecasts are weaker than revenue forecasts — opportunistic financing and M&amp;A are discretionary and only modelled as calibrated noise.</li>
          <li>Generic XBRL tags miss industry specifics (Netflix content spend, Boeing customer advances, Walmart's pandemic demand boost).</li>
          <li>Interval coverage is below nominal across two crisis cutoffs: the fans are useful for ranking and stress, not as calibrated point forecasts.</li>
        </ul>
      </Card>
    </div>
  );
}

function CalibrationSection({ cal }: { cal: Calibration }) {
  const [v, setV] = useState<"revenue" | "cash_like">("revenue");
  const c = cal.vars[v];
  const years = Object.keys(c.by_year).sort();
  return (
    <Card title={`Large-sample calibration — ${cal.n_forecasts.toLocaleString()} out-of-sample forecasts`}
      sub={`${cal.n_companies} companies × yearly point-in-time cutoffs ${cal.origins[0].slice(0, 4)}–${cal.origins[cal.origins.length - 1].slice(0, 4)}, ${cal.horizon}-quarter horizon`}
      right={
        <div className="chips">
          <button className="chip" aria-pressed={v === "revenue"} onClick={() => setV("revenue")}>Revenue</button>
          <button className="chip" aria-pressed={v === "cash_like"} onClick={() => setV("cash_like")}>Cash</button>
        </div>
      }>
      <div className="grid g4">
        <div><div className="muted">90% band coverage, raw → conformal</div><div className="num" style={{ fontSize: 22, fontWeight: 600 }}>{pct(c.raw.coverage90)} → {pct(c.conformal.coverage90)}</div><div className="muted">target 90%</div></div>
        <div><div className="muted">50% band coverage, raw → conformal</div><div className="num" style={{ fontSize: 22, fontWeight: 600 }}>{pct(c.raw.coverage50)} → {pct(c.conformal.coverage50)}</div><div className="muted">target 50%</div></div>
        <div><div className="muted">CRPS skill vs naive baseline</div><div className="num" style={{ fontSize: 22, fontWeight: 600 }}>{pct(c.crps_skill_vs_naive)}</div><div className="muted">twin beats naive in {pct(c.share_cases_beating_naive)} of forecasts</div></div>
        <div><div className="muted">Recession regime ablation</div><div className="num" style={{ fontSize: 22, fontWeight: 600 }}>{c.regime_ablation.improvement_pct >= 0 ? "−" : "+"}{Math.abs(c.regime_ablation.improvement_pct).toFixed(1)}% CRPS</div><div className="muted">with vs without random recessions</div></div>
      </div>
      <div className="grid g2" style={{ marginTop: 16 }}>
        <div>
          <h3>PIT histogram</h3>
          <p className="muted" style={{ marginBottom: 6 }}>Where each realized value fell in its forecast distribution. Flat = calibrated; a U-shape means bands are too narrow.</p>
          <Columns labels={c.pit_hist.map((_, i) => `${i * 10}`)} values={c.pit_hist} format={(x) => pct(x)} />
        </div>
        <div>
          <h3>Raw 90% coverage by cutoff year</h3>
          <p className="muted" style={{ marginBottom: 6 }}>Conformal scaling for each year is learned only from earlier years' forecasts.</p>
          <Columns labels={years.map((y) => `'${y.slice(2)}`)} values={years.map((y) => c.by_year[y].cov90)} format={(x) => pct(x)}
            highlight={(i) => (years[i] === "2019" || years[i] === "2020" ? "var(--s2)" : "var(--s1)")} />
          <p className="muted">Orange: cutoffs whose forecast window contains the 2020 shock.</p>
        </div>
      </div>
    </Card>
  );
}

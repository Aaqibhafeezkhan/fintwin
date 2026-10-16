import { useEffect, useState } from "react";
import { Columns } from "../charts/Bars";
import { FanChart, FanLegend } from "../charts/FanChart";
import { Scatter } from "../charts/Scatter";
import { loadBacktest, loadCalibration, type Backtest, type Calibration } from "../data";
import { fixed, money, moneyTick, pct, prettyName, quarterLabel } from "../format";
import { Metric, MetricText, Section, Skeleton } from "../ui";

const VARS: Record<string, string> = { revenue: "Revenue", cash_like: "Cash", total_debt: "Debt" };

export function BacktestView({ onOpen }: { onOpen: (t: string) => void }) {
  const [bt, setBt] = useState<Backtest | null>(null);
  const [cal, setCal] = useState<Calibration | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { loadBacktest().then(setBt).catch((e) => setErr(String(e))); loadCalibration().then(setCal); }, []);
  if (err) return <p className="callout">{err}</p>;
  if (!bt || !cal) return <Skeleton h={600} />;

  const xs = cal.cross_section;
  const rows = xs.rows.filter((r) => r.realized_min_cum_fcf_pct_rev != null);
  const sorted = [...rows].sort((a, b) => a.health_stress - b.health_stress);
  const k = Math.floor((sorted.length * 2) / 5);
  const severe = (rs: typeof rows) => rs.filter((r) => (r.realized_min_cum_fcf_pct_rev ?? 0) < -10).length / Math.max(rs.length, 1);

  return (
    <div className="fade-in">
      <Section>
        <div className="eyebrow">Evidence</div>
        <h1 className="display h-l" style={{ margin: "8px 0 10px" }}>Does the twin know anything?</h1>
        <p className="lede">Every test below is out of sample and point-in-time. Each twin is calibrated only on facts
          <i> filed</i> before its test date, so later restatements stay invisible, and nothing was tuned on the outcomes.</p>
      </Section>

      <Section eyebrow="Finding 1" title="Frozen in February 2020, it ranked cash burn, mostly through persistence">
        <div className="metrics" style={{ ["--n" as string]: 4, marginBottom: 28 }}>
          <Metric label="Rank correlation" value={xs.spearman} format={(v) => `ρ ${v.toFixed(2)}`} foot={`95% CI ${fixed(xs.ci95[0], 2)}–${fixed(xs.ci95[1], 2)}`}
            info="Spearman correlation between the twin's demand-freeze health score (Feb 2020 data) and realized worst cumulative free cash flow, 2020Q1–2021Q2." />
          <MetricText label="Significance" value="p < 10⁻⁶" foot={`${xs.n} companies`} />
          <Metric label="Severe burn, fragile two-fifths" value={severe(sorted.slice(0, k)) * 100} format={(v) => v.toFixed(0)} unit="%" foot="cash burn worse than 10% of revenue" />
          <Metric label="Severe burn, robust two-fifths" value={severe(sorted.slice(-k)) * 100} format={(v) => v.toFixed(0)} unit="%" foot="same threshold" />
        </div>
        <Scatter points={rows.map((r) => ({ id: r.ticker, x: r.health_stress, y: r.realized_min_cum_fcf_pct_rev as number, label: r.ticker,
          detail: `${prettyName(r.name)} · debt raised ${fixed(r.realized_debt_raise_pct_rev, 0)}% of revenue` }))}
          xLabel="Twin health under a demand freeze (Feb 2020)" yLabel="Worst cumulative FCF 2020–21, % of revenue"
          xFmt={(x) => x.toFixed(0)} yFmt={(y) => `${y.toFixed(0)}%`}
          labelIds={["CCL", "RCL", "NCLH", "BA", "AAL", "MSFT", "GOOGL", "WMT", "LVS", "EXPE", "WYNN"]} onClick={onOpen} />
        <p className="muted" style={{ marginTop: 10, maxWidth: 760 }}>Every company receives the same generic shock, so this measures structural fragility, not who the
          pandemic actually hit. Walmart is the visible miss: fragile to a demand collapse it never suffered.</p>
        <p className="muted" style={{ marginTop: 6, maxWidth: 760 }}>The research paper adds harder controls. A trailing free-cash-flow
          margin ranks this outcome better (ρ ≈ 0.68), and against each company's own pre-2020 run-rate no balance-sheet model,
          the twin included, ranks the shock. The twin's robust strength is transmission: fed the revenue that actually happened, it
          identifies where a margin rule misjudges cash flow, in every year from 2014 to 2023.{" "}
          <a href="https://github.com/SpiliosDimakopoulos/fintwin/blob/main/docs/paper/fintwin.pdf">Read the paper</a>.</p>
      </Section>

      <CalibrationFinding cal={cal} />

      <CaseExplorer bt={bt} />

      <Section eyebrow="Limits" title="Where it is wrong">
        <ul className="prose" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
          <li>Unconditional forecasts cannot see a regime break coming: Carnival's revenue fell about 99% in 2020, beyond even the harshest preset.</li>
          <li>Cash forecasts lose to a random walk on average. Treasury decisions are discretionary, and seasonal working-capital swings are only partly modelled.</li>
          <li>Generic XBRL tags miss industry detail: Boeing's programme accounting, Netflix's content spending.</li>
          <li>Conformal rescaling fixes average coverage, not coverage within a crisis year.</li>
        </ul>
      </Section>
    </div>
  );
}

function CalibrationFinding({ cal }: { cal: Calibration }) {
  const [v, setV] = useState<"revenue" | "cash_like">("revenue");
  const c = cal.vars[v];
  const years = Object.keys(c.by_year).sort();
  return (
    <Section eyebrow="Finding 2" title={`${cal.n_forecasts.toLocaleString()} forecasts: skilful on revenue, honest about uncertainty`}
      right={<div className="segmented" role="group" aria-label="Variable">
        <button aria-pressed={v === "revenue"} onClick={() => setV("revenue")}>Revenue</button>
        <button aria-pressed={v === "cash_like"} onClick={() => setV("cash_like")}>Cash</button>
      </div>}>
      <p className="sub" style={{ marginBottom: 20, maxWidth: 760 }}>{cal.n_companies} companies, yearly point-in-time cutoffs from {cal.origins[0].slice(0, 4)} to {cal.origins[cal.origins.length - 1].slice(0, 4)},
        each forecasting the next {cal.horizon} reported quarters with 2,000 paths.</p>
      <div className="metrics" style={{ ["--n" as string]: 4, marginBottom: 30 }}>
        <Metric label="Accuracy vs naive" value={c.crps_skill_vs_naive * 100} format={(x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(0)}`} unit="%"
          foot={`twin wins ${pct(c.share_cases_beating_naive)} of forecasts`} info="CRPS skill against a seasonal random walk with historical spread. Positive means better." />
        <MetricText label="90% bands, raw → calibrated" value={`${pct(c.raw.coverage90)} → ${pct(c.conformal.coverage90)}`} foot="target 90%"
          info="Online conformal rescaling: each year's band width is corrected using only earlier years' errors." />
        <MetricText label="50% bands, raw → calibrated" value={`${pct(c.raw.coverage50)} → ${pct(c.conformal.coverage50)}`} foot="target 50%" />
        <Metric label="Recession regime" value={-c.regime_ablation.improvement_pct} format={(x) => `${x <= 0 ? "−" : "+"}${Math.abs(x).toFixed(1)}`} unit="% CRPS"
          foot="ablation, same random shocks" info="Adding Markov recessions with NBER base rates changes forecast error very little at a one-year horizon." />
      </div>
      <div className="cols-2">
        <div>
          <div className="chart-title">Where outcomes fell inside the forecast</div>
          <div className="chart-sub">PIT histogram: flat means calibrated; the U-shape says raw bands are too narrow</div>
          <Columns labels={c.pit_hist.map((_, i) => `${i * 10}`)} values={c.pit_hist} format={(x) => pct(x)} highlight={() => "var(--ink-2)"} />
        </div>
        <div>
          <div className="chart-title">Raw 90% coverage by cutoff year</div>
          <div className="chart-sub">vermillion: windows that contain the 2020 shock</div>
          <Columns labels={years.map((y) => `'${y.slice(2)}`)} values={years.map((y) => c.by_year[y].cov90)} format={(x) => pct(x)}
            highlight={(i) => (years[i] === "2019" || years[i] === "2020" ? "var(--s2)" : "var(--ink-2)")} />
        </div>
      </div>
    </Section>
  );
}

function CaseExplorer({ bt }: { bt: Backtest }) {
  const [ticker, setTicker] = useState("CCL");
  const [cut, setCut] = useState("pre_covid");
  const [v, setV] = useState("revenue");
  const tickers = [...new Set(Object.values(bt.forecast).map((f) => f.ticker))];
  const fb = bt.forecast[`${ticker}:${cut}`];
  const series = fb?.series[v];
  const sc = fb?.scores[v];
  const structural = fb && "dates" in fb.structural ? fb.structural : null;
  const stressLabel = cut === "pre_covid" ? "Demand freeze" : "Stagflation";
  const n = series?.realized.dates.length ?? 0;
  return (
    <>
      <Section eyebrow="Finding 3" title="Case by case: forecast against what was reported"
        right={
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <div className="segmented" role="group" aria-label="Company">
              {tickers.map((t) => <button key={t} aria-pressed={t === ticker} onClick={() => setTicker(t)}>{t}</button>)}
            </div>
            <div className="segmented" role="group" aria-label="Cutoff">
              <button aria-pressed={cut === "pre_covid"} onClick={() => setCut("pre_covid")}>Feb 2020</button>
              <button aria-pressed={cut === "pre_hikes"} onClick={() => setCut("pre_hikes")}>Jan 2022</button>
            </div>
            <div className="segmented" role="group" aria-label="Variable">
              {Object.entries(VARS).map(([key, l]) => <button key={key} aria-pressed={v === key} onClick={() => setV(key)}>{l}</button>)}
            </div>
          </div>
        }>
        {series && sc ? (
          <>
            <FanLegend layers={[{ label: "Baseline", color: "var(--s1)" }, { label: stressLabel, color: "var(--s2)" }]} realized="Actually reported" />
            <div style={{ marginTop: 10 }}>
              <FanChart histLabels={series.history.dates.map(quarterLabel)} history={series.history.values} legend={false}
                futureLabels={series.realized.dates.map(quarterLabel)}
                layers={[{ label: "Baseline", color: "var(--s1)", bands: series.base_bands.map((r) => r.slice(0, n)) },
                  { label: stressLabel, color: "var(--s2)", bands: series.stress_bands.map((r) => r.slice(0, n)) }]}
                realized={series.realized.values} realizedLabel="Actually reported" format={(x) => money(x)} tick={moneyTick} height={300} />
            </div>
            <div className="metrics" style={{ ["--n" as string]: 4, marginTop: 20 }}>
              <Metric label="Inside the 50% band" value={sc.coverage50 * 100} format={(x) => x.toFixed(0)} unit="%" foot={`${sc.n} quarters`} />
              <Metric label="Inside the 90% band" value={sc.coverage90 * 100} format={(x) => x.toFixed(0)} unit="%" foot="baseline forecast" />
              <Metric label={`Inside the ${stressLabel.toLowerCase()} band`} value={sc.stress_coverage90 * 100} format={(x) => x.toFixed(0)} unit="%" foot="90% band" />
              <Metric label="Accuracy vs naive" value={sc.crps_skill * 100} format={(x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(0)}`} unit="%" foot="CRPS skill" />
            </div>
          </>
        ) : <p className="muted">No realized data for this case.</p>}
      </Section>

      {structural && (
        <Section eyebrow="Finding 4" title="Given the real revenue, does the machine burn cash like the company did?"
          note="The twin is fed the realized revenue path, so only its internal mechanics (costs, working capital, capex, financing) produce the cash flow.">
          <FanLegend layers={[{ label: "Twin", color: "var(--s1)" }]} reported={false} realized="Actual" />
          <div style={{ marginTop: 10 }}>
            <FanChart futureLabels={structural.dates.map(quarterLabel)} legend={false}
              layers={[{ label: "Twin", color: "var(--s1)", bands: structural.model_cum_fcf_bands }]}
              realized={structural.actual_cum_fcf} realizedLabel="Actual" format={(x) => money(x)} tick={moneyTick} height={240} />
          </div>
          <p className="muted" style={{ marginTop: 10 }}>{ticker}: cumulative free cash flow error {fixed(structural.final_error_pct, 0)}% at the end of the window,
            quarter-to-quarter correlation {fixed(structural.corr, 2)}.</p>
        </Section>
      )}
    </>
  );
}

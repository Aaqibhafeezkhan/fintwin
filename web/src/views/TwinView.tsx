import { FanChart } from "../charts/FanChart";
import type { Company, Meta } from "../data";
import { RATINGS } from "../engine/ratings";
import { fixed, futureQuarters, healthStatus, money, moneyTick, pct, quarterLabel } from "../format";
import { Card, HealthBar, Stat, StatusPill } from "../ui";
import { MemoCard } from "./MemoCard";

const PARAM_ROWS: [keyof Company["params"] | string, string, (p: Company["params"]) => string][] = [
  ["mu", "Trend revenue growth", (p) => `${pct(Math.exp(p.mu * 4) - 1, 1)} / yr`],
  ["sigma_g", "Demand volatility", (p) => `${pct(p.sigma_g, 1)} / quarter`],
  ["t_df", "Tail thickness (Student-t df)", (p) => fixed(p.t_df, 1)],
  ["F,v", "Operating leverage (fixed cost share)", (p) => `${money(p.F)} fixed / qtr · ${pct(p.v)} variable`],
  ["ddays", "Customer deposits / deferred revenue", (p) => `${fixed(p.ddays, 0)} days`],
  ["coupon", "Average cost of debt", (p) => pct(p.coupon, 2)],
  ["refi_ratio", "Debt rollover policy", (p) => pct(p.refi_ratio)],
  ["sigma_fin", "Discretionary financing volatility", (p) => `${pct(p.sigma_fin, 1)} of debt / qtr`],
  ["maturities", "Debt maturity schedule", (p) => `${money(p.maturities_q.slice(0, 4).reduce((a, b) => a + b, 0))} due next 4 qtrs`],
  ["revolver_cap", "Committed credit facility", (p) => money(p.revolver_cap)],
  ["cash_floor", "Minimum operating cash", (p) => money(p.cash_floor)],
  ["ocf_ratio", "Unexplained operating cash flow", (p) => `${pct(p.ocf_ratio, 1)} of revenue`],
];

export function TwinView({ c, meta, onStress }: { c: Company; meta: Meta; onStress: (preset: string) => void }) {
  const base = c.presets.base;
  const h = c.history;
  const T = c.params.horizon;
  const fut = futureQuarters(c.params.last_quarter, T);
  const histLabels = h.dates.map(quarterLabel);
  const tail = (k: keyof typeof h.series, n = 16) => h.series[k].slice(-n);
  const tailLabels = histLabels.slice(-16);
  const lastRating = [...h.series.rating].reverse().find((r) => r != null);
  const rev = c.reverse_stress.sales_depth;
  const status = healthStatus(base.health_score);
  const prov = (field: string) => {
    const arr = h.provenance[field] ?? [];
    return arr[arr.length - 1];
  };

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="grid g2">
        <section className="card hero">
          <div>
            <div className="hero-score num" style={{ color: `var(--${status.key === "warning" ? "ink" : status.key})` }}>
              {base.health_score.toFixed(0)}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>Health score / 100</div>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <h2>{c.name}</h2>
              <StatusPill health={base.health_score} />
            </div>
            <p className="sub">
              {c.sector} · {c.params.history_quarters} quarters of SEC filings through {c.params.last_quarter}.
              Median of 5,000 simulated {T}-quarter futures under calibrated business-as-usual dynamics;
              the unluckiest 10% of paths score {base.health_p10.toFixed(0)} or lower.
            </p>
            <div className="muted">
              Sources: <a href={c.edgar_url} target="_blank" rel="noreferrer">EDGAR filings</a>
              {prov("revenue") && <> · <a href={prov("revenue")!} target="_blank" rel="noreferrer">latest revenue fact</a></>}
              {prov("total_debt") && <> · <a href={prov("total_debt")!} target="_blank" rel="noreferrer">latest debt fact</a></>}
            </div>
          </div>
        </section>
        <div className="grid g2">
          <Stat label="Liquidity breach, 3 yrs" value={pct(base.p_breach, base.p_breach < 0.1 ? 1 : 0)}
            foot="cash runs out after revolver & debt markets" />
          <Stat label="Synthetic rating today" value={lastRating != null ? RATINGS[lastRating] : "–"}
            foot={`P(sub-investment grade in 3y) ${pct(base.p_downgrade_below_ig)}`} />
          <Stat label="Breaking point" value={rev.p50 == null ? ">95%" : `−${pct(rev.p50)}`}
            foot="revenue drop that gives a 50% breach chance" />
          <Stat label="Coverage stress" value={pct(base.p_icr_below_1_5)} foot="P(interest coverage < 1.5× in 3y)" />
        </div>
      </div>

      <MemoCard ticker={c.ticker} />

      <div className="grid g3">
        <Card title="Revenue" sub="Quarterly, reported then simulated">
          <FanChart histLabels={tailLabels} history={tail("revenue")} futureLabels={fut}
            layers={[{ label: "Baseline", color: "var(--s1)", bands: base.bands!.revenue }]} format={(x) => money(x)} tick={moneyTick} height={220} />
        </Card>
        <Card title="Cash & short-term investments" sub="Liquidity buffer">
          <FanChart histLabels={tailLabels} history={tail("cash")} futureLabels={fut}
            layers={[{ label: "Baseline", color: "var(--s1)", bands: base.bands!.cash }]} format={(x) => money(x)} tick={moneyTick} height={220} />
        </Card>
        <Card title="Total debt" sub="Term debt, incl. refinancing and new issuance">
          <FanChart histLabels={tailLabels} history={tail("debt")} futureLabels={fut}
            layers={[{ label: "Baseline", color: "var(--s1)", bands: base.bands!.debt }]} format={(x) => money(x)} tick={moneyTick} height={220} />
        </Card>
      </div>

      <div className="grid g2">
        <Card title="Stress snapshot" sub="Health score and breach probability under each preset · click to open in the Stress Lab">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Scenario</th><th style={{ width: "40%" }}>Health</th><th className="r">P(breach)</th><th className="r">Sub-IG</th></tr></thead>
              <tbody>
                {Object.entries(meta.presets).map(([k, v]) => (
                  <tr key={k} className="clickable" onClick={() => onStress(k)} title={v.desc}>
                    <td>{v.label}</td>
                    <td><HealthBar value={c.presets[k].health_score} /></td>
                    <td className="r">{pct(c.presets[k].p_breach)}</td>
                    <td className="r">{pct(c.presets[k].p_downgrade_below_ig)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="What the twin learned from the filings" sub="Every parameter is estimated from this company's own history unless marked as an assumption">
          <div className="table-wrap">
            <table>
              <tbody>
                {PARAM_ROWS.map(([key, label, f]) => {
                  const src = c.params._sources[key as string];
                  const assumed = src?.startsWith("assumption");
                  return (
                    <tr key={label} title={src ?? "model default"}>
                      <td>{label}<div className="muted">{src ?? "model default"}</div></td>
                      <td className="r" style={{ whiteSpace: "nowrap" }}>
                        {f(c.params)}
                        {assumed && <div className="muted">assumption</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Data quality" sub="Checks run on the extracted XBRL panel">
        <div className="grid g4">
          <div><div className="muted">Quarters extracted</div><div className="num" style={{ fontSize: 18, fontWeight: 600 }}>{c.quality.quarters}</div><div className="muted">{c.quality.first} → {c.quality.last}</div></div>
          <div><div className="muted">Balance-sheet identity gap</div><div className="num" style={{ fontSize: 18, fontWeight: 600 }}>{fixed(c.quality.balance_sheet_identity_max_gap_pct, 2)}%</div><div className="muted">max, last 20 quarters</div></div>
          <div><div className="muted">Core field completeness</div><div className="num" style={{ fontSize: 18, fontWeight: 600 }}>{fixed(c.quality.core_completeness_last20_pct, 0)}%</div><div className="muted">last 20 quarters</div></div>
          <div><div className="muted">Debt maturity schedule</div><div style={{ fontSize: 14, fontWeight: 600 }}>{c.quality.maturity_ladder_stale ? "stale → assumed" : `as of ${c.quality.maturity_ladder_date}`}</div></div>
        </div>
        {c.quality.notes.length > 0 && <p className="muted" style={{ marginTop: 10 }}>Notes: {c.quality.notes.join(" · ")}</p>}
      </Card>
    </div>
  );
}

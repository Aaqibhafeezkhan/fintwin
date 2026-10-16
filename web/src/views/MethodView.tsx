import { Card } from "../ui";

export function MethodView() {
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="grid g3">
        <Card title="1 · Real data, any ticker">
          <p className="sub">SEC EDGAR XBRL <span className="kbd">companyfacts</span> → a clean quarterly panel. Tag drift is handled with
            ordered fallbacks; year-to-date cash-flow facts are de-cumulated (Q4 = FY − 9M); every number keeps the accession
            number of the filing it came from. Rates come from FRED.</p>
        </Card>
        <Card title="2 · A stock-and-flow twin">
          <p className="sub">Nine stocks (cash, receivables, inventory, payables, customer deposits, PP&amp;E, debt, revolver, equity)
            connected by flows, with two reinforcing and two balancing feedback loops and first-order delays.
            The balance sheet balances on every path, every quarter — enforced by property-based tests.</p>
        </Card>
        <Card title="3 · Calibrated Monte Carlo">
          <p className="sub">Demand, margin, rate and financing shocks are fitted on each company's own history: robust (MAD)
            volatilities, Student-t tails, demand–margin correlation, Vasicek short rate. 5,000 paths run in a Web Worker
            in tens of milliseconds.</p>
        </Card>
      </div>

      <Card title="Core equations (per quarter t, per path)">
        <div className="eq">{`g_t      = μ + φ(g_{t-1} − μ) + σ_g ε^d_t                       demand growth, AR(1), Student-t ε
Rev_t    = B_{t-1} e^{g_t} · S_season · (1 + shock_t)
Costs_t  = F (1+π)^t · cut_t + (v + m_t + Δv_t) · Rev_t          operating leverage
m_t      = ρ_m m_{t-1} + σ_m ε^m_t                               margin shock, corr(ε^d, ε^m) = ρ
r_t      = r_{t-1} + κ(θ − r_{t-1}) + σ_r ε^r_t                  Vasicek short rate
spread_t = Rating(ICR^{TTM}_{t-1})                               Damodaran coverage → spread (loop R1)
AR_t     = AR_{t-1} + (DSO/91 · Rev_t − AR_{t-1}) / τ_AR         first-order delays
Inv_t    = Inv_{t-1} + (DIO/91 · Costs_t − Inv_{t-1}) / τ_Inv
CFO_t    = NI_t + D&A_t + SBC_t − ΔNWC_t + other_t
Cash_t   = Cash_{t-1} + CFO_t − Capex_t − Div_t − BB_t − Mat_t + Refi_t + Issue_t + Draw_t
Access_t = 1 | 0.6 | 0.3 (ICR ≥ 1.5 | ≥ 0.8 | below) × MarketOpen_t       loop R2
Breach   = Cash_t < 0 after revolver, debt markets and (optional) equity`}</div>
      </Card>

      <div className="grid g2">
        <Card title="Health score (0–100)">
          <p className="sub">30% liquidity runway (cash + undrawn revolver vs. fixed costs, interest and unrefinanceable
            maturities; 8 quarters = full marks) · 30% synthetic rating from interest coverage · 20% net debt / EBITDA
            (0× = 100, 6× = 0) · 20% Altman Z'' (book-value version). A path that has breached is capped at 25.
            The headline score is the median across paths of the path-average.</p>
        </Card>
        <Card title="Engineering">
          <p className="sub">Python reference engine (numpy, vectorized) for calibration, backtests and exports; a TypeScript
            port runs in the browser. Golden parity tests feed both engines identical shocks and require agreement to 1e-6.
            Reverse stress tests use bisection with common random numbers so breach probability is monotone in shock size.</p>
        </Card>
      </div>
    </div>
  );
}

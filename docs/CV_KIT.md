# CV kit

## Project title (CV line)

**FinTwin: Corporate Financial Health Digital Twin** (Python, TypeScript/React, SEC EDGAR XBRL, Monte Carlo, system dynamics)

## CV bullets (pick 2–3)

* Built FinTwin, an open-source digital twin of public companies' finances from SEC XBRL filings. It is a stock-and-flow (system dynamics) model with 9 balance-sheet stocks and 4 feedback loops, stress-tested with calibrated Monte Carlo; live dashboard that rebuilds itself weekly from new filings at zero cost (GitHub Actions, 16 parallel shards), plus a 21-page research paper archived on Zenodo (doi:10.5281/zenodo.23434606).
* Validated on 30,000+ point-in-time, out-of-sample forecasts across 375 S&P 500 companies (2013–2025). Revenue forecasts beat a seasonal random walk by 27% (scaled CRPS), and online conformal calibration raised 90%-interval coverage from 70% to 91%.
* Designed an out-of-sample evaluation against 13 benchmarks (Altman, Ohlson, Zmijewski, cash-flow persistence) on COVID-19, 2020 bankruptcies and 2,661 firm-years: the twin beats classic distress scores on 2020 cash burn and on bankruptcies against size-matched survivors (AUC 0.95 vs 0.88 for Altman), and given realized revenue it identifies where simple cash-flow rules fail (incremental ρ = 0.30, positive in every year 2014–2023). It also documents what does not work: neither the twin nor the classic distress scores predicted who the 2020 shock would hit.
* Engineered a point-in-time XBRL pipeline (tag drift, YTD de-cumulation, impairment-adjusted EBIT, filed-date vintages), Sobol global sensitivity, reverse stress testing, and a rule-based analyst that writes evidence-backed credit notes for 390+ companies straight from the simulation output.
* Shipped a serverless React/TypeScript dashboard running 5,000 simulations in ~150 ms in a Web Worker, parity-tested against the Python engine to 1e-6, with CI and property-based tests.

## 30-second spoken pitch

"I built a flight simulator for a company's finances. It reads 15 years of a company's official SEC filings and learns how its money behaves: which costs are fixed, how fast customers pay, when its debt comes due. Then it replays the next three years 5,000 times under whatever crisis you pick, like a pandemic, a rate spike or closed bond markets, and shows the probability that the company runs out of cash. Then I tried hard to prove it wrong. Frozen in February 2020, it beat the classic distress scores at ranking who would burn cash, but a simple cash-flow ratio beat it, and neither it nor the classic scores predicted who the pandemic would actually hit. What it does well is the other half of a stress test: given the revenue that actually happened, it knows where cash departs from a simple rule, every year for a decade."

## Interview deep-dive answers

**"Why system dynamics instead of a regression or ML forecast?"**
Forecasting the shock is impossible; what matters is the *response*, and that is driven by structure: operating leverage, maturity walls, feedback between coverage and the cost of debt. A stock-and-flow model makes that structure explicit, keeps the balance sheet consistent and lets you ask counterfactuals. A black box can't answer "what if markets close for a year?"

**"How do you know it's not overfit?"**
There are five checks:
1. Point-in-time vintages, so the model never sees later data.
2. Parameters are estimated on each company's own history with robust estimators, with no tuning on outcomes.
3. An honest backtest. It reports where the twin fails (Boeing, Netflix) and that interval coverage is below nominal.
4. A structural test that feeds realized revenue to separate "couldn't foresee" from "misunderstood the mechanics".
5. Adversarial review of my own results. A referee-style review found that a trailing cash-flow margin explained most of my headline COVID result; I added persistence benchmarks and a run-rate-adjusted outcome, and rewrote the paper around what survived.

**"What was the hardest engineering problem?"**
XBRL data quality. Companies switch tags, report cash flows year-to-date and restate history. Generic tags also miss industry specifics such as Netflix's content spend and Boeing's customer advances. I solved it with ordered tag fallbacks, de-cumulation by shared start dates, filed-date filtering, and an explicit "unexplained operating cash flow" term so the model stays consistent with reported cash.

**"What would you do next?"**
Industry-specific modules: fleet lay-up costs for cruise and airlines, program accounting for aerospace, content amortization for media. I would also add Sobol global sensitivity, and calibrate market access on actual 2020 issuance data.

## LinkedIn post draft

> I just finished FinTwin, a "digital twin" of a public company's finances.
>
> It reads a company's SEC filings, builds a stock-and-flow model of how cash, debt and margins interact, and runs 5,000 simulated futures under any crisis you choose: a pandemic, +300bp rates, closed debt markets. You get a probability distribution, not a guess.
>
> What I learned testing it: frozen before COVID, it beat the Altman, Ohlson and Zmijewski scores at ranking who would burn cash, but a simple cash-flow margin beat it, and neither it nor the classic scores predicted who the shock would hit. Where it shines is transmission: fed the revenue that actually happened, it knows where cash departs from a simple rule, consistently across 2,661 firm-years. Its revenue forecasts beat a random walk and exponential smoothing.
>
> It all runs in the browser, with a Python reference engine and a TypeScript engine parity-tested to 1e-6.
>
> #FinancialModeling #MonteCarlo #SystemDynamics #DataScience #Python #TypeScript

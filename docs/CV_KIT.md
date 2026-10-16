# CV kit

## Project title (CV line)

**FinTwin: Corporate Financial Health Digital Twin** (Python, TypeScript/React, SEC EDGAR XBRL, Monte Carlo, system dynamics)

## CV bullets (pick 2–3)

* Built FinTwin, an open-source digital twin of public companies' finances from SEC XBRL filings. It is a stock-and-flow (system dynamics) model with 9 balance-sheet stocks and 4 feedback loops, stress-tested with calibrated Monte Carlo; live dashboard that rebuilds itself weekly from new filings at zero cost (GitHub Actions, 16 parallel shards), plus a 5-page technical preprint.
* Validated on 30,000+ point-in-time, out-of-sample forecasts across 375 S&P 500 companies (2013–2025). Revenue forecasts beat a seasonal random walk by 28% (CRPS), and online conformal calibration raised 90%-interval coverage from 70% to 91%.
* Frozen on pre-COVID filings, the twin's fragility ranking of 331 companies matched realized 2020–21 cash burn (Spearman ρ = 0.39, p < 10⁻¹²). Severe burn hit 22% of its most fragile quintile versus 3% of its most robust.
* Engineered a point-in-time XBRL pipeline (tag drift, YTD de-cumulation, impairment-adjusted EBIT, filed-date vintages), Sobol global sensitivity, reverse stress testing, and a rule-based analyst that writes evidence-backed credit notes for 392 companies straight from the simulation output.
* Shipped a serverless React/TypeScript dashboard running 5,000 simulations in ~150 ms in a Web Worker, parity-tested against the Python engine to 1e-6, with CI and property-based tests.

## 30-second spoken pitch

"I built a flight simulator for a company's finances. It reads 15 years of a company's official SEC filings and learns how its money behaves: which costs are fixed, how fast customers pay, when its debt comes due. Then it replays the next three years 5,000 times under whatever crisis you pick, like a pandemic, a rate spike or closed bond markets, and shows the probability that the company runs out of cash. To prove it works, I froze it in February 2020 and asked which of 331 big US companies would bleed cash. Of the fifth it rated most fragile, 22% did; of the fifth it rated most robust, 3%. Boeing came second from the bottom."

## Interview deep-dive answers

**"Why system dynamics instead of a regression or ML forecast?"**
Forecasting the shock is impossible; what matters is the *response*, and that is driven by structure: operating leverage, maturity walls, feedback between coverage and the cost of debt. A stock-and-flow model makes that structure explicit, keeps the balance sheet consistent and lets you ask counterfactuals. A black box can't answer "what if markets close for a year?"

**"How do you know it's not overfit?"**
There are four checks:
1. Point-in-time vintages, so the model never sees later data.
2. Parameters are estimated on each company's own history with robust estimators, with no tuning on outcomes.
3. An honest backtest. It reports where the twin fails (Boeing, Netflix) and that interval coverage is below nominal.
4. A structural test that feeds realized revenue to separate "couldn't foresee" from "misunderstood the mechanics".

**"What was the hardest engineering problem?"**
XBRL data quality. Companies switch tags, report cash flows year-to-date and restate history. Generic tags also miss industry specifics such as Netflix's content spend and Boeing's customer advances. I solved it with ordered tag fallbacks, de-cumulation by shared start dates, filed-date filtering, and an explicit "unexplained operating cash flow" term so the model stays consistent with reported cash.

**"What would you do next?"**
Industry-specific modules: fleet lay-up costs for cruise and airlines, program accounting for aerospace, content amortization for media. I would also add Sobol global sensitivity, and calibrate market access on actual 2020 issuance data.

## LinkedIn post draft

> I just finished FinTwin, a "digital twin" of a public company's finances.
>
> It reads a company's SEC filings, builds a stock-and-flow model of how cash, debt and margins interact, and runs 5,000 simulated futures under any crisis you choose: a pandemic, +300bp rates, closed debt markets. You get a probability distribution, not a guess.
>
> The test that convinced me it works: I froze 331 company twins using only data filed before 20 Feb 2020. Their fragility ranking matched how much cash each company actually burned in 2020–21 (Spearman ρ = 0.39, p < 10⁻¹²), with severe burn seven times as common in the most fragile fifth as in the most robust. Boeing came out second most fragile; Walmart and the drug distributors were the honest misses. Across 30,000+ out-of-sample forecasts, revenue predictions beat a naive benchmark by 28%.
>
> It all runs in the browser, with a Python reference engine and a TypeScript engine parity-tested to 1e-6.
>
> #FinancialModeling #MonteCarlo #SystemDynamics #DataScience #Python #TypeScript

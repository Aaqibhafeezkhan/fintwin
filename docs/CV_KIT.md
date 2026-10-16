# CV kit

## Project title (CV line)

**FinTwin: Corporate Financial Health Digital Twin** (Python, TypeScript/React, SEC EDGAR XBRL, Monte Carlo, system dynamics)

## CV bullets (pick 2–3)

* Built a digital twin of public companies' finances from SEC XBRL filings. It is a stock-and-flow (system dynamics) model with 9 balance-sheet stocks and 4 feedback loops, stress-tested with 5,000-path calibrated Monte Carlo simulation.
* Designed a point-in-time data pipeline that handles tag drift, de-cumulates year-to-date cash flows and excludes later restatements. The pipeline produced look-ahead-free backtests across 30 companies.
* Calibrated on pre-COVID filings only, the twin's stress ranking matched realized 2020–21 cash burn across 30 companies (Spearman ρ = 0.56, p = 0.001). Cruise lines and Boeing were flagged as most fragile.
* Shipped an interactive dashboard (React, Web Worker) that runs 5,000 simulations in ~150 ms in the browser. A TypeScript engine is parity-tested against the Python reference to 1e-6, and the balance-sheet identity is checked with property-based tests.
* Implemented reverse stress testing (bisection with common random numbers), synthetic credit ratings and CRPS-scored probabilistic backtests against naive baselines.

## 30-second spoken pitch

"I built a flight simulator for a company's finances. It reads 15 years of a company's official SEC filings and learns how its money behaves: which costs are fixed, how fast customers pay, when its debt comes due. Then it replays the next three years 5,000 times under whatever crisis you pick, like a pandemic, a rate spike or closed bond markets, and shows the probability that the company runs out of cash. To prove it works, I gave it only the data available in February 2020. It correctly flagged the cruise lines and Boeing as the most fragile of 30 companies."

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
> The test that convinced me it works: I calibrated 30 companies using only data filed before 20 Feb 2020. The twin's stress ranking matched how much cash each one actually burned in 2020–21 (Spearman ρ = 0.56). Cruise lines and Boeing came out most fragile, and Walmart was the honest miss.
>
> It all runs in the browser, with a Python reference engine and a TypeScript engine parity-tested to 1e-6.
>
> #FinancialModeling #MonteCarlo #SystemDynamics #DataScience #Python #TypeScript

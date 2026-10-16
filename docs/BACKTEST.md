# Backtest report

All numbers come from `web/public/data/backtest.json`, which `uv run python -m fintwin.export BACKTEST` regenerates. Twins are calibrated on **point-in-time** data (facts *filed* before the cutoff), with no tuning on outcomes.

## 0. Large-sample validation (headline)

**Design.** I tested 94 large non-financial companies at 13 yearly point-in-time cutoffs (15 Feb 2013–2025), with a 4-quarter horizon and 2,000 paths per forecast, giving 7,814 forecasts. The data are `web/public/data/calibration.json`, produced by `scripts/full_pipeline.sh`.

| | Revenue | Cash & ST investments |
|---|---|---|
| CRPS skill vs naive (pooled) | **+32%** | −22% |
| Forecasts beating naive | 69% | 45% |
| 90% coverage, raw → online conformal | 68% → **90%** | 41% → **92%** |
| 50% coverage, raw → online conformal | 34% → 53% | 22% → 56% |
| Recession-regime ablation (CRPS change) | −0.4% | −0.1% |

* **Revenue** forecasts are genuinely skilful.
* **Raw intervals are too narrow.** The PIT histogram is U-shaped, and online conformal rescaling, which for each year uses only earlier years' errors, fixes average coverage.
* **Cash** remains the weak spot: a random walk is a strong benchmark for cash 1–4 quarters out, and seasonal working-capital swings (e.g. Walmart's January peak) are only partly modelled.
* **The large sample exposed a real bug.** A cost-proportional cash floor made low-margin retailers "borrow up" to cash they never hold. Replacing it with the company's revealed minimum cash cut Walmart's cash CRPS roughly ninefold.
* **The recession regime** adds realism to stress paths but little forecast skill at a 1-year horizon. That is expected: with an entry hazard of 4.5% per quarter, few forecast windows contain a recession.

**COVID cross-section, scaled up.** With 88 companies frozen on 20 Feb 2020, Spearman ρ = 0.51 (p = 4·10⁻⁷, bootstrap 95% CI 0.33–0.65). Severe cash burn (worse than 10% of annual revenue) hit 26% of the twin's two most fragile quintiles and 0% of its two most robust.

The sections below are the original 6-company deep dives.

## Cutoffs

| Key | Information set | Stress scenario attached |
|---|---|---|
| `pre_covid` | filings by 20 Feb 2020 | Demand freeze (−70% revenue, markets shut 2q) |
| `pre_hikes` | filings by 31 Jan 2022 | Stagflation (rates +300bp, costs +3pp) |

## 1. Cross-section: did the twin know who would bleed?

I calibrated 30 non-financial companies on pre-COVID filings and ran each through the same generic demand-freeze scenario. The realized outcome is each company's worst cumulative free cash flow between Q1 2020 and Q2 2021, as a % of pre-COVID annual revenue.

| Twin metric vs realized | Spearman ρ | p | n |
|---|---|---|---|
| Stress health score vs worst cumulative FCF | **0.55** | 0.002 | 30 |
| Stress P(breach) vs worst cumulative FCF | −0.39 | 0.033 | 30 |
| Stress health score vs debt raised (% revenue) | −0.17 | 0.36 | 30 |

Reading:

* The lowest stress health scores went to Boeing (0), MGM, Macy's, American Airlines, Walmart, Norwegian, Marriott and Royal Caribbean. The cruise lines realized −72% to −83% of revenue in cumulative FCF, the worst outcomes in the sample.
* **Walmart is the clear false positive.** It is structurally fragile to a demand collapse (thin margins, high fixed costs) but saw a demand *boost*. The test measures fragility to an identical shock, not exposure to the actual one.
* Debt raised correlates only weakly. Financing reflects opportunity (cheap credit in 2020–21) as much as need.

## 2. Forecast scoring (6 showcase companies × 2 cutoffs, 8 quarters each)

The naive baselines are a seasonal random walk for revenue and a random walk for cash and debt, each with a Gaussian spread from historical changes. Skill = 1 − CRPS_twin / CRPS_baseline.

| Variable | 50% band coverage | 90% band coverage | Median CRPS skill | Cases beating baseline |
|---|---|---|---|---|
| Revenue | 16% | 62% | +17% | 67% |
| Cash & ST investments | 19% | 43% | +8% | 50% |
| Total debt | 26% | 49% | −4% | 42% |

Coverage is well below nominal. Both cutoffs sit immediately before regime breaks (a pandemic and the fastest hiking cycle in 40 years), and balance-sheet moves are dominated by discretionary financing decisions. The fans are therefore suited to *relative* risk ranking and stress testing, not to calibrated point forecasting.

## 3. Structural test: feed the realized revenue, compare cumulative free cash flow

This isolates the model's mechanics (cost structure, working capital, capex, payouts) from its inability to foresee the shock.

| Case | Twin cum. FCF | Actual | Error | Quarterly corr. |
|---|---|---|---|---|
| AAPL pre-COVID | $179.0B | $182.1B | −2% | 0.97 |
| CCL pre-COVID | −$12.8B | −$17.6B | 28% | 0.66 |
| INTC pre-COVID | $37.2B | $32.3B | 15% | −0.07 |
| AAPL pre-hikes | $170.8B | $204.4B | −16% | 0.67 |
| BA pre-COVID | −$8.7B | −$24.1B | 64% | 0.09 |
| NFLX pre-COVID | −$3.7B | +$1.8B | — | 0.22 |

Where the twin fails, and why:

* **Boeing.** The 737 MAX grounding drove inventory build-up and reversed customer advances. These are program-specific working-capital dynamics that the generic DIO and deposit-days ratios can't capture.
* **Netflix.** Production paused in 2020, so content cash spend collapsed. The twin's "unexplained operating cash flow" ratio is calibrated on the pre-pandemic content build-out.
* **Carnival.** The direction and timing are right, but the twin under-estimates burn by about a third. Customer-deposit refunds and fixed ship-operating costs ran higher than the calibrated cost structure.

## Reproduce

```bash
cd engine
bash scripts/build_all.sh            # all companies + goldens + backtests
uv run python scripts/backtest_check.py CCL AAPL   # console summary
```

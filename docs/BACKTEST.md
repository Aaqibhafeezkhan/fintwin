# Backtest report

All numbers come from `web/public/data/backtest.json`, which `uv run python -m fintwin.export BACKTEST` regenerates. Twins are calibrated on **point-in-time** data (facts *filed* before the cutoff), with no tuning on outcomes.

## Cutoffs

| Key | Information set | Stress scenario attached |
|---|---|---|
| `pre_covid` | filings by 20 Feb 2020 | Demand freeze (−70% revenue, markets shut 2q) |
| `pre_hikes` | filings by 31 Jan 2022 | Stagflation (rates +300bp, costs +3pp) |

## 1. Cross-section: did the twin know who would bleed?

I calibrated 30 non-financial companies on pre-COVID filings and ran each through the same generic demand-freeze scenario. The realized outcome is each company's worst cumulative free cash flow between Q1 2020 and Q2 2021, as a % of pre-COVID annual revenue.

| Twin metric vs realized | Spearman ρ | p | n |
|---|---|---|---|
| Stress health score vs worst cumulative FCF | **0.56** | 0.001 | 30 |
| Stress P(breach) vs worst cumulative FCF | −0.45 | 0.013 | 30 |
| Stress health score vs debt raised (% revenue) | −0.16 | 0.40 | 30 |

Reading:

* The lowest stress health scores went to Boeing (0), MGM, Macy's, American Airlines, Walmart, Norwegian, Marriott and Royal Caribbean. The cruise lines realized −72% to −83% of revenue in cumulative FCF, the worst outcomes in the sample.
* **Walmart is the clear false positive.** It is structurally fragile to a demand collapse (thin margins, high fixed costs) but saw a demand *boost*. The test measures fragility to an identical shock, not exposure to the actual one.
* Debt raised correlates only weakly. Financing reflects opportunity (cheap credit in 2020–21) as much as need.

## 2. Forecast scoring (6 showcase companies × 2 cutoffs, 8 quarters each)

The naive baselines are a seasonal random walk for revenue and a random walk for cash and debt, each with a Gaussian spread from historical changes. Skill = 1 − CRPS_twin / CRPS_baseline.

| Variable | 50% band coverage | 90% band coverage | Median CRPS skill | Cases beating baseline |
|---|---|---|---|---|
| Revenue | 16% | 63% | +15% | 67% |
| Cash & ST investments | 19% | 43% | +14% | 58% |
| Total debt | 28% | 50% | −3% | 42% |

Coverage is well below nominal. Both cutoffs sit immediately before regime breaks (a pandemic and the fastest hiking cycle in 40 years), and balance-sheet moves are dominated by discretionary financing decisions. The fans are therefore suited to *relative* risk ranking and stress testing, not to calibrated point forecasting.

## 3. Structural test: feed the realized revenue, compare cumulative free cash flow

This isolates the model's mechanics (cost structure, working capital, capex, payouts) from its inability to foresee the shock.

| Case | Twin cum. FCF | Actual | Error | Quarterly corr. |
|---|---|---|---|---|
| AAPL pre-COVID | $179.0B | $182.1B | −2% | 0.97 |
| CCL pre-COVID | −$12.1B | −$17.6B | 31% | 0.68 |
| INTC pre-COVID | $37.2B | $32.3B | 15% | −0.07 |
| AAPL pre-hikes | $170.8B | $204.4B | −16% | 0.67 |
| BA pre-COVID | −$9.4B | −$24.1B | 61% | 0.09 |
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

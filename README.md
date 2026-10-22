# FinTwin: a financial-health digital twin for public companies

[![ci](https://github.com/SpiliosDimakopoulos/fintwin/actions/workflows/ci.yml/badge.svg)](https://github.com/SpiliosDimakopoulos/fintwin/actions/workflows/ci.yml)
[![data](https://github.com/SpiliosDimakopoulos/fintwin/actions/workflows/data.yml/badge.svg)](https://github.com/SpiliosDimakopoulos/fintwin/actions/workflows/data.yml)
![coverage](https://img.shields.io/badge/coverage-88%25-brightgreen)
![ruff](https://img.shields.io/badge/lint-ruff-261230)
![mypy](https://img.shields.io/badge/types-mypy-2a6db2)
![lighthouse](https://img.shields.io/badge/lighthouse-94%20%C2%B7%20100%20%C2%B7%20100%20%C2%B7%20100-brightgreen)
![licence](https://img.shields.io/badge/licence-MIT-lightgrey)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23434606.svg)](https://doi.org/10.5281/zenodo.23434606)

**[Live dashboard](https://spiliosdimakopoulos.github.io/fintwin/)** · **[Paper (PDF)](docs/paper/fintwin.pdf)** · [Methodology](docs/METHODOLOGY.md) · [Backtest report](docs/BACKTEST.md) · [Carnival case study](docs/CASE_STUDY_CCL.md)

**FinTwin turns a company's SEC filings into a living model of its finances, then stress-tests it thousands of times.** It doesn't predict a stock price. It simulates how cash, debt, margins and credit quality respond to a pandemic, a rate shock or a closed bond market, and it reports a *distribution* of outcomes rather than a single number.

![Stress lab demo](docs/demo.gif)

> **30-second pitch.** A flight simulator for corporate finance. It reads 15 years of a company's official filings and learns how its finances behave: fixed vs variable costs, how fast customers pay, when its debt matures. Then it replays the future 5,000 times under any crisis you pick, live in the browser. Then I tested it the hard way, on every non-financial SEC filer including the ones that went bust, against simple rules that see the same data. Most of what it seemed to know was persistence: a 16-quarter cash-flow margin predicts cash better than the twin, and the twin's score predicts bankruptcy no better than its own formula without simulation. What survives is small and specific: given the revenue that happened, the direction of the twin's departures from that margin is informative, and adding about 15% of them lowers the error out of sample. It covers 390+ companies on the dashboard and rebuilds itself from the latest filings every week.

## Results

![The paper in one picture: given realized revenue, the twin alone is less accurate than a 16-quarter margin but improves it when combined; in ranking bankruptcies it equals its own formula without simulation](docs/findings.png)

All numbers come from out-of-sample, point-in-time tests on a survivorship-free universe: **5,220 non-financial SEC filers** (every company with $50M+ revenue in some year 2012-2024, including those later acquired, delisted or bankrupt), 20,431 firm-years 2014-2024, and a census of **377 bankruptcy petitions** (8-K Item 1.03). The decision rule for the main test was committed before it was run.

| Test | Result |
|---|---|
| **Transmission** (main test): realized revenue given to the twin and to six simple rules, 16,138 firm-years | Alone, the twin is the least accurate of eight models (median error 11.3 pp of revenue vs **6.9** for a 16-quarter margin). The old headline statistic (incremental ρ 0.33 against a 4-quarter margin) is matched by the 16-quarter margin alone (**0.40**): it measured mean reversion. The twin's departures still carry information no rule has (encompassing *t* = 9.9; ρ 0.22 against the 16-quarter margin's residual), and margin + ~15% of the twin's departure cuts out-of-sample error by **3.5%** (CI excludes zero; also beats the same combination with a regression rule). |
| **Bankruptcy**: petition within 8 quarters, all filers | AUC **0.86** for the twin, **0.87** for its scoring formula without simulation, 0.86 Ohlson, 0.81 Altman Z″. Among already-weak firms (82% of petitions): 0.77 vs 0.76. Simulation adds nothing to ranking. |
| **Liquidity decisions** given realized revenue | Event probabilities add +0.01 to +0.04 AUC out of sample to a static runway rule + scores (cash halving, new borrowing, dividend and capex cuts). The market-access and cash-conservation loops are the only channels that produce these events; the other two loops are inert. |
| **2020** (one cutoff of eleven) | FCF margin beats the twin at ranking raw burn (0.55 vs 0.31, all filers; 0.69 vs 0.45, S&P 500 of 20 Feb 2020). Nothing ranks abnormal burn under a uniform scenario, but given each firm's industry shock, the twin's fragility does (*t* = 5.2). |
| **Forecasts and calibration** | Revenue CRPS 26% better than a seasonal random walk, 19% better than ETS; cash forecasts lose to both. Conformal 90% intervals reach 91% on average (using only already-reported errors) but **77%** for revenue in the 2020 stress quarters. |
| **Engineering** | Python and TypeScript engines agree to 1e-6 on golden runs; the balance sheet balances on every path (property-based tests); 52/53-week fiscal calendars (16-week quarters) are read correctly. |

Where it fails, in the paper's own words ([docs/paper/fintwin.pdf](docs/paper/fintwin.pdf)):
- It is not an early-warning system: its ranking of firms is that of its own scoring formula, and fragility rankings mostly measure persistent cash-flow habits.
- It overreacts to revenue changes (too much assumed operating leverage); its cash forecasts must be shrunk toward a long-window margin.
- Its uncertainty bands are calibrated on average, not in a crisis year, and do not widen enough for small firms.
- Its feedback loops do not change the ranking of companies.

## What it does

| | |
|---|---|
| **Point-in-time SEC data** | XBRL `companyfacts` with tag fallbacks, year-to-date de-cumulation, impairment-adjusted EBIT, and *filed-date* vintages that make backtests free of look-ahead bias. Every number links to its source filing. |
| **System-dynamics model** | 9 balance-sheet stocks, quarterly flows, first-order delays and 4 feedback loops: a leverage–spread spiral, a market-access cliff, cash conservation and delayed restructuring. |
| **Calibrated Monte Carlo** | Robust (MAD) volatilities, Student-t tails, demand–margin correlation, a Vasicek short rate, and a Markov recession regime with NBER base rates and company-specific GDP sensitivity. |
| **Stress tools** | 8 crisis presets, free sliders and 6 CFO levers. Reverse stress testing answers "how big a shock breaks it?". Tornado charts and Sobol global sensitivity (with bootstrap CIs) show what matters. |
| **Analyst notes** | A rule-based analyst turns each company's simulation into a credit-memo-style note: verdict, evidenced risks, buffers, scenario commentary, watch list. It is deterministic, so every figure is correct by construction. An optional LLM module writes freer prose from the same fact sheet and machine-checks its figures, if you supply your own key. |
| **Sector-adjusted health** | Leverage that would alarm a software company is normal for a utility. Coverage and leverage are scored against each GICS sector's own norms, which are estimated from the data, and a waterfall shows how each component moves the score. |
| **Time machine** | Rewind any company to what its twin said at every February since 2013, using only the filings that existed then, and see what actually happened next (`#time/CCL`). |
| **Compare** | Put two companies side by side (`#versus/CCL/RCL`), or scan the whole universe × 8 crises, filtered by sector. |
| **Dashboard** | Editorial research-terminal design, light and dark. The landing page runs a live Monte Carlo you can steer. There is a Ctrl K / ⌘K company switcher, a stress lab whose scenarios are shareable as links, peer context on every company, and keyboard shortcuts (press `?`). Everything runs client-side in a Web Worker, so no server is needed. |
| **Ask the twin** | Describe a crisis in plain English ("revenue falls 40% for a year and banks stop lending", "another 2008 for Carnival") and the stress lab sets it up and simulates it. Built-in rules work everywhere; an optional on-device language model (Qwen2.5 1.5B via WebLLM, no API key, nothing leaves the browser) handles free-form text. Language only chooses the scenario: model output is validated and clamped, and every number comes from the simulation. |
| **What changed this week** | Each Monday's rebuild is compared with the previous one: which companies' health moved by 5+ points, after which filing, and which part of the score (runway, coverage, leverage, solvency) drove it. Also as an RSS feed. |
| **Always current, at zero cost** | Every Monday a GitHub Actions workflow pulls the newest SEC filings and FRED data, rebuilds all twins across 16 parallel runners, re-runs the validation and the time machine, checks Python–TypeScript parity, and redeploys. |

| | |
|---|---|
| ![Overview](docs/screenshots/overview-light-1400.png) | ![Company twin](docs/screenshots/twin-light-1400.png) |
| ![Stress matrix, dark theme](docs/screenshots/compare-dark-1400.png) | ![Evidence](docs/screenshots/backtest-light-1400.png) |

## Run it

```bash
cp .env.example .env                       # SEC_USER_AGENT (required by SEC)
cd engine && uv sync && uv run pytest -q   # 39 tests: balance-sheet identity (Hypothesis), offline XBRL end-to-end, 52/53-week calendars, point-in-time, the transmission nulls, CRPS...
bash scripts/full_pipeline.sh              # validation (~30k forecasts) + all snapshots + backtests (hours; CI shards it)
cd ../web && npm ci && npm test && npm run dev    # includes Python <-> TypeScript parity
```

Optional extras:
- `uv run python -m fintwin.notes` regenerates the analyst notes. The optional LLM memos need your own API key: `uv run --extra ai python -m fintwin.memo CCL`.
- `uv run --extra api python -m fintwin.api` lets you twin any ticker live.
- `uv run python scripts/paper_assets.py` regenerates the paper's figures and numbers.

## Repository map

```
engine/fintwin/   data/ (EDGAR, facts, FRED) · model/ (stock-and-flow core, ratings) · stochastic/ (calibrate, shocks, MC)
                  scenarios/ (presets, reverse stress) · sensitivity/ (tornado, Sobol) · backtest/ (walk-forward, batch, scoring)
                  universe.py (S&P 500, sector norms) · pipeline.py (sharded weekly build) · export.py · notes.py · memo.py · api.py
web/src/          engine/ (TS port + parity tests) · views/ · charts/
docs/             paper/ (LaTeX + figures, numbers generated from data) · METHODOLOGY · BACKTEST · CASE_STUDY_CCL · CV_KIT
```

*Data: SEC EDGAR XBRL, FRED. Rating table: A. Damodaran (Jan 2026). MIT licence. Not investment advice.*

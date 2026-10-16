"""Per-company research experiments behind the paper (one JSON per company, merged by `stats.py`).

Three designs, all strictly point-in-time (the twin and every benchmark see only filings available at the cutoff):

* covid    - twins frozen on 20 Feb 2020 under several scenarios and with each feedback loop switched off, the
             accounting benchmarks an analyst would have computed on the same day, and realized 2020-21 outcomes.
* panel    - every 15 February 2013-2023: the twin's baseline verdict, the same benchmarks, and distress
             outcomes over the following eight reported quarters.
* forecast - every 15 February 2013-2025: four-quarter predictive distributions of revenue and cash from the twin,
             a seasonal random walk and an exponential-smoothing state-space model (ETS), scored by the CRPS.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from ..backtest.batch import _baseline, _realized
from ..backtest.scoring import crps_gaussian, crps_samples
from ..data.facts import CompanyData, load_company
from ..data.fred import macro_quarterly
from ..model.ratings import rating_rank
from ..model.sd_model import simulate
from ..scenarios.presets import DEFAULT_LEVERS, PRESETS, build_scenario
from ..stochastic.calibrate import calibrate
from ..stochastic.mc import summarize
from ..stochastic.shocks import draw_shocks
from ..universe import classify

COVID_CUT = "2020-02-20"
PANEL_ORIGINS = [f"{y}-02-15" for y in range(2013, 2024)]
FORECAST_ORIGINS = [f"{y}-02-15" for y in range(2013, 2026)]
SCENARIOS = ["base", "rates_200", "sales_20", "recession", "pandemic", "credit_crunch"]
ABLATIONS: dict[str, dict] = {
    "full": {},
    "no_r1": {"loop_r1": False},
    "no_r2": {"loop_r2": False},
    "no_b1": {"cut_capex": False, "cut_payouts": False},
    "no_b2": {"cut_costs": False},
    "no_loops": {"loop_r1": False, "loop_r2": False, "cut_capex": False, "cut_payouts": False, "cut_costs": False},
}
H_FC = 4
FREEZE = PRESETS["pandemic"]["knobs"]


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _ttm(q: pd.DataFrame, col: str) -> float:
    s = q[col].tail(4)
    return float(s.sum()) if s.notna().sum() == 4 else np.nan


def health_at_open(p: dict) -> float:
    """The twin's health formula evaluated on the opening balance sheet, without any simulation.

    Mirrors the scoring block of model.sd_model (runway, coverage rating, leverage, Altman Z'') with no sector
    norms, so comparing it with the simulated score isolates what the simulation adds to the formula.
    """
    ebit, ebitda = float(np.sum(p["ebit_ttm0"])), float(np.sum(p["ebitda_ttm0"]))
    interest = float(np.sum(p["interest_ttm0"]))
    icr = ebit / max(interest, 1e-9)
    access = 1.0 if icr >= 1.5 else 0.6 if icr >= 0.8 else 0.3
    burn = max(p["F"] + interest / 4 + p["maturities_q"][0] * (1 - access), 1e-9)
    s_liq = float(np.clip((p["cash0"] + p["revolver_cap"]) / burn / 8.0, 0.0, 1.0)) * 100
    s_cov = float(rating_rank(np.array([icr]))[0]) / 14.0 * 100
    nd = (p["debt0"] - p["cash0"]) / ebitda if ebitda > 0 else 99.0
    s_lev = float(np.clip((6.0 - nd) / 6.0, 0.0, 1.0)) * 100 if ebitda > 0 else 0.0
    assets = p["cash0"] + p["ar0"] + p["inv0"] + p["ppe0"] + p["other_net0"] + p["other_liab0"]
    liabilities = max(assets - p["equity0"], 1e-9)
    wc = p["cash0"] + p["ar0"] + p["inv0"] - p["ap0"] - p["def0"] + p["wc_other0"]
    z = (6.56 * wc + 3.26 * p["retained0"] + 6.72 * ebit) / max(assets, 1e-9) + 1.05 * p["equity0"] / liabilities
    s_solv = float(np.clip((z - 1.1) / 1.5, 0.0, 1.0)) * 100
    return 0.3 * s_liq + 0.3 * s_cov + 0.2 * s_lev + 0.2 * s_solv


def features(c: CompanyData, p: dict) -> dict:
    """Accounting benchmarks on the information set of the cutoff (higher-is-riskier orientation is set in stats)."""
    q = c.quarters
    last = q.iloc[-1]
    rev = _ttm(q, "revenue")
    ebit = float(np.sum(p["ebit_ttm0"]))
    ebitda = float(np.sum(p["ebitda_ttm0"]))
    interest = float(np.sum(p["interest_ttm0"]))
    ni = _ttm(q, "net_income")
    ni_prev = float(q["net_income"].iloc[-8:-4].sum()) if len(q) >= 8 else np.nan
    cfo = _ttm(q, "cfo")
    cash = float(np.nansum([last["cash"], last["short_investments"]]))
    debt = float(last["total_debt"]) if np.isfinite(last["total_debt"]) else 0.0
    ta, tl, ca, cl = (float(last[k]) for k in ("assets", "liabilities", "current_assets", "current_liabilities"))
    eq, re = float(last["equity"]), float(last["retained_earnings"])
    if not np.isfinite(tl) and np.isfinite(ta) and np.isfinite(eq):
        tl = ta - eq
    wc = ca - cl
    # Altman (1968) Z'' for non-manufacturers (book equity); Ohlson (1980) O-score; Zmijewski (1984)
    z2 = 6.56 * wc / ta + 3.26 * re / ta + 6.72 * ebit / ta + 1.05 * eq / tl
    o = (
        -1.32
        - 0.407 * np.log(max(ta, 1.0) / 1e6)
        + 6.03 * tl / ta
        - 1.43 * wc / ta
        + 0.0757 * cl / ca
        - 1.72 * float(tl > ta)
        - 2.37 * ni / ta
        - 1.83 * cfo / tl
        + 0.285 * float(ni < 0 and ni_prev < 0)
        - 0.521 * (ni - ni_prev) / max(abs(ni) + abs(ni_prev), 1e-9)
    )
    zm = -4.336 - 4.513 * ni / ta + 5.679 * tl / ta + 0.004 * ca / cl
    # an analyst's static stress test of the same scenario: liquidity / cash needs over a three-quarter freeze,
    # with fixed costs, interest and maturities due, and the contribution of the revenue that remains
    rev_q = rev / 4
    need_q = max(p["F"] + interest / 4 - (1 - p["v"]) * (1 - FREEZE["sales_depth"]) * rev_q, 0.0)
    due = float(np.sum(p["maturities_q"][:3]))
    static = (cash + p["revolver_cap"]) / max(3 * need_q + due, 1e-9)
    yoy = np.log(q["revenue"] / q["revenue"].shift(4)).dropna().tail(20)
    fcf = _ttm(q, "cfo") - _ttm(q, "capex")
    return {
        "fcf_margin": _f(fcf / rev),
        "capex_rev": _f(_ttm(q, "capex") / rev),
        "health_t0": _f(health_at_open(p)),
        "z2": _f(z2),
        "o_score": _f(o),
        "zmijewski": _f(zm),
        "nd_ebitda": _f((debt - cash) / ebitda) if ebitda > 0 else 20.0,
        "icr": _f(np.clip(ebit / interest, -10, 100)) if interest > 0 else 100.0,
        "cash_rev": _f(cash / rev),
        "current_ratio": _f(ca / cl),
        "debt_assets": _f(debt / ta),
        "due_cash": _f(float(np.sum(p["maturities_q"][:4])) / max(cash, 1e-9)),
        "rev_vol": _f(yoy.std()),
        "fixed_share": _f(4 * p["F"] / max(4 * p["F"] + p["v"] * rev, 1e-9)),
        "static_cover": _f(min(static, 50.0)),
        "log_rev": _f(np.log(max(rev, 1.0))),
    }


def _run(p: dict, knobs: dict, levers: dict, n: int, horizon: int, seed: int) -> dict:
    eps = draw_shocks(p, n, horizon, seed=seed)
    sm = summarize(simulate(p, build_scenario(knobs, horizon), eps, {**DEFAULT_LEVERS, **levers}))
    return {"health": sm["health_score"], "p_breach": sm["p_breach"], "health_p10": sm["health_p10"]}


def covid(ticker: str, full: pd.DataFrame | None) -> dict | None:
    hist = load_company(ticker, asof=COVID_CUT)
    if len(hist.quarters) < 16:
        return None
    p = calibrate(hist, macro_quarterly(COVID_CUT), 8)
    tol = p.get("sector_tol", 1.0)
    raw = {**p, "sector_tol": 1.0}  # primary analysis: no sector norms (those are estimated from later data)
    out: dict = {
        "ticker": ticker,
        "name": hist.name,
        "sector": classify(ticker)[0],
        "last_quarter": str(hist.quarters.index[-1].date()),
    }
    out["scenarios"] = {k: _run(raw, PRESETS[k]["knobs"], {}, 2000, 8, 7) for k in SCENARIOS}
    out["ablations"] = {k: _run(raw, FREEZE, lv, 2000, 8, 7) for k, lv in ABLATIONS.items()}
    # loops act through trailing coverage and the maturity wall, so they get more room over three years
    p12 = {**calibrate(hist, macro_quarterly(COVID_CUT), 12), "sector_tol": 1.0}
    out["ablations_h12"] = {k: _run(p12, FREEZE, lv, 2000, 12, 7) for k, lv in ABLATIONS.items()}
    out["sector_adjusted"] = _run({**p, "sector_tol": tol}, FREEZE, {}, 2000, 8, 7)
    out["features"] = features(hist, p)
    out["realized"] = covid_outcomes(hist, full) if full is not None else {}
    return out


def _abnormal_burn(pre: pd.DataFrame, window: pd.DataFrame, rev_ttm: float) -> float:
    """Worst cumulative free cash flow *relative to the company's own pre-cutoff run-rate*, % of revenue.

    Raw cumulative FCF mostly measures a persistent propensity to burn cash (capex-heavy utilities, growth companies
    burn every year); a stress test claims to predict the deterioration a shock causes, so the outcome subtracts the
    trailing four-quarter FCF run-rate from every quarter of the window.
    """
    run_rate = (_ttm(pre, "cfo") - _ttm(pre, "capex")) / 4
    if not np.isfinite(run_rate):
        return np.nan
    gap = ((window["cfo"] - window["capex"]).fillna(run_rate) - run_rate).cumsum()
    return float(min(gap.min(), 0.0) / rev_ttm * 100)


def covid_outcomes(hist: CompanyData, full: pd.DataFrame) -> dict:
    pre = hist.quarters
    rev_ttm = _ttm(pre, "revenue")
    win = full[(full.index > pd.Timestamp("2020-01-15")) & (full.index <= pd.Timestamp("2021-07-15"))]
    if len(win) < 4 or not np.isfinite(rev_ttm) or rev_ttm <= 0:
        return {}
    fcf = (win["cfo"] - win["capex"]).fillna(0).cumsum()
    yoy = (full["revenue"] / full["revenue"].shift(4) - 1).reindex(win.index)
    cash_like = (full["cash"] + full["short_investments"].fillna(0)).reindex(win.index)
    cash_pre = float(pre["cash"].iloc[-1] + np.nan_to_num(pre["short_investments"].iloc[-1]))
    div_pre = float(pre["dividends"].tail(4).fillna(0).sum())
    post = win[win.index > pd.Timestamp("2020-04-15")].head(4)
    div_post = float(post["dividends"].fillna(0).sum())
    return {
        "burn": _f(fcf.min() / rev_ttm * 100),
        "abn_burn": _f(_abnormal_burn(pre, win, rev_ttm)),
        "rev_drop": _f(yoy.min() * 100),
        "debt_raise": _f((win["total_debt"].max() - pre["total_debt"].iloc[-1]) / rev_ttm * 100),
        "cash_min_ratio": _f(cash_like.min() / cash_pre) if cash_pre > 0 else None,
        "div_payer": bool(div_pre > 0),
        "div_cut": bool(div_pre > 0 and len(post) == 4 and div_post < 0.5 * div_pre),
    }


def _distress(hist: CompanyData, full: pd.DataFrame) -> dict:
    """Outcomes over the eight reported quarters after the cutoff's last known quarter."""
    pre = hist.quarters
    nxt = full[full.index > pre.index[-1] + pd.Timedelta(days=20)].head(8)
    rev_ttm = _ttm(pre, "revenue")
    if len(nxt) < 8 or not np.isfinite(rev_ttm) or rev_ttm <= 0:
        return {}
    fcf = (nxt["cfo"] - nxt["capex"]).fillna(0).cumsum()
    both = pd.concat([pre.tail(4), nxt])
    ebit = (both["operating_income"]).rolling(4).sum().tail(8)
    intr = both["interest_expense"].rolling(4).sum().tail(8)
    icr = (ebit / intr.where(intr > 0)).dropna()
    icr0 = _ttm(pre, "operating_income") / max(_ttm(pre, "interest_expense"), 1e-9)
    div_pre = float(pre["dividends"].tail(4).fillna(0).sum())
    div_post = float(nxt["dividends"].head(4).fillna(0).sum())
    return {
        "burn8": _f(fcf.min() / rev_ttm * 100),
        "abn_burn8": _f(_abnormal_burn(pre, nxt, rev_ttm)),
        "icr0": _f(icr0),
        "icr_min": _f(icr.min()) if len(icr) else None,
        "div_payer": bool(div_pre > 0),
        "div_cut": bool(div_pre > 0 and div_post < 0.5 * div_pre),
    }


def _ets_samples(y: np.ndarray, h: int, log: bool, seasonal: bool, n: int = 2000) -> np.ndarray | None:
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    y = y[np.isfinite(y)][-40:]
    if log:
        if (y <= 0).any():
            return None
        y = np.log(y)
    if len(y) < 12:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = ETSModel(
                y,
                error="add",
                trend="add" if seasonal else None,
                damped_trend=seasonal,
                seasonal="add" if seasonal else None,
                seasonal_periods=4 if seasonal else None,
            ).fit(disp=False)
            sims = np.asarray(m.simulate(h, anchor="end", repetitions=n, rng=np.random.default_rng(3))).reshape(h, n)
    except Exception:
        return None
    return np.exp(sims) if log else sims


def forecasts(ticker: str, full_data: CompanyData, hists: dict[str, CompanyData]) -> list[dict]:
    full = full_data.quarters
    rows: list[dict] = []
    for origin in FORECAST_ORIGINS:
        hist = hists.get(origin)
        if hist is None or len(hist.quarters) < 16:
            continue
        try:
            rows += _forecast_origin(origin, hist, full)
        except Exception:  # one unusable vintage must not drop the company's other forecasts
            continue
    return rows


def _forecast_origin(origin: str, hist: CompanyData, full: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    real = _realized(full, hist.quarters.index[-1])
    if len(real) < H_FC:
        return rows
    p = calibrate(hist, macro_quarterly(origin), H_FC)
    out = simulate(p, build_scenario({}, H_FC), draw_shocks(p, 2000, H_FC, seed=11), DEFAULT_LEVERS)
    q = hist.quarters
    scale = _ttm(q, "revenue") / 4
    series = {
        "revenue": q["revenue"].to_numpy(float),
        "cash_like": (q["cash"] + q["short_investments"].fillna(0)).to_numpy(float),
    }
    ets = {
        "revenue": _ets_samples(series["revenue"], H_FC, log=True, seasonal=True),
        "cash_like": _ets_samples(series["cash_like"], H_FC, log=False, seasonal=False),
    }
    for var, key in (("revenue", "revenue"), ("cash_like", "cash")):
        for h in range(H_FC):
            y = float(real[var].iloc[h])
            if not np.isfinite(y):
                continue
            mu_b, sd_b = _baseline(q, var, h + 1)
            e = ets[var]
            rows.append(
                {
                    "origin": origin,
                    "var": var,
                    "h": h + 1,
                    "scale": _f(scale),
                    "crps_twin": crps_samples(out[key][:, h], y),
                    "crps_rw": crps_gaussian(mu_b, sd_b, y),
                    "crps_ets": crps_samples(e[h], y) if e is not None else None,
                    "pit_ets": float(np.mean(e[h] <= y)) if e is not None else None,
                }
            )
    return rows


def company(ticker: str) -> dict:
    is_bk = "~" in ticker
    full_data = None if is_bk else load_company(ticker)
    res: dict = {"ticker": ticker, "bankrupt_2020": is_bk, "errors": {}}
    try:
        res["covid"] = covid(ticker, None if full_data is None else full_data.quarters)
    except Exception as e:
        res["errors"]["covid"] = f"{type(e).__name__}: {e}"
    if full_data is None:
        return res
    hists: dict[str, CompanyData] = {}
    for origin in FORECAST_ORIGINS:
        try:
            hists[origin] = load_company(ticker, asof=origin)
        except Exception as e:
            res["errors"][origin] = f"{type(e).__name__}: {e}"
    panel = []
    for origin in PANEL_ORIGINS:
        hist = hists.get(origin)
        if hist is None or len(hist.quarters) < 16:
            continue
        try:
            p = calibrate(hist, macro_quarterly(origin), 12)
            raw = {**p, "sector_tol": 1.0}
            panel.append(
                {
                    "origin": origin,
                    "base": _run(raw, {}, {}, 1500, 12, 5),
                    "recession": _run(raw, PRESETS["recession"]["knobs"], {}, 1500, 12, 5),
                    "base_no_loops": _run(raw, {}, ABLATIONS["no_loops"], 1500, 12, 5),
                    "features": features(hist, p),
                    "outcome": _distress(hist, full_data.quarters),
                }
            )
        except Exception as e:
            res["errors"][f"panel {origin}"] = f"{type(e).__name__}: {e}"
    res["panel"] = panel
    try:
        res["forecasts"] = forecasts(ticker, full_data, hists)
    except Exception as e:
        res["errors"]["forecasts"] = f"{type(e).__name__}: {e}"
    return res

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
from ..model.ratings import rating_rank, spreads_asof
from ..model.sd_model import simulate
from ..scenarios.presets import DEFAULT_LEVERS, PRESETS, build_scenario
from ..stochastic.calibrate import SPECIFIED_FIXED_SHARE_PRIOR
from ..stochastic.calibrate import calibrate as _calibrate
from ..stochastic.mc import summarize
from ..stochastic.shocks import draw_shocks
from ..universe import classify

COVID_CUT = "2020-02-20"
PANEL_ORIGINS = [f"{y}-02-15" for y in range(2013, 2025)]
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
DEPTHS = (0.0, 0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.8)
DEMAND = {"sales_duration": 3, "sales_recovery": 8, "spread_bp": 200, "spread_duration": 4}


def data_vintage(cik: int) -> dict:
    """Which data the run used: the hash of the cached companyfacts file and the filings read by the XBRL fallback."""
    import hashlib

    from ..data import edgar
    from ..data.facts import company_facts

    path = edgar.CACHE_DIR / f"companyfacts_{cik:010d}.json.gz"
    raw = company_facts(cik)
    return {
        "facts_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
        "xbrl_fallback": list(raw.get("_fallback", [])),
    }


def calibrate(hist: CompanyData, macro: pd.DataFrame, horizon: int = 12, assumptions: dict | None = None) -> dict:
    """Calibration with the rating-spread table that was published at the cutoff (the product uses January 2026's)."""
    # research runs keep the pre-specified 35% prior; the revised value is selected walk-forward in `plan2`
    p = _calibrate(hist, macro, horizon, {"fixed_share_prior": SPECIFIED_FIXED_SHARE_PRIOR, **(assumptions or {})})
    pit = spreads_asof(hist.asof)
    if pit is not None:
        p["spreads"] = pit
    return p


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def usable(hist: CompanyData, asof: str) -> bool:
    """16 quarters of history, and a company that was still filing: the last known quarter is recent.

    Without the second condition a company that stopped filing in 2016 would enter a 2019 cutoff with stale data.
    """
    q = hist.quarters
    return len(q) >= 16 and (pd.Timestamp(asof) - q.index[-1]).days <= 200


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
    if not usable(hist, COVID_CUT):
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
    out["structural"] = structural(hist, raw, full, macro_quarterly(COVID_CUT)) if full is not None else {}
    # the stress score under a demand freeze of each depth: `stats` evaluates it at the company's industry shock
    out["depth_grid"] = {f"{d:.2f}": _run(raw, {**FREEZE, "sales_depth": d}, {}, 1000, 8, 7)["health"] for d in DEPTHS}
    return out


# Judgement calls varied in the sensitivity analysis: calibration assumptions (`calib`) and model assumptions (`p`).
SENSITIVITY: dict[str, dict] = {
    "revolver_low": {"calib": {"revolver_share": 0.04}},
    "revolver_high": {"calib": {"revolver_share": 0.15}},
    "fixed_prior_low": {"calib": {"fixed_share_prior": 0.20}},
    "fixed_prior_high": {"calib": {"fixed_share_prior": 0.50}},
    "prior_weak": {"calib": {"prior_weight": 0.5}},
    "prior_strong": {"calib": {"prior_weight": 8.0}},
    "no_shrinkage": {"calib": {"growth_shrink": 1.0, "beta_shrink": 1.0}},
    # grid of fixed-cost priors (weight 2, as specified) and the unshrunk estimate, from which `stats` selects a revised
    # specification walk-forward, globally and by industry
    **{
        f"prior_share_{int(x * 100):02d}": {"calib": {"fixed_share_prior": x}}
        for x in (0.05, 0.10, 0.15, 0.25, 0.30, 0.45)
    },
    "prior_none": {"calib": {"prior_weight": 0.0}},
    "access_strict": {"p": {"access_icr": (2.5, 1.5)}},
    "access_lenient": {"p": {"access_icr": (1.0, 0.5), "access_levels": (0.8, 0.5)}},
    "cuts_fast": {"p": {"cut_delay": 1, "cut_speed": 0.08, "cut_floor": 0.75}},
    "spreads_2026": {"p": {}},  # the product's January 2026 rating table instead of the table published at the cutoff
    "spreads_baa": {"p": {}},  # the 2026 table rescaled by the Baa spread known at the cutoff
}
EVENTS = ("cash_half", "debt_raise", "div_cut", "capex_cut")


def _spread_scale(asof: str) -> float:
    """Rating spreads are Damodaran's January 2026 table; rescale them by the Baa-Treasury spread known at `asof`."""
    from ..data.fred import fred_series

    s = fred_series("BAA10Y")
    ref = float(s[(s.index >= "2025-12-01") & (s.index <= "2026-01-31")].mean())
    now = float(s[s.index <= pd.Timestamp(asof)].tail(63).mean())
    return float(np.clip(now / ref, 0.5, 3.0)) if np.isfinite(now) and ref > 0 else 1.0


def _margin(pre: pd.DataFrame, cash: pd.Series, k: int) -> float:
    c, r = cash.tail(k), pre["revenue"].tail(k)
    if c.notna().sum() < k or r.notna().sum() < k or r.sum() <= 0:
        return np.nan
    return float(c.sum() / r.sum())


def _cash_rule(pre: pd.DataFrame, cash: pd.Series, dynamic: bool) -> np.ndarray | None:
    """Per-company regression of quarterly cash flow on revenue (and its change) over the last 16 quarters.

    The static version is operating leverage without simulation (cash = a + b * revenue, i.e. a fixed and a
    variable part); the dynamic version adds working-capital timing (cash also responds to the change in revenue).
    """
    d = pd.DataFrame({"rev": pre["revenue"], "y": cash})
    d["drev"] = d["rev"].diff()
    d = d.dropna().tail(16)
    if len(d) < 12:
        return None
    X = np.column_stack([np.ones(len(d)), d["rev"], *([d["drev"]] if dynamic else [])])
    return np.linalg.lstsq(X, d["y"].to_numpy(float), rcond=None)[0]


def _apply_rule(beta: np.ndarray | None, rev: np.ndarray, rev_prev: float) -> np.ndarray:
    if beta is None:
        return np.full(len(rev), np.nan)
    out = beta[0] + beta[1] * rev
    if len(beta) == 3:
        out = out + beta[2] * np.diff(np.concatenate([[rev_prev], rev]))
    return out


def _probs(sim: dict, p: dict, n_q: int, rev_ttm: float, capex_pre: float) -> dict:
    """Share of simulated paths on which each liquidity event happens (same definitions as the realized events)."""
    cash = sim["cash"][:, :n_q]
    debt = (sim["debt"] + sim["revolver"])[:, :n_q]
    div4, capex4 = sim["dividends"][:, :4].sum(1), sim["capex"][:, :4].sum(1)
    raise_ = (debt - p["debt0"]) / rev_ttm
    out: dict = {
        "cash_half": float(np.mean(cash.min(1) < 0.5 * p["cash0"])) if p["cash0"] > 0 else None,
        "debt_raise": float(np.mean(raise_.max(1) > 0.05)),
        "div_cut": float(np.mean(div4 < 0.5 * 4 * p["div_q"])) if p["div_q"] > 0 else None,
        "capex_cut": float(np.mean(capex4 < 0.75 * capex_pre)) if capex_pre > 0 else None,
    }
    # the same events at other thresholds, and when they happen (cumulative probability by quarter)
    out["grid"] = {
        "cash": {f"{x}": float(np.mean(cash.min(1) < x * p["cash0"])) for x in (0.3, 0.5, 0.7)}
        if p["cash0"] > 0
        else {},
        "debt": {f"{x}": float(np.mean(raise_.max(1) > x)) for x in (0.03, 0.05, 0.10)},
        "div": {f"{x}": float(np.mean(div4 < (1 - x) * 4 * p["div_q"])) for x in (0.25, 0.5)} if p["div_q"] > 0 else {},
        "capex": {f"{x}": float(np.mean(capex4 < (1 - x) * capex_pre)) for x in (0.25, 0.5)} if capex_pre > 0 else {},
    }
    out["timing"] = {
        "cash_half": [float(np.mean((cash[:, : k + 1] < 0.5 * p["cash0"]).any(1))) for k in range(n_q)]
        if p["cash0"] > 0
        else None,
        "debt_raise": [float(np.mean((raise_[:, : k + 1] > 0.05).any(1))) for k in range(n_q)],
    }
    return out


def structural(hist: CompanyData, p: dict, full: pd.DataFrame, macro: pd.DataFrame | None = None, n_q: int = 8) -> dict:
    """Feed the revenue that actually followed the cutoff into the twin and compare its cash response with reality.

    Predicting *which* shock hits a company is the scenario's job; translating a given revenue path into cash is
    the simulation's job. This isolates the second. Every rival sees the same realized revenue, quarter by quarter:
    trailing cash-flow margins over 4, 8 and 16 quarters (the sector-shrunk margin is built in `stats`), and two
    per-company regressions of cash flow on revenue, without and with working-capital timing. Paths are stored as
    % of trailing revenue, so totals, worst cumulative values and further rules can be computed downstream.

    The same run yields the liquidity decisions a risk user cares about (cash halves, new borrowing, dividend and
    capex cuts) for the twin, each loop ablation, a static runway calculation with the same inputs, and reality.
    """
    pre = hist.quarters
    nxt = full[full.index > pre.index[-1] + pd.Timedelta(days=20)].head(n_q)
    rev_ttm = _ttm(pre, "revenue")
    if len(nxt) < n_q or nxt["revenue"].isna().any() or not np.isfinite(rev_ttm) or rev_ttm <= 0:
        return {}
    rev = nxt["revenue"].to_numpy(float)
    cfo, capex = nxt["cfo"].to_numpy(float), nxt["capex"].to_numpy(float)
    if not (np.isfinite(cfo).all() and np.isfinite(capex).all()):
        return {}
    T = int(p["horizon"])
    scn = build_scenario({}, T)
    override = np.full(T, np.nan)
    override[:n_q] = rev
    scn["revenue_override"] = override
    eps = draw_shocks(p, 500, T, seed=3)

    def pc(x) -> list[float]:
        return [round(float(v) / rev_ttm * 100, 4) for v in x]

    pre_cfo, pre_fcf = pre["cfo"], pre["cfo"] - pre["capex"]
    capex_pre = float(pre["capex"].tail(4).sum())
    ebitda_real = (nxt["operating_income"] + nxt["da"].fillna(0)).to_numpy(float)
    out: dict = {
        "rev": pc(rev),
        "real_cfo": pc(cfo),
        "real_fcf": pc(cfo - capex),
        "real_ebitda": pc(ebitda_real) if np.isfinite(ebitda_real).all() else None,
        "real_capex": pc(capex),
        "m": {f"{n}{k}": _f(_margin(pre, c, k)) for n, c in (("cfo", pre_cfo), ("fcf", pre_fcf)) for k in (4, 8, 16)},
    }
    rev_prev = float(pre["revenue"].iloc[-1])
    for name, cash in (("cfo", pre_cfo), ("fcf", pre_fcf)):
        out[f"ols_{name}"] = pc(_apply_rule(_cash_rule(pre, cash, False), rev, rev_prev))
        out[f"dyn_{name}"] = pc(_apply_rule(_cash_rule(pre, cash, True), rev, rev_prev))
    probs = {}
    for k, lv in ABLATIONS.items():
        sim = simulate(p, scn, eps, {**DEFAULT_LEVERS, **lv})
        probs[k] = _probs(sim, p, n_q, rev_ttm, capex_pre)
        if k in ("full", "no_loops"):
            tag = "twin" if k == "full" else "noloops"
            out[f"{tag}_cfo"] = pc(np.median(sim["cfo"][:, :n_q], axis=0))
            out[f"{tag}_fcf"] = pc(np.median(sim["fcf"][:, :n_q], axis=0))
            if k == "full":
                out["twin_ebitda"] = pc(np.median(sim["ebitda"][:, :n_q], axis=0))
                out["twin_capex"] = pc(np.median(sim["capex"][:, :n_q], axis=0))
    out["probs"] = probs

    # realized liquidity decisions
    cash_like = (nxt["cash"] + nxt["short_investments"].fillna(0)).to_numpy(float)
    debt = nxt["total_debt"].to_numpy(float)
    div_pre = float(pre["dividends"].tail(4).fillna(0).sum())
    out["events"] = {
        "cash_half": bool(np.nanmin(cash_like) < 0.5 * p["cash0"])
        if p["cash0"] > 0 and np.isfinite(cash_like).any()
        else None,
        "debt_raise": bool((np.nanmax(debt) - p["debt0"]) / rev_ttm > 0.05) if np.isfinite(debt).any() else None,
        "div_cut": bool(nxt["dividends"].head(4).fillna(0).sum() < 0.5 * div_pre) if div_pre > 0 else None,
        "capex_cut": bool(capex[:4].sum() < 0.75 * capex_pre) if capex_pre > 0 else None,
    }

    def first(mask: np.ndarray) -> int | None:
        hit = np.flatnonzero(mask)
        return int(hit[0]) + 1 if len(hit) else None

    raise_real = (debt - p["debt0"]) / rev_ttm
    out["realized_cont"] = {
        "cash_min_ratio": _f(np.nanmin(cash_like) / p["cash0"])
        if p["cash0"] > 0 and np.isfinite(cash_like).any()
        else None,
        "debt_raise_ratio": _f(np.nanmax(raise_real)) if np.isfinite(debt).any() else None,
        "div_ratio": _f(nxt["dividends"].head(4).fillna(0).sum() / div_pre) if div_pre > 0 else None,
        "capex_ratio": _f(capex[:4].sum() / capex_pre) if capex_pre > 0 else None,
        "t_cash_half": first(cash_like < 0.5 * p["cash0"]) if p["cash0"] > 0 else None,
        "t_debt_raise": first(np.nan_to_num(raise_real, nan=-1) > 0.05),
    }
    # an analyst's static runway with the same inputs: the trailing FCF margin on the realized revenue, minus the
    # current dividend and buyback run-rate and the maturities the company does not usually refinance
    fcf_m = out["m"]["fcf4"]
    if fcf_m is not None:
        payout_q = div_pre / 4 + float(pre["buybacks"].tail(4).fillna(0).sum()) / 4
        mat = np.asarray(p["maturities_q"][:n_q], float) * (1 - p["refi_ratio"])
        path = p["cash0"] + np.cumsum(fcf_m * rev - payout_q - mat)
        fcf4 = fcf_m * rev[:4].sum()
        out["static"] = {
            "cash_min": _f(path.min() / max(p["cash0"], 1e-9)),
            "fin_need": _f(max(p["cash_target"] - path.min(), 0.0) / rev_ttm * 100),
            "div_pressure": _f(min(div_pre / fcf4, 50.0)) if fcf4 > 0 else 50.0,
            "rev4": _f(rev[:4].sum() / rev_ttm),
        }

    # sensitivity of the transmission result and of the baseline verdict to the model's judgement calls
    if macro is not None:
        sens = {}
        for name, var in SENSITIVITY.items():
            try:
                pv = calibrate(hist, macro, T, var["calib"]) if "calib" in var else dict(p)
                pv = {**pv, "sector_tol": 1.0, **var.get("p", {})}
                if name in ("spreads_2026", "spreads_baa"):
                    pv.pop("spreads", None)
                if name == "spreads_baa":
                    pv["spread_scale"] = _spread_scale(str((pre.index[-1] + pd.Timedelta(days=45)).date()))
                sim = simulate(pv, scn, draw_shocks(pv, 500, T, seed=3), DEFAULT_LEVERS)
                base = simulate(pv, build_scenario({}, T), draw_shocks(pv, 1000, T, seed=5), DEFAULT_LEVERS)
                sens[name] = {
                    "cfo": pc(np.median(sim["cfo"][:, :n_q], axis=0)),
                    "fcf": pc(np.median(sim["fcf"][:, :n_q], axis=0)),
                    "probs": _probs(sim, pv, n_q, rev_ttm, capex_pre),
                    "health": summarize(base)["health_score"],
                }
            except Exception:  # a variant that cannot be calibrated is skipped, not fatal
                continue
        out["sens"] = sens
    return out


def _cumulative(pre: pd.DataFrame, window: pd.DataFrame, rev_ttm: float) -> tuple[float, float]:
    """Cumulative FCF over the window and its excess over the pre-cutoff run-rate, % of trailing revenue.

    Worst cumulative values (`_abnormal_burn`, `burn`) are drawdowns: for a firm with positive cash flow they equal the
    first quarter. For rank correlations the whole window is the better continuous outcome.
    """
    run_rate = (_ttm(pre, "cfo") - _ttm(pre, "capex")) / 4
    fcf = window["cfo"] - window["capex"]
    total = float(fcf.fillna(0).sum() / rev_ttm * 100)
    if not np.isfinite(run_rate):
        return total, np.nan
    return total, float((fcf.fillna(run_rate) - run_rate).sum() / rev_ttm * 100)


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
    cum, abn_cum = _cumulative(pre, win, rev_ttm)
    return {
        "burn": _f(fcf.min() / rev_ttm * 100),
        "abn_burn": _f(_abnormal_burn(pre, win, rev_ttm)),
        "cum_fcf": _f(cum),
        "abn_cum_fcf": _f(abn_cum),
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
        "cum8": _f(_cumulative(pre, nxt, rev_ttm)[0]),
        "abn_cum8": _f(_cumulative(pre, nxt, rev_ttm)[1]),
        "abn_burn8": _f(_abnormal_burn(pre, nxt, rev_ttm)),
        "icr0": _f(icr0),
        "icr_min": _f(icr.min()) if len(icr) else None,
        "div_payer": bool(div_pre > 0),
        "div_cut": bool(div_pre > 0 and div_post < 0.5 * div_pre),
        "rev_drop8": _f((nxt["revenue"] / both["revenue"].shift(4).reindex(nxt.index) - 1).min() * 100),
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
        if hist is None or not usable(hist, origin):
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
                    # for conditional coverage: the realized value, the twin's quantiles and the quarter forecast
                    "y": y,
                    "q": [float(v) for v in np.percentile(out[key][:, h], [5, 25, 50, 75, 95])],
                    "pit_twin": float(np.mean(out[key][:, h] <= y)),
                    "target": str(real.index[h].date()),
                    "rw_mu": _f(mu_b),
                    "rw_sd": _f(sd_b),
                }
            )
    return rows


def company(ticker: str, with_forecasts: bool = True) -> dict:
    """All designs for one company. `ticker` is a ticker, a ``CIK0000012345`` key or a legacy ``XXX~2020`` key."""
    is_bk = "~" in ticker
    full_data = None if is_bk else load_company(ticker)
    res: dict = {
        "ticker": ticker,
        "cik": int(full_data.cik) if full_data else None,
        "bankrupt_2020": is_bk,
        "errors": {},
    }
    if full_data is not None:
        res["data"] = data_vintage(int(full_data.cik))
    try:
        res["covid"] = covid(ticker, None if full_data is None else full_data.quarters)
    except Exception as e:
        res["errors"]["covid"] = f"{type(e).__name__}: {e}"
    if full_data is None:
        return res
    hists: dict[str, CompanyData] = {}
    for origin in FORECAST_ORIGINS if with_forecasts else PANEL_ORIGINS:
        try:
            hists[origin] = load_company(ticker, asof=origin)
        except Exception as e:
            res["errors"][origin] = f"{type(e).__name__}: {e}"
    panel = []
    for origin in PANEL_ORIGINS:
        hist = hists.get(origin)
        if hist is None or not usable(hist, origin):
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
                    "structural": structural(hist, raw, full_data.quarters, macro_quarterly(origin)),
                    # stress score under a generic demand shock of each depth (no market closure), so that `stats`
                    # can give each firm its industry's realized shock in any episode (2015-16, 2020, 2022)
                    "depth_grid": {
                        f"{d:.2f}": _run(raw, {**DEMAND, "sales_depth": d}, {}, 1000, 12, 7)["health"] for d in DEPTHS
                    },
                }
            )
        except Exception as e:
            res["errors"][f"panel {origin}"] = f"{type(e).__name__}: {e}"
    res["panel"] = panel
    if not with_forecasts:
        return res
    try:
        res["forecasts"] = forecasts(ticker, full_data, hists)
    except Exception as e:
        res["errors"]["forecasts"] = f"{type(e).__name__}: {e}"
    return res

"""Statistics for the paper: merges per-company research runs into docs/paper/research.json.

Conventions. Every predictor is oriented as a *risk* score (higher = more fragile) before it is compared, so a
positive Spearman correlation with realized cash-burn severity, or an AUC above 0.5, always means "useful".
Confidence intervals come from bootstraps that resample *firms* (the panel has repeated firm-years).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

OUT = Path(__file__).resolve().parents[3] / "docs" / "paper" / "research.json"
DATA = Path(__file__).resolve().parents[1] / "data"
MIN_LOG_REV = float(np.log(50e6))  # $50M trailing revenue at the cutoff
B = 2000
B_PANEL = 500  # firm-clustered panel bootstraps are slower
RNG = np.random.default_rng(20200220)

# name -> (column, sign): risk = sign * value
BENCH = {
    "altman_z2": ("z2", -1),
    "ohlson_o": ("o_score", 1),
    "zmijewski": ("zmijewski", 1),
    "nd_ebitda": ("nd_ebitda", 1),
    "icr": ("icr", -1),
    "cash_rev": ("cash_rev", -1),
    "current_ratio": ("current_ratio", -1),
    "static_stress": ("static_cover", -1),
    "rev_vol": ("rev_vol", 1),
    "fixed_share": ("fixed_share", 1),
    "size": ("log_rev", -1),
    "fcf_margin": ("fcf_margin", -1),
    "capex_rev": ("capex_rev", 1),
}
LABELS = {
    "twin": "Twin (stress health)",
    "twin_pb": "Twin (breach probability)",
    "altman_z2": "Altman Z$''$",
    "ohlson_o": "Ohlson O",
    "zmijewski": "Zmijewski",
    "nd_ebitda": "Net debt / EBITDA",
    "icr": "Interest coverage",
    "cash_rev": "Cash / revenue",
    "current_ratio": "Current ratio",
    "static_stress": "Static stress test",
    "rev_vol": "Revenue volatility",
    "fixed_share": "Fixed-cost share",
    "size": "Size (revenue)",
    "fcf_margin": "Trailing FCF margin",
    "capex_rev": "Capex / revenue",
    "formula": "Health formula, no simulation",
    "twin_base": "Twin (baseline health)",
}


# ---------------------------------------------------------------- helpers
def auc(score: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(score) & np.isfinite(y)
    s, t = score[m], y[m].astype(bool)
    n1, n0 = t.sum(), (~t).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return float((r[t].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def rho(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    return float(spearmanr(a[m], b[m])[0]) if m.sum() > 5 else np.nan


def _clusters(firms: np.ndarray) -> list[np.ndarray]:
    codes = pd.factorize(firms)[0]
    order = np.argsort(codes, kind="stable")
    return np.split(order, np.flatnonzero(np.diff(codes[order])) + 1)


def boot(stat, cols: list[np.ndarray], firms: np.ndarray | None = None, b: int = B) -> np.ndarray:
    """Bootstrap a statistic of aligned arrays, resampling rows or whole firms."""
    n = len(cols[0])
    groups = _clusters(firms) if firms is not None else None
    out = np.empty(b)
    for k in range(b):
        if groups is None:
            idx = RNG.integers(0, n, n)
        else:
            pick = RNG.integers(0, len(groups), len(groups))
            idx = np.concatenate([groups[g] for g in pick])
        out[k] = stat(*(c[idx] for c in cols))
    return out


def ci(x: np.ndarray) -> list[float]:
    return [float(np.nanpercentile(x, 2.5)), float(np.nanpercentile(x, 97.5))]


def p_two_sided(x: np.ndarray) -> float:
    """Bootstrap p-value for H0: statistic = 0 (share of resamples on the other side of zero, doubled)."""
    x = x[np.isfinite(x)]
    return float(min(1.0, 2 * min((x <= 0).mean(), (x >= 0).mean()))) if len(x) else np.nan


def pct(x: np.ndarray) -> np.ndarray:
    """Percentile rank in [0, 1], NaN-preserving."""
    out = np.full(len(x), np.nan)
    m = np.isfinite(x)
    out[m] = (rankdata(x[m]) - 0.5) / m.sum()
    return out


def _col(df: pd.DataFrame, c: str) -> pd.Series:
    return df[c].astype(float) if c in df else pd.Series(np.nan, index=df.index)


def risk_frame(df: pd.DataFrame, twin_health: str, twin_pb: str | None = None) -> pd.DataFrame:
    """Risk-oriented predictors. `formula` is the twin's health formula on the opening balance sheet (no simulation),
    the control that separates what simulation adds from what the score's ingredients already know."""
    r = pd.DataFrame(index=df.index)
    r["twin"] = -df[twin_health].astype(float)
    if twin_pb:
        r["twin_pb"] = df[twin_pb].astype(float)
    r["formula"] = -_col(df, "health_t0")
    for k, (col, sign) in BENCH.items():
        r[k] = sign * _col(df, col)
    return r


def paired(stat, a: np.ndarray, b: np.ndarray, y: np.ndarray, firms: np.ndarray | None = None, b_: int = B) -> dict:
    """Paired bootstrap of stat(a, y) - stat(b, y) on the observations where both predictors exist."""
    m = np.isfinite(a) & np.isfinite(b) & np.isfinite(y)
    d = boot(lambda u, v, t: stat(u, t) - stat(v, t), [a[m], b[m], y[m]], None if firms is None else firms[m], b=b_)
    return {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d), "n": int(m.sum())}


def _cv_composite(R: pd.DataFrame, sector: pd.Series, y: np.ndarray, k: int = 10) -> np.ndarray:
    """Out-of-fold predictions of y from the percentile ranks of the predictors in R plus sector effects."""
    X = pd.DataFrame({c: pct(R[c].to_numpy(float)) for c in R.columns}, index=R.index).fillna(0.5)
    X = pd.concat([X, pd.get_dummies(sector, drop_first=True, dtype=float)], axis=1)
    X.insert(0, "const", 1.0)
    A, n = X.to_numpy(float), len(X)
    fold = np.random.default_rng(7).permutation(n) % k
    pred = np.full(n, np.nan)
    for f in range(k):
        tr, te = fold != f, fold == f
        beta = np.linalg.lstsq(A[tr], y[tr], rcond=None)[0]
        pred[te] = A[te] @ beta
    return pred


def resid_on_sector(x: np.ndarray, sector: np.ndarray) -> np.ndarray:
    s = pd.Series(x)
    return (s - s.groupby(sector).transform("mean")).to_numpy()


# ---------------------------------------------------------------- loading
def membership() -> dict[str, dict[int, str]]:
    """CIK -> GICS sector for today's S&P 500 sample and the 20 February 2020 constituents; legacy 2020 sample."""
    out: dict[str, dict[int, str]] = {}
    for name, f in (("sp_today", "universe_sp500.csv"), ("sp2020", "sp500_2020-02-20.csv")):
        d = pd.read_csv(DATA / f).dropna(subset=["cik"])
        out[name] = dict(zip(d["cik"].astype(int), d["sector"], strict=True))
    bk = pd.read_csv(DATA / "bankruptcies_2020.csv")
    out["legacy_bk"] = dict(zip(bk["cik"].astype(int), bk["sector"], strict=True))
    return out


def bankruptcy_dates() -> dict[int, list[pd.Timestamp]]:
    """CIK -> filing dates of every 8-K with Item 1.03 (Chapter 11 / 7 petitions), from the EDGAR census."""
    f = DATA / "universe_edgar.csv"
    if not f.exists():
        return {}
    u = pd.read_csv(f, dtype={"bankruptcy_8k": str})
    return {
        int(c): [pd.Timestamp(x) for x in str(d).split(";")]
        for c, d in zip(u["cik"], u["bankruptcy_8k"], strict=True)
        if isinstance(d, str) and d
    }


def bk_event(dates: list[pd.Timestamp], origin: str, days: int = 730) -> float:
    """1 if a bankruptcy 8-K follows the cutoff within `days`; NaN if one was filed in the two years before it."""
    o = pd.Timestamp(origin)
    if any(o - pd.Timedelta(days=730) < d <= o for d in dates):
        return np.nan
    return float(any(o < d <= o + pd.Timedelta(days=days) for d in dates))


def load(cache: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    xs, panel, fc, errors = [], [], [], {}
    mem, bkd = membership(), bankruptcy_dates()
    for f in sorted(cache.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r.get("errors"):
            errors[r["ticker"]] = r["errors"]
        cik = r.get("cik")
        flags = {k: (cik in v) if cik is not None else False for k, v in mem.items()}
        gics = next((v[cik] for v in mem.values() if cik in v), None)
        dates = bkd.get(cik, []) if cik is not None else []
        c = r.get("covid")
        if c:
            row = {
                "ticker": c["ticker"],
                "cik": cik,
                "name": c["name"],
                "sector": c["sector"] or "Unknown",
                "gics": gics,
                "bankrupt": r.get("bankrupt_2020", False),
                **flags,
                "bk_2020": bk_event(dates, "2020-02-20", 680),  # filings to the end of 2021
            }
            row |= {f"grid_{k}": v for k, v in (c.get("depth_grid") or {}).items()}
            row["st"] = c.get("structural") or {}
            row |= {f"h_{k}": v["health"] for k, v in c["scenarios"].items()}
            row |= {f"pb_{k}": v["p_breach"] for k, v in c["scenarios"].items()}
            row |= {f"abl_{k}": v["health"] for k, v in c["ablations"].items()}
            row |= {f"ablpb_{k}": v["p_breach"] for k, v in c["ablations"].items()}
            for k, v in (c.get("ablations_h12") or {}).items():
                row |= {f"abl12_{k}": v["health"], f"abl12pb_{k}": v["p_breach"]}
            row["h_sector_adj"] = c["sector_adjusted"]["health"]
            row |= c["features"]
            row |= {f"real_{k}": v for k, v in (c.get("realized") or {}).items()}
            xs.append(row)
        for pr in r.get("panel", []):
            row = {
                "ticker": r["ticker"],
                "cik": cik,
                "year": int(pr["origin"][:4]),
                "industry": (c or {}).get("sector") or _industry(r["ticker"]),
                **flags,
                "y_bk8": bk_event(dates, pr["origin"]),
                "y_bk4": bk_event(dates, pr["origin"], 365),
                "st": pr.get("structural") or {},
            }
            row |= {
                "h_base": pr["base"]["health"],
                "pb_base": pr["base"]["p_breach"],
                "h_rec": pr["recession"]["health"],
                "h_base_no_loops": pr.get("base_no_loops", {}).get("health", np.nan),
            }
            row |= pr["features"]
            row |= {f"y_{k}": v for k, v in (pr.get("outcome") or {}).items()}
            panel.append(row)
        for fr in r.get("forecasts", []):
            fc.append({"ticker": r["ticker"], **fr})
    xs, panel = pd.DataFrame(xs), pd.DataFrame(panel)
    if "log_rev" in panel:  # point-in-time size screen: $50M trailing revenue at the cutoff
        panel = panel[panel["log_rev"].astype(float) >= MIN_LOG_REV].reset_index(drop=True)
    return xs, panel, pd.DataFrame(fc), errors


def _industry(key: str) -> str:
    from ..universe import classify

    try:
        return classify(key)[0] or "Unknown"
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------- COVID cross-section
def covid_section(xs: pd.DataFrame, outcome: str = "real_burn") -> dict:
    """outcome: `real_burn` (raw worst cumulative FCF) or `real_abn_burn` (relative to the pre-2020 run-rate).

    `xs` is the sample to use (the EDGAR universe alive on the cutoff, or the S&P 500 of that day, or today's)."""
    sp = xs[xs[outcome].notna()].reset_index(drop=True)
    sev = -sp[outcome].to_numpy(float)  # positive = more cash burned
    severe = (sp[outcome] < -10).to_numpy(float)
    R = risk_frame(sp, "h_pandemic", "pb_pandemic")
    sector = sp["sector"].to_numpy()
    out: dict = {"n": int(len(sp)), "n_severe": int(severe.sum())}

    R.insert(1, "twin_base", -sp["h_base"].astype(float))
    preds: dict[str, dict] = {}
    twin = R["twin"].to_numpy(float)
    for k in R.columns:
        x = R[k].to_numpy(float)
        if np.isfinite(x).sum() < 20:  # predictor not available in this run
            continue
        rs = rho(resid_on_sector(pct(x), sector), resid_on_sector(pct(sev), sector))
        preds[k] = {
            "label": LABELS[k],
            "n": int(np.isfinite(x).sum()),
            "rho": rho(x, sev),
            "rho_ci": ci(boot(rho, [x, sev])),
            "auc_severe": auc(x, severe),
            "rho_within_sector": rs,
            "twin_minus": None if k == "twin" else paired(rho, twin, x, sev),
        }
    out["predictors"] = preds
    out["within_sector_ci_twin"] = ci(
        boot(lambda a, b, s: rho(resid_on_sector(pct(a), s), resid_on_sector(pct(b), s)), [twin, sev, sector])
    )
    bench_avail = [k for k in BENCH if k in preds]
    best = max(bench_avail, key=lambda k: preds[k]["rho"])
    out["best_benchmark"] = best
    out["baseline_minus_best"] = paired(rho, R["twin_base"].to_numpy(float), R[best].to_numpy(float), sev)

    # a fitted composite of all benchmarks (10-fold cross-validated, sector effects), the fair "all ratios" rival
    comp = _cv_composite(R[bench_avail], sp["sector"], pct(sev))
    comp_f = _cv_composite(R[[*bench_avail, "formula"]], sp["sector"], pct(sev)) if "formula" in preds else comp
    out["composite"] = {
        "rho": rho(comp, sev),
        "rho_with_formula": rho(comp_f, sev),
        "twin_minus": paired(rho, twin, comp, sev),
        "twin_minus_with_formula": paired(rho, twin, comp_f, sev),
    }

    # incremental value: rank regression of burn severity on the twin, the no-simulation formula and all benchmarks
    import statsmodels.api as sm

    cols = ["twin", *(["formula"] if "formula" in preds else []), *bench_avail]
    X = pd.DataFrame({k: pct(R[k].to_numpy(float)) for k in cols}).fillna(0.5)  # missing -> median rank
    fe = pd.get_dummies(sp["sector"], drop_first=True, dtype=float)
    yv = pct(sev)
    full = sm.OLS(yv, sm.add_constant(pd.concat([X, fe], axis=1))).fit(cov_type="HC3")
    restr = sm.OLS(yv, sm.add_constant(pd.concat([X.drop(columns="twin"), fe], axis=1))).fit(cov_type="HC3")
    out["regression"] = {
        "coef": {k: float(full.params[k]) for k in X.columns},
        "t": {k: float(full.tvalues[k]) for k in X.columns},
        "p": {k: float(full.pvalues[k]) for k in X.columns},
        "r2_full": float(full.rsquared),
        "r2_without_twin": float(restr.rsquared),
        "n": int(full.nobs),
    }

    # robustness: drop capex-heavy utilities
    subsets = {"without_utilities": (sp["sector"] != "Utilities").to_numpy()}
    out["robustness"] = {}
    for name, keep in subsets.items():
        b_sub = max(bench_avail, key=lambda k: rho(R[k].to_numpy(float)[keep], sev[keep]))
        out["robustness"][name] = {
            "n": int(keep.sum()),
            "rho_twin": rho(twin[keep], sev[keep]),
            "rho_baseline": rho(R["twin_base"].to_numpy(float)[keep], sev[keep]),
            "best_benchmark": b_sub,
            "rho_best": rho(R[b_sub].to_numpy(float)[keep], sev[keep]),
            "twin_minus_best": paired(rho, twin[keep], R[b_sub].to_numpy(float)[keep], sev[keep]),
        }

    # exposure: the twin ranks fragility; realized burn needs fragility AND a hit
    drop = sp["real_rev_drop"].to_numpy(float)
    hit = drop <= np.nanmedian(drop)
    out["exposure"] = {
        "median_rev_drop": float(np.nanmedian(drop)),
        "rho_hit": rho(twin[hit], sev[hit]),
        "rho_spared": rho(twin[~hit & np.isfinite(drop)], sev[~hit & np.isfinite(drop)]),
        "n_hit": int(hit.sum()),
        "auc_severe_hit": auc(twin[hit], severe[hit]),
    }
    inter = pd.DataFrame({"twin": pct(twin), "hit": pct(-drop)}).fillna(0.5)
    inter["twin_x_hit"] = inter["twin"] * inter["hit"]
    m = sm.OLS(yv, sm.add_constant(inter)).fit(cov_type="HC3")
    out["exposure"]["interaction"] = {k: {"coef": float(m.params[k]), "t": float(m.tvalues[k])} for k in inter.columns}

    # which scenario carries the signal; which loop matters
    out["by_scenario"] = {
        k: rho(-sp[f"h_{k}"].to_numpy(float), sev)
        for k in ("base", "rates_200", "sales_20", "recession", "pandemic", "credit_crunch")
    }
    abl = {}
    for k in ("full", "no_r1", "no_r2", "no_b1", "no_b2", "no_loops"):
        x = -sp[f"abl_{k}"].to_numpy(float)
        d = boot(lambda a, b, c: rho(a, c) - rho(b, c), [twin, x, sev]) if k != "full" else None
        abl[k] = {
            "rho": rho(x, sev),
            "auc_severe": auc(x, severe),
            "rho_pb": rho(sp[f"ablpb_{k}"].to_numpy(float), sev),
            "loss": None if d is None else {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)},
        }
    out["ablations"] = abl
    # breach probability is where the loops act: paired differences in rank correlation with burn severity
    pb_full = sp["ablpb_full"].to_numpy(float)
    out["ablations_pb_loss"] = {}
    for k in ("no_r1", "no_r2", "no_b1", "no_b2", "no_loops"):
        d = boot(lambda a, b, c: rho(a, c) - rho(b, c), [pb_full, sp[f"ablpb_{k}"].to_numpy(float), sev])
        out["ablations_pb_loss"][k] = {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)}
    if "abl12_full" in sp:
        h12 = {}
        full12, pb12 = -sp["abl12_full"].to_numpy(float), sp["abl12pb_full"].to_numpy(float)
        for k in ("full", "no_r1", "no_r2", "no_b1", "no_b2", "no_loops"):
            x, xp = -sp[f"abl12_{k}"].to_numpy(float), sp[f"abl12pb_{k}"].to_numpy(float)
            e: dict = {"rho": rho(x, sev), "rho_pb": rho(xp, sev)}
            if k != "full":
                d = boot(lambda a, b, c: rho(a, c) - rho(b, c), [full12, x, sev])
                dp = boot(lambda a, b, c: rho(a, c) - rho(b, c), [pb12, xp, sev])
                e["loss"] = {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)}
                e["loss_pb"] = {"diff": float(np.nanmean(dp)), "ci": ci(dp), "p": p_two_sided(dp)}
            h12[k] = e
        out["ablations_h12"] = h12
    d = boot(lambda a, b, c: rho(a, c) - rho(b, c), [twin, -sp["h_base"].to_numpy(float), sev])
    out["stress_minus_baseline"] = {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)}
    out["sector_adjusted_rho"] = rho(-sp["h_sector_adj"].to_numpy(float), sev)

    # secondary outcomes
    payer = sp["real_div_payer"].astype(bool).to_numpy()
    cut = sp["real_div_cut"].astype(float).to_numpy()
    out["dividend_cut"] = {
        "n_payers": int(payer.sum()),
        "n_cuts": int(cut[payer].sum()),
        "auc": {k: auc(R[k].to_numpy(float)[payer], cut[payer]) for k in R.columns},
    }
    out["debt_raise_rho"] = rho(twin, sp["real_debt_raise"].to_numpy(float))

    q = pd.qcut(pd.Series(twin).rank(method="first"), 5, labels=False).to_numpy()
    out["quintiles"] = {
        "severe_share": [float(severe[q == i].mean()) for i in range(5)],  # 0 = most robust
        "median_burn": [float(np.median(-sev[q == i])) for i in range(5)],
        "top_quintile_share_of_severe": float(severe[q == 4].sum() / max(severe.sum(), 1)),
    }
    z = R["altman_z2"].to_numpy(float)
    zq = pd.qcut(pd.Series(z).rank(method="first"), 5, labels=False).to_numpy()
    out["quintiles_altman"] = {"severe_share": [float(severe[(zq == i) & np.isfinite(z)].mean()) for i in range(5)]}
    keep = ["ticker", "name", "sector", "h_pandemic", "real_burn", "real_rev_drop", "real_abn_burn"]
    out["rows"] = sp[[c for c in keep if c in sp]].to_dict("records")
    return out


# ---------------------------------------------------------------- distress panel
def _events(p: pd.DataFrame) -> dict[str, np.ndarray]:
    icr0, icrmin = p["y_icr0"].to_numpy(float), p["y_icr_min"].to_numpy(float)
    cov = np.where(icr0 >= 1.5, (icrmin < 1.5).astype(float), np.nan)
    cov[~np.isfinite(icrmin)] = np.nan
    div = np.where(p["y_div_payer"].fillna(False).astype(bool), p["y_div_cut"].fillna(False).astype(float), np.nan)
    burn = p["y_burn8"].to_numpy(float)
    abn = _col(p, "y_abn_burn8").to_numpy(float)
    return {
        "severe_burn": np.where(np.isfinite(burn), (burn < -10).astype(float), np.nan),
        "abnormal_burn": np.where(np.isfinite(abn), (abn < -10).astype(float), np.nan),
        "coverage_collapse": cov,
        "dividend_cut": div,
        # Chapter 11 / 7 petition (8-K Item 1.03) within eight quarters, from the EDGAR census
        "bankruptcy": _col(p, "y_bk8").to_numpy(float),
    }


def _raw(p: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Feature sets: `health` is the twin's baseline health only; `twin` adds its baseline breach probability and its
    recession-scenario health; `formula` is the health formula on the opening balance sheet (no simulation)."""
    X = pd.DataFrame(index=p.index)
    for k in cols:
        if k == "health":
            X["h_base"] = -p["h_base"]
        elif k == "twin":
            X["h_base"], X["pb_base"], X["h_rec"] = -p["h_base"], p["pb_base"], -p["h_rec"]
        elif k == "formula":
            X["formula"] = -_col(p, "health_t0")
        else:
            col, sign = BENCH[k]
            X[k] = sign * _col(p, col)
    return X


def _design(X: pd.DataFrame, lo: pd.Series, hi: pd.Series, med: pd.Series) -> pd.DataFrame:
    X = X.clip(lo, hi, axis=1)
    for c in list(X.columns):
        X[c + "_na"] = X[c].isna().astype(float)
    return X.fillna(med)


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, ytr: np.ndarray, cols: list[str]) -> np.ndarray:
    import statsmodels.api as sm

    raw_tr, raw_te = _raw(train, cols), _raw(test, cols)
    lo, hi = raw_tr.quantile(0.01), raw_tr.quantile(0.99)  # winsorize with training-set limits only
    med = raw_tr.clip(lo, hi, axis=1).median()
    Xtr, Xte = _design(raw_tr, lo, hi, med), _design(raw_te, lo, hi, med)
    Xtr = Xtr.loc[:, Xtr.notna().all() & (Xtr.std() > 0)]  # drop features that are absent in this run
    Xte = Xte.reindex(columns=Xtr.columns, fill_value=0.0)
    mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
    Xtr, Xte = (Xtr - mu) / sd, (Xte - mu) / sd
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = sm.GLM(ytr, sm.add_constant(Xtr, has_constant="add"), family=sm.families.Binomial()).fit_regularized(
            alpha=0.01, L1_wt=0.0
        )
    return np.asarray(m.predict(sm.add_constant(Xte, has_constant="add")))


def panel_section(p: pd.DataFrame) -> dict:
    ev = _events(p)
    firms = p["ticker"].to_numpy()
    R = risk_frame(p, "h_base", "pb_base")
    R["twin_rec"] = -p["h_rec"].astype(float)
    R["twin_no_loops"] = -p["h_base_no_loops"].astype(float)
    out: dict = {
        "n_firm_years": int(len(p)),
        "n_firms": int(p["ticker"].nunique()),
        "years": sorted(p["year"].unique().tolist()),
    }
    for name, y in ev.items():
        m = np.isfinite(y)
        if m.sum() < 100:  # outcome not available in this run
            continue
        res: dict = {"n": int(m.sum()), "events": int(np.nansum(y)), "base_rate": float(np.nanmean(y))}
        uni = {}
        twin = R["twin"].to_numpy(float)
        for k in R.columns:
            x = R[k].to_numpy(float)
            sel = m & np.isfinite(x)
            if sel.sum() < 20:  # predictor not available in this run
                continue
            entry: dict = {"auc": auc(x[sel], y[sel]), "n": int(sel.sum())}
            if name in ("severe_burn", "abnormal_burn", "bankruptcy"):
                entry["auc_ci"] = ci(boot(auc, [x[sel], y[sel]], firms[sel], b=B_PANEL))
                if k != "twin":
                    entry["twin_minus"] = paired(auc, twin, x, y, firms, B_PANEL)
            uni[k] = entry
        res["univariate"] = uni
        res["auc_by_year"] = {
            k: {
                int(yr): auc(
                    R[k].to_numpy(float)[(p["year"] == yr).to_numpy() & m], y[(p["year"] == yr).to_numpy() & m]
                )
                for yr in out["years"]
            }
            for k in ("twin", "formula", "altman_z2", "icr", "fcf_margin", "static_stress")
            if k in uni
        }
        # out-of-sample logistic models: test year Y, train on origins <= Y-3 (their 8-quarter outcomes are known)
        bench = list(BENCH)
        models = {
            "benchmarks": bench,
            "benchmarks_plus_twin": [*bench, "twin"],
            "benchmarks_formula": [*bench, "formula"],
            "benchmarks_formula_health": [*bench, "formula", "health"],
            "benchmarks_formula_twin": [*bench, "formula", "twin"],
            "health_only": ["health"],
            "twin_only": ["twin"],
        }
        preds: dict[str, list] = {k: [] for k in models}
        ys, fs = [], []
        for yr in out["years"]:
            tr = (p["year"] <= yr - 3).to_numpy() & m
            te = (p["year"] == yr).to_numpy() & m
            if tr.sum() < 300 or te.sum() < 30 or np.nansum(y[tr]) < 10:
                continue
            for key, cols in models.items():
                preds[key].append(_fit_predict(p[tr], p[te], y[tr], cols))
            ys.append(y[te])
            fs.append(firms[te])
        if ys:
            yy, ff = np.concatenate(ys), np.concatenate(fs)
            P = {k: np.concatenate(v) for k, v in preds.items()}
            oos: dict = {}
            for k, v in P.items():
                oos[k] = {
                    "auc": auc(v, yy),
                    "brier": float(np.mean((v - yy) ** 2)),
                    "log_loss": float(
                        -np.mean(yy * np.log(np.clip(v, 1e-6, 1)) + (1 - yy) * np.log(np.clip(1 - v, 1e-6, 1)))
                    ),
                }
            oos["delta_auc_twin_added"] = paired(auc, P["benchmarks_plus_twin"], P["benchmarks"], yy, ff, B_PANEL)
            oos["delta_health_beyond_formula"] = paired(
                auc, P["benchmarks_formula_health"], P["benchmarks_formula"], yy, ff, B_PANEL
            )
            oos["delta_twin_beyond_formula"] = paired(
                auc, P["benchmarks_formula_twin"], P["benchmarks_formula"], yy, ff, B_PANEL
            )
            oos["n_test"] = int(len(yy))
            oos["test_years"] = [yr for yr in out["years"] if ((p["year"] <= yr - 3).to_numpy() & m).sum() >= 300]
            res["out_of_sample"] = oos
        # in-sample logit with firm-clustered errors: is the twin significant given every benchmark and year effects?
        res["clustered_logit"] = _clustered_logit(p[m], y[m])
        out[name] = res
    return out


def _clustered_logit(p: pd.DataFrame, y: np.ndarray) -> dict:
    import statsmodels.api as sm

    X = pd.DataFrame({k: pct(sign * _col(p, col).to_numpy(float)) for k, (col, sign) in BENCH.items()}, index=p.index)
    X.insert(0, "formula", pct(-_col(p, "health_t0").to_numpy(float)))
    X = X.loc[:, X.notna().any()].fillna(0.5)
    X.insert(0, "twin", pct(-p["h_base"].to_numpy(float)))
    yr = pd.get_dummies(p["year"], prefix="y", drop_first=True, dtype=float)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = sm.Logit(y, sm.add_constant(pd.concat([X, yr], axis=1))).fit(
                disp=False, cov_type="cluster", cov_kwds={"groups": pd.factorize(p["ticker"])[0]}
            )
        return {
            k: {"coef": float(m.params[k]), "z": float(m.tvalues[k]), "p": float(m.pvalues[k])} for k in X.columns
        } | {
            "pseudo_r2": float(m.prsquared),
            "n": int(m.nobs),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- forecast comparison
def forecast_section(fc: pd.DataFrame) -> dict:
    import statsmodels.api as sm

    out = {}
    for var, g in fc.groupby("var"):
        g = g[g["crps_ets"].notna() & g["scale"].gt(0)].copy()
        res: dict = {"n": int(len(g)), "n_firms": int(g["ticker"].nunique())}
        for base in ("rw", "ets"):
            c_t, c_b = g["crps_twin"] / g["scale"], g[f"crps_{base}"] / g["scale"]
            d = (c_t - c_b).to_numpy(float)
            # Diebold-Mariano style test on scaled CRPS differentials, with standard errors clustered two ways: by
            # firm (repeated forecasts) and by origin (common shocks such as 2020)
            firm_ids, origin_ids = pd.factorize(g["ticker"])[0], pd.factorize(g["origin"])[0]
            groups = np.column_stack([firm_ids, origin_ids]) if origin_ids.max() > 0 else firm_ids
            m = sm.OLS(d, np.ones(len(d))).fit(cov_type="cluster", cov_kwds={"groups": groups})
            res[base] = {
                "skill_pooled": float(1 - g["crps_twin"].sum() / g[f"crps_{base}"].sum()),
                "skill_scaled": float(1 - c_t.mean() / c_b.mean()),
                "share_better": float((g["crps_twin"] < g[f"crps_{base}"]).mean()),
                "dm_mean_diff": float(m.params[0]),
                "dm_t": float(m.tvalues[0]),
                "dm_p": float(m.pvalues[0]),
                "by_h": {
                    int(h): float(
                        1 - (gh["crps_twin"] / gh["scale"]).mean() / (gh[f"crps_{base}"] / gh["scale"]).mean()
                    )
                    for h, gh in g.groupby("h")
                },
            }
        res["ets_vs_rw_skill_scaled"] = float(
            1 - (g["crps_ets"] / g["scale"]).mean() / (g["crps_rw"] / g["scale"]).mean()
        )
        out[var] = res
    return out


def main(cache: Path) -> dict:
    from . import calibration, distress, transmission

    xs, panel, fc, errors = load(cache)
    xs = xs[xs["log_rev"].astype(float) >= MIN_LOG_REV].reset_index(drop=True) if "log_rev" in xs else xs
    samples = {
        "edgar": np.ones(len(xs), bool),
        "sp2020": xs["sp2020"].to_numpy(bool),
        "sp_today": xs["sp_today"].to_numpy(bool),
    }
    res: dict = {
        "n_files": len(list(cache.glob("*.json"))),
        "samples": {
            "covid": {k: int(v.sum()) for k, v in samples.items()},
            "panel_firm_years": int(len(panel)),
            "panel_firms": int(panel["ticker"].nunique()) if len(panel) else 0,
        },
        "covid": {k: covid_section(xs[v].reset_index(drop=True)) for k, v in samples.items() if v.sum() >= 30},
        "covid_abnormal": {
            k: covid_section(xs[v].reset_index(drop=True), "real_abn_burn") for k, v in samples.items() if v.sum() >= 30
        },
        "bankruptcy_2020": distress.bankruptcy_2020(xs, B),
        "bankruptcy_panel": distress.bankruptcy_panel(panel, B_PANEL),
        "exposure": distress.exposure(xs, B),
        "panel": panel_section(panel),
        "panel_sp": panel_section(sp.reset_index(drop=True)) if len(sp := panel[panel["sp_today"] | panel["sp2020"]]) >= 300 else {},
        "transmission": {
            "panel": transmission.section(panel, B_PANEL),
            "covid": transmission.section(xs, B, panel=False),
        },
        "forecasts": forecast_section(fc),
        "calibration": calibration.section(fc, panel),
        "errors": errors,
    }
    from ..export import _clean

    OUT.write_text(json.dumps(_clean(res), indent=1), encoding="utf-8")
    v = res["transmission"]["panel"].get("verdict", {})
    print(json.dumps(res["samples"]), "\nverdict:", json.dumps(v, default=str))
    return res

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
    return [np.flatnonzero(firms == f) for f in pd.unique(firms)]


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


def risk_frame(df: pd.DataFrame, twin_health: str, twin_pb: str | None = None) -> pd.DataFrame:
    r = pd.DataFrame(index=df.index)
    r["twin"] = -df[twin_health].astype(float)
    if twin_pb:
        r["twin_pb"] = df[twin_pb].astype(float)
    for k, (col, sign) in BENCH.items():
        r[k] = sign * df[col].astype(float)
    return r


def resid_on_sector(x: np.ndarray, sector: np.ndarray) -> np.ndarray:
    s = pd.Series(x)
    return (s - s.groupby(sector).transform("mean")).to_numpy()


# ---------------------------------------------------------------- loading
def load(cache: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    xs, panel, fc, errors = [], [], [], {}
    for f in sorted(cache.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r.get("errors"):
            errors[r["ticker"]] = r["errors"]
        c = r.get("covid")
        if c:
            row = {
                "ticker": c["ticker"],
                "name": c["name"],
                "sector": c["sector"] or "Unknown",
                "bankrupt": r.get("bankrupt_2020", False),
            }
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
            row = {"ticker": r["ticker"], "year": int(pr["origin"][:4])}
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
    return pd.DataFrame(xs), pd.DataFrame(panel), pd.DataFrame(fc), errors


# ---------------------------------------------------------------- COVID cross-section
def covid_section(xs: pd.DataFrame) -> dict:
    sp = xs[~xs["bankrupt"] & xs["real_burn"].notna()].reset_index(drop=True)
    sev = -sp["real_burn"].to_numpy(float)  # positive = more cash burned
    severe = (sp["real_burn"] < -10).to_numpy(float)
    R = risk_frame(sp, "h_pandemic", "pb_pandemic")
    sector = sp["sector"].to_numpy()
    out: dict = {"n": int(len(sp)), "n_severe": int(severe.sum())}

    preds = {}
    twin = R["twin"].to_numpy(float)
    for k in R.columns:
        x = R[k].to_numpy(float)
        bt = boot(rho, [x, sev])
        d = boot(lambda a, b, c: rho(a, c) - rho(b, c), [twin, x, sev]) if k != "twin" else None
        rs = rho(resid_on_sector(pct(x), sector), resid_on_sector(pct(sev), sector))
        preds[k] = {
            "label": LABELS[k],
            "n": int(np.isfinite(x).sum()),
            "rho": rho(x, sev),
            "rho_ci": ci(bt),
            "auc_severe": auc(x, severe),
            "rho_within_sector": rs,
            "twin_minus": None if d is None else {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)},
        }
    out["predictors"] = preds
    out["within_sector_ci_twin"] = ci(
        boot(lambda a, b, s: rho(resid_on_sector(pct(a), s), resid_on_sector(pct(b), s)), [twin, sev, sector])
    )

    # incremental value: rank regression of burn severity on the twin and all benchmarks, sector fixed effects
    import statsmodels.api as sm

    X = pd.DataFrame({k: pct(R[k].to_numpy(float)) for k in ["twin", *BENCH]})
    X = X.fillna(0.5)  # missing benchmark -> median rank
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
    }
    z = R["altman_z2"].to_numpy(float)
    zq = pd.qcut(pd.Series(z).rank(method="first"), 5, labels=False).to_numpy()
    out["quintiles_altman"] = {"severe_share": [float(severe[(zq == i) & np.isfinite(z)].mean()) for i in range(5)]}
    out["rows"] = sp[["ticker", "name", "sector", "h_pandemic", "real_burn", "real_rev_drop"]].to_dict("records")
    return out


# ---------------------------------------------------------------- 2020 bankruptcies
def bankruptcy_section(xs: pd.DataFrame) -> dict:
    df = xs.reset_index(drop=True)
    y = df["bankrupt"].to_numpy(float)
    R = risk_frame(df, "h_pandemic", "pb_pandemic")
    R["twin_base"] = -df["h_base"].astype(float)
    out: dict = {"n_bankrupt": int(y.sum()), "n_survivors": int((1 - y).sum())}
    twin = R["twin"].to_numpy(float)
    res = {}
    for k in R.columns:
        x = R[k].to_numpy(float)
        both = np.isfinite(x)
        d = boot(lambda a, b, t: auc(a, t) - auc(b, t), [twin[both], x[both], y[both]]) if k not in ("twin",) else None
        res[k] = {
            "label": LABELS.get(k, "Twin (baseline health)"),
            "auc": auc(x, y),
            "auc_ci": ci(boot(auc, [x, y])),
            "n_bankrupt": int((both & (y == 1)).sum()),
            "twin_minus": None if d is None else {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)},
        }
    out["predictors"] = res
    sp = df[~df["bankrupt"]]
    pct_rank = [float((sp["h_pandemic"] < h).mean()) for h in df.loc[df["bankrupt"], "h_pandemic"]]
    out["percentile_in_sp500"] = pct_rank  # share of S&P companies the twin rated *more* fragile
    out["share_in_most_fragile_decile"] = float(np.mean(np.array(pct_rank) <= 0.10))
    out["share_in_most_fragile_quintile"] = float(np.mean(np.array(pct_rank) <= 0.20))
    sec = df["sector"].isin(df.loc[df["bankrupt"], "sector"].value_counts().index[:2])
    out["sector_matched"] = {
        "sectors": list(df.loc[df["bankrupt"], "sector"].value_counts().index[:2]),
        "auc_twin": auc(twin[sec.to_numpy()], y[sec.to_numpy()]),
        "auc_altman": auc(R["altman_z2"].to_numpy(float)[sec.to_numpy()], y[sec.to_numpy()]),
        "n": int(sec.sum()),
    }
    out["firms"] = df.loc[
        df["bankrupt"], ["ticker", "name", "sector", "h_pandemic", "h_base", "z2", "log_rev"]
    ].to_dict("records")
    # S&P 500 members are large, so size alone separates them from 2020 bankrupts: compare like with like
    size = df["log_rev"].to_numpy(float)
    cap = np.nanpercentile(size[y == 1], 90)
    small = size <= cap
    out["size_matched"] = {
        "max_log_rev": float(cap),
        "n_survivors": int((small & (y == 0)).sum()),
        "n_bankrupt": int((small & (y == 1)).sum()),
        "auc": {
            k: auc(R[k].to_numpy(float)[small], y[small]) for k in ("twin", "twin_base", "altman_z2", "icr", "size")
        },
    }
    import statsmodels.api as sm

    X = pd.DataFrame({"twin": pct(R["twin_base"].to_numpy(float)), "size": pct(R["size"].to_numpy(float))})
    X["altman_z2"] = pct(R["altman_z2"].to_numpy(float))
    X = X.fillna(0.5)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = sm.Logit(y, sm.add_constant(X)).fit(disp=False, cov_type="HC1")
        out["logit_with_size"] = {
            k: {"coef": float(m.params[k]), "z": float(m.tvalues[k]), "p": float(m.pvalues[k])} for k in X.columns
        }
    except Exception as e:
        out["logit_with_size"] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ---------------------------------------------------------------- 2013-2023 distress panel
def _events(p: pd.DataFrame) -> dict[str, np.ndarray]:
    icr0, icrmin = p["y_icr0"].to_numpy(float), p["y_icr_min"].to_numpy(float)
    cov = np.where(icr0 >= 1.5, (icrmin < 1.5).astype(float), np.nan)
    cov[~np.isfinite(icrmin)] = np.nan
    div = np.where(p["y_div_payer"].fillna(False).astype(bool), p["y_div_cut"].fillna(False).astype(float), np.nan)
    burn = p["y_burn8"].to_numpy(float)
    return {
        "severe_burn": np.where(np.isfinite(burn), (burn < -10).astype(float), np.nan),
        "coverage_collapse": cov,
        "dividend_cut": div,
    }


def _design(p: pd.DataFrame, cols: list[str], med: pd.Series | None = None) -> tuple[pd.DataFrame, pd.Series]:
    X = pd.DataFrame(index=p.index)
    for k in cols:
        if k == "twin":
            X["h_base"], X["pb_base"], X["h_rec"] = -p["h_base"], p["pb_base"], -p["h_rec"]
        else:
            col, sign = BENCH[k]
            X[k] = sign * p[col].astype(float)
    X = X.clip(X.quantile(0.01), X.quantile(0.99), axis=1)
    med = X.median() if med is None else med
    for c in list(X.columns):
        X[c + "_na"] = X[c].isna().astype(float)
    return X.fillna(med), med


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, ytr: np.ndarray, cols: list[str]) -> np.ndarray:
    import statsmodels.api as sm

    Xtr, med = _design(train, cols)
    Xte, _ = _design(test, cols, med)
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
        res: dict = {"n": int(m.sum()), "events": int(np.nansum(y)), "base_rate": float(np.nanmean(y))}
        uni = {}
        twin = R["twin"].to_numpy(float)
        for k in R.columns:
            x = R[k].to_numpy(float)
            sel = m & np.isfinite(x)
            if sel.sum() < 20:  # predictor not available in this run
                continue
            entry: dict = {"auc": auc(x[sel], y[sel]), "n": int(sel.sum())}
            if name == "severe_burn":
                entry["auc_ci"] = ci(boot(auc, [x[sel], y[sel]], firms[sel], b=B_PANEL))
                if k != "twin":
                    both = sel & np.isfinite(twin)
                    d = boot(
                        lambda a, b, t: auc(a, t) - auc(b, t), [twin[both], x[both], y[both]], firms[both], b=B_PANEL
                    )
                    entry["twin_minus"] = {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)}
            uni[k] = entry
        res["univariate"] = uni
        res["auc_by_year"] = {
            k: {
                int(yr): auc(
                    R[k].to_numpy(float)[(p["year"] == yr).to_numpy() & m], y[(p["year"] == yr).to_numpy() & m]
                )
                for yr in out["years"]
            }
            for k in ("twin", "altman_z2", "nd_ebitda", "icr", "static_stress")
        }
        # out-of-sample logistic models: test year Y, train on origins <= Y-3 (their 8-quarter outcomes are known)
        bench = list(BENCH)
        preds: dict[str, list] = {"benchmarks": [], "benchmarks_plus_twin": [], "twin_only": []}
        ys, fs = [], []
        for yr in out["years"]:
            tr = (p["year"] <= yr - 3).to_numpy() & m
            te = (p["year"] == yr).to_numpy() & m
            if tr.sum() < 300 or te.sum() < 30 or np.nansum(y[tr]) < 10:
                continue
            for key, cols in (
                ("benchmarks", bench),
                ("benchmarks_plus_twin", [*bench, "twin"]),
                ("twin_only", ["twin"]),
            ):
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
            d = boot(
                lambda a, b, t: auc(a, t) - auc(b, t), [P["benchmarks_plus_twin"], P["benchmarks"], yy], ff, b=B_PANEL
            )
            oos["delta_auc_twin_added"] = {"diff": float(np.nanmean(d)), "ci": ci(d), "p": p_two_sided(d)}
            oos["n_test"] = int(len(yy))
            oos["test_years"] = [yr for yr in out["years"] if ((p["year"] <= yr - 3).to_numpy() & m).sum() >= 300]
            res["out_of_sample"] = oos
        # in-sample logit with firm-clustered errors: is the twin significant given every benchmark and year effects?
        res["clustered_logit"] = _clustered_logit(p[m], y[m])
        out[name] = res
    return out


def _clustered_logit(p: pd.DataFrame, y: np.ndarray) -> dict:
    import statsmodels.api as sm

    X = pd.DataFrame({k: pct(sign * p[col].to_numpy(float)) for k, (col, sign) in BENCH.items()}, index=p.index).fillna(
        0.5
    )
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
            # Diebold-Mariano style test on scaled CRPS differentials, standard errors clustered by firm
            m = sm.OLS(d, np.ones(len(d))).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(g["ticker"])[0]})
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
    xs, panel, fc, errors = load(cache)
    res: dict = {
        "n_files": len(list(cache.glob("*.json"))),
        "covid": covid_section(xs),
        "bankruptcy": bankruptcy_section(xs),
        "panel": panel_section(panel),
        "forecasts": forecast_section(fc),
        "errors": errors,
    }
    from ..export import _clean

    OUT.write_text(json.dumps(_clean(res), indent=1), encoding="utf-8")
    c, b = res["covid"], res["bankruptcy"]
    print(
        f"covid n={c['n']} rho twin={c['predictors']['twin']['rho']:.3f} within-sector={c['predictors']['twin']['rho_within_sector']:.3f}"
    )
    print(f"bankruptcy AUC twin={b['predictors']['twin']['auc']:.3f} altman={b['predictors']['altman_z2']['auc']:.3f}")
    return res

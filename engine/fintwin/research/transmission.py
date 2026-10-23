"""The transmission test: given the revenue that actually happened, does the twin know where cash goes?

The first version of this test correlated (twin - margin rule) with (realized - margin rule), with a four-quarter
margin as the rule. Referees pointed out that any predictor smoother than the rule passes that test, because margins
mean-revert and the twin's costs come from a 16-quarter regression. This module therefore compares the twin with a
ladder of simple rules that see the same realized revenue, quarter by quarter:

    N1  trailing 4-quarter cash-flow margin x revenue (the old rule)
    N2  trailing 8-quarter margin                      N3  trailing 16-quarter margin
    N4  4-quarter margin shrunk toward the industry median (weight chosen on earlier years only)
    N5  per-company regression cash = a + b * revenue (operating leverage, no simulation)
    N6  N5 plus the change in revenue (working-capital timing)
    T0  the twin without feedback loops                T1  the twin

and reports, for each: errors in levels, the incremental correlation against *each* rule (not only the weakest),
an encompassing regression, an out-of-sample hybrid (rule + lambda * (twin - rule), lambda from earlier years), and
the same by firm characteristics. Outcomes are cumulative operating or free cash flow over eight quarters, as a
percentage of trailing revenue. The same runs give liquidity decisions (cash halves, new borrowing, dividend and
capex cuts) for the twin, its loop ablations and a static runway rule with the same inputs.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import stats as S

MODELS = ["N1", "N2", "N3", "N4", "N5", "N6", "T0", "T1"]
LABELS = {
    "N1": "Margin, 4 quarters",
    "N2": "Margin, 8 quarters",
    "N3": "Margin, 16 quarters",
    "N4": "Margin shrunk to industry",
    "N5": "Cash-revenue regression",
    "N6": "Regression + revenue change",
    "T0": "Twin without loops",
    "T1": "Twin",
}
NULLS = ["N1", "N2", "N3", "N4", "N5", "N6"]
EVENTS = ("cash_half", "debt_raise", "div_cut", "capex_cut")
ABL = ("full", "no_r1", "no_r2", "no_b1", "no_b2", "no_loops")
# the static runway rule's measure for each event, with its risk orientation
STATIC = {
    "cash_half": ("cash_min", -1),
    "debt_raise": ("fin_need", 1),
    "div_cut": ("div_pressure", 1),
    "capex_cut": ("rev4", -1),
}
LAMBDAS = np.round(np.arange(0.0, 1.51, 0.05), 2)


# ---------------------------------------------------------------- frame
def frame(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per firm-cutoff with 8-quarter totals (and worst cumulative values) of every model, % of revenue."""
    recs = []
    for r in rows.itertuples():
        st = r.st if isinstance(r.st, dict) else {}
        if not st.get("real_cfo"):
            continue
        rev = np.asarray(st["rev"], float)
        m = st.get("m", {})
        rec = {
            "ticker": r.ticker,
            "year": getattr(r, "year", 2020),
            "industry": getattr(r, "industry", ""),
            "rev_change": float(rev.sum() / (len(rev) / 4) - 100),
        }
        for var in ("cfo", "fcf"):
            paths = {
                "real": st[f"real_{var}"],
                "N1": _mpath(m.get(f"{var}4"), rev),
                "N2": _mpath(m.get(f"{var}8"), rev),
                "N3": _mpath(m.get(f"{var}16"), rev),
                "N5": st.get(f"ols_{var}"),
                "N6": st.get(f"dyn_{var}"),
                "T0": st.get(f"noloops_{var}"),
                "T1": st.get(f"twin_{var}"),
            }
            for k, path in paths.items():
                x = np.asarray(path if path is not None else [np.nan] * len(rev), float)
                rec[f"{k}_{var}"] = float(x.sum())
                rec[f"{k}_{var}_w"] = float(np.min(np.cumsum(x)))
            rec[f"m4_{var}"] = m.get(f"{var}4")
            rec["revsum"] = float(rev.sum())
        for k, path in (st.get("sens") or {}).items():
            rec[f"S_{k}_cfo"] = float(np.sum(np.asarray(path["cfo"], float)))
            rec[f"S_{k}_health"] = path.get("health")
            for e in EVENTS:
                rec[f"S_{k}_pb_{e}"] = (path.get("probs") or {}).get(e)
        for e in EVENTS:
            v = (st.get("events") or {}).get(e)
            rec[f"ev_{e}"] = np.nan if v is None else float(v)
            for a in ABL:
                rec[f"pb_{a}_{e}"] = ((st.get("probs") or {}).get(a) or {}).get(e)
        for k, v in (st.get("static") or {}).items():
            rec[f"st_{k}"] = v
        for c in (
            "nd_ebitda",
            "fixed_share",
            "due_cash",
            "health_t0",
            "fcf_margin",
            "z2",
            "log_rev",
            "h_base",
            "y_bk8",
            "y_burn8",
        ):
            rec[c] = getattr(r, c, np.nan)
        recs.append(rec)
    df = pd.DataFrame(recs)
    for c in df.columns:
        if c not in ("ticker", "industry"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def loo_median(x: pd.Series) -> pd.Series:
    """Median of the other members of the group (NaN for singletons and missing values)."""
    v = x.to_numpy(float)
    ok = np.flatnonzero(np.isfinite(v))
    out = np.full(len(v), np.nan)
    n = len(ok)
    if n < 2:
        return pd.Series(out, index=x.index)
    order = ok[np.argsort(v[ok])]
    srt = v[order]
    for k, i in enumerate(order):
        rest = np.delete(srt, k)
        out[i] = 0.5 * (rest[(n - 2) // 2] + rest[(n - 1) // 2])
    return pd.Series(out, index=x.index)


def _mpath(m, rev: np.ndarray) -> np.ndarray:
    return np.full(len(rev), np.nan) if m is None else float(m) * rev


def add_shrunk(df: pd.DataFrame) -> pd.DataFrame:
    """N4: the 4-quarter margin shrunk toward the leave-one-out industry median of the same cutoff year.

    The weight on the company's own margin is chosen, for each year, to minimize the median absolute error on
    earlier years only (0.5 for the first year), so N4 never uses information from the year it predicts.
    """
    df = df.copy()
    for var in ("cfo", "fcf"):
        m = df[f"m4_{var}"]
        loo = df.groupby(["year", "industry"])[f"m4_{var}"].transform(loo_median)
        weights = np.round(np.arange(0.0, 1.01, 0.1), 1)
        pred = {w: (w * m + (1 - w) * loo) * df["revsum"] for w in weights}
        out = pd.Series(np.nan, index=df.index)
        chosen = {}
        for y in sorted(df["year"].unique()):
            past = df["year"] <= y - 3  # outcomes of later cutoffs were not yet reported
            if past.sum() >= 100:
                err = {w: np.nanmedian(np.abs(pred[w][past] - df.loc[past, f"real_{var}"])) for w in weights}
                w = min(err, key=lambda k: err[k])
            else:
                w = 0.5
            chosen[int(y)] = float(w)
            out[df["year"] == y] = pred[w][df["year"] == y]
        df[f"N4_{var}"] = out
        df.attrs[f"N4_weights_{var}"] = chosen
    return df


# ---------------------------------------------------------------- statistics
def _wins(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip(x, lo, hi)


def levels(df: pd.DataFrame, var: str) -> dict:
    real = df[f"real_{var}"].to_numpy(float)
    lo, hi = np.nanpercentile(real, [1, 99])
    out = {}
    base = df[f"N1_{var}"].to_numpy(float)
    for k in MODELS:
        x = df[f"{k}_{var}"].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(real)
        e = np.abs(x - real)
        out[k] = {
            "label": LABELS[k],
            "n": int(ok.sum()),
            "median_ae": float(np.nanmedian(e[ok])),
            "mae_w": float(np.nanmean(np.abs(_wins(x, lo, hi) - _wins(real, lo, hi))[ok])),
            "rho": S.rho(x, real),
            "share_closer_than_N1": float(np.nanmean((e < np.abs(base - real))[ok & np.isfinite(base)])),
        }
    return out


def incremental(df: pd.DataFrame, var: str, firms: np.ndarray, b: int) -> dict:
    """rho(model - base, realized - base) for every model and base: the old statistic, against every null."""
    real = df[f"real_{var}"].to_numpy(float)
    out: dict = {}
    key_cells = {
        ("T1", "N1"),
        ("N2", "N1"),
        ("N3", "N1"),
        ("N4", "N1"),
        ("N5", "N1"),
        ("N6", "N1"),
        ("T1", "N3"),
        ("T1", "N4"),
        ("T1", "N6"),
        ("T0", "N6"),
    }
    for base in ["N1", "N3", "N4", "N6"]:
        bx = df[f"{base}_{var}"].to_numpy(float)
        row = {}
        for k in MODELS:
            if k == base:
                continue
            x = df[f"{k}_{var}"].to_numpy(float)
            e: dict = {"rho": S.rho(x - bx, real - bx)}
            if (k, base) in key_cells:
                e["ci"] = S.ci(S.boot(S.rho, [x - bx, real - bx], firms, b=b))
            row[k] = e
        out[base] = row
    return out


def encompassing(df: pd.DataFrame, var: str) -> dict:
    """OLS of (realized - N1) on each model's departure from N1, with year effects and firm-clustered errors.

    If the twin's coefficient survives the smoother rules (N3, N4) and the timing rule (N6), its departures from the
    four-quarter rule carry information they do not.
    """
    import statsmodels.api as sm

    cols = ["T1", "N3", "N4", "N6"]
    d = df[[f"real_{var}", *[f"{k}_{var}" for k in ["N1", *cols]], "year", "ticker"]].dropna()
    real = d[f"real_{var}"]
    lo, hi = np.nanpercentile(real, [1, 99])
    y = _wins(real, lo, hi) - _wins(d[f"N1_{var}"], lo, hi)
    X = pd.DataFrame({k: _wins(d[f"{k}_{var}"], lo, hi) - _wins(d[f"N1_{var}"], lo, hi) for k in cols})
    X = pd.concat([X, pd.get_dummies(d["year"], prefix="y", drop_first=True, dtype=float)], axis=1)
    out = {}
    for name, use in (("all", cols), ("twin_only", ["T1"]), ("nulls_only", ["N3", "N4", "N6"])):
        Xs = sm.add_constant(X[[*use, *[c for c in X if c.startswith("y_")]]])
        m = sm.OLS(y.to_numpy(float), Xs).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ticker"])[0]})
        out[name] = {
            "coef": {k: float(m.params[k]) for k in use},
            "t": {k: float(m.tvalues[k]) for k in use},
            "p": {k: float(m.pvalues[k]) for k in use},
            "r2": float(m.rsquared),
            "n": int(m.nobs),
        }
    # the same with standard errors clustered by firm and by cutoff year (common shocks within a year)
    two_way = np.column_stack([pd.factorize(d["ticker"])[0], pd.factorize(d["year"])[0]])
    Xs = sm.add_constant(X[[*cols, *[c for c in X if c.startswith("y_")]]])
    m = sm.OLS(y.to_numpy(float), Xs).fit(cov_type="cluster", cov_kwds={"groups": two_way})
    out["all_two_way"] = {"t": {k: float(m.tvalues[k]) for k in cols}, "p": {k: float(m.pvalues[k]) for k in cols}}
    # Harvey, Leybourne and Newbold (1998): does forecast A encompass forecast B? d = e_A (e_A - e_B), mean > 0 rejects
    real_w = np.asarray(_wins(real, lo, hi), float)
    hln: dict = {}
    for a_, b_ in (("N3", "T1"), ("T1", "N3"), ("N6", "T1"), ("T1", "N6")):
        e_a = real_w - np.asarray(_wins(d[f"{a_}_{var}"], lo, hi), float)
        e_b = real_w - np.asarray(_wins(d[f"{b_}_{var}"], lo, hi), float)
        dd = e_a * (e_a - e_b)
        mm = sm.OLS(dd, np.ones(len(dd))).fit(cov_type="cluster", cov_kwds={"groups": two_way})
        hln[f"{a_}_encompasses_{b_}"] = {
            "t": float(mm.tvalues[0]),
            "p_one_sided": float(mm.pvalues[0] / 2) if mm.params[0] > 0 else float(1 - mm.pvalues[0] / 2),
        }
    out["hln"] = hln
    # unconstrained form (Fair and Shiller 1990): realized on every forecast in levels, so that noise in the four-quarter
    # rule cannot load on the other forecasts through a coefficient restricted to 1 - sum(b)
    lv = pd.DataFrame({k: _wins(d[f"{k}_{var}"], lo, hi) for k in ["N1", *cols]})
    lv = pd.concat([lv, X[[c for c in X if c.startswith("y_")]]], axis=1)
    for name, use in (("levels", ["N1", *cols]), ("levels_nulls_only", ["N1", "N3", "N4", "N6"])):
        Xs = sm.add_constant(lv[[*use, *[c for c in lv if c.startswith("y_")]]])
        m = sm.OLS(np.asarray(_wins(real, lo, hi), float), Xs).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ticker"])[0]}
        )
        m2 = sm.OLS(np.asarray(_wins(real, lo, hi), float), Xs).fit(cov_type="cluster", cov_kwds={"groups": two_way})
        out[name] = {
            "coef": {k: float(m.params[k]) for k in use},
            "t": {k: float(m.tvalues[k]) for k in use},
            "p": {k: float(m.pvalues[k]) for k in use},
            "r2": float(m.rsquared),
            "n": int(m.nobs),
            "t_two_way": {k: float(m2.tvalues[k]) for k in use},
        }
    return out


def hybrid(df: pd.DataFrame, var: str, firms: np.ndarray, b: int) -> dict:
    """Out-of-sample combinations base + lambda * (adjuster - base), lambda chosen on earlier cutoff years.

    Evaluated on years with at least 200 earlier observations; the null hybrid (N1 adjusted by N6) is the control.
    """
    real = df[f"real_{var}"].to_numpy(float)
    lo, hi = np.nanpercentile(real, [1, 99])
    yrs = df["year"].to_numpy()
    pairs = {
        "N1+T1": ("N1", "T1"),
        "N3+T1": ("N3", "T1"),
        "N4+T1": ("N4", "T1"),
        "N6+T1": ("N6", "T1"),
        "N1+N3": ("N1", "N3"),
        "N1+N6": ("N1", "N6"),
        "N3+N6": ("N3", "N6"),
        # combination-puzzle controls: any second, noisier estimate given a small weight
        "N3+N1": ("N3", "N1"),
        "N3+N2": ("N3", "N2"),
        "N3+N5": ("N3", "N5"),
        "N3+T0": ("N3", "T0"),
    }
    preds: dict[str, np.ndarray] = {}
    lambdas: dict[str, dict[int, float]] = {}
    for name, (base, adj) in pairs.items():
        bx, ax = df[f"{base}_{var}"].to_numpy(float), df[f"{adj}_{var}"].to_numpy(float)
        p = np.full(len(df), np.nan)
        lambdas[name] = {}
        for y in sorted(set(yrs)):
            tr = (yrs <= y - 3) & np.isfinite(bx) & np.isfinite(ax) & np.isfinite(real)
            if tr.sum() < 200:
                continue
            err = [
                np.nanmean(np.abs(_wins(bx[tr] + lam * (ax[tr] - bx[tr]), lo, hi) - _wins(real[tr], lo, hi)))
                for lam in LAMBDAS
            ]
            lam = float(LAMBDAS[int(np.argmin(err))])
            lambdas[name][int(y)] = lam
            te = yrs == y
            p[te] = bx[te] + lam * (ax[te] - bx[te])
        preds[name] = p
    test = np.isfinite(preds["N1+T1"]) & np.isfinite(real)
    for k in MODELS:
        preds[k] = df[f"{k}_{var}"].to_numpy(float)
    test &= np.all([np.isfinite(v) for v in preds.values()], axis=0)

    def mae(x, t):
        return float(np.mean(np.abs(_wins(x, lo, hi) - _wins(t, lo, hi))))

    out: dict = {"n": int(test.sum()), "lambda": lambdas, "mae_w": {}, "median_ae": {}}
    for k, v in preds.items():
        out["mae_w"][k] = mae(v[test], real[test])
        out["median_ae"][k] = float(np.median(np.abs(v[test] - real[test])))
    f = firms[test]
    for a, c in (
        ("N1+T1", "N1"),
        ("N3+T1", "N3"),
        ("N3+T1", "N3+N6"),
        ("N3+T1", "N3+N1"),
        ("N3+T1", "N3+N2"),
        ("N3+T1", "N3+N5"),
        ("N3+T1", "N3+T0"),
        ("N4+T1", "N4"),
        ("N6+T1", "N6"),
        ("N1+T1", "N1+N6"),
        ("T1", "N1"),
        ("T1", "N3"),
        ("T1", "N6"),
    ):
        d = S.boot(lambda u, v, t: mae(u, t) - mae(v, t), [preds[a][test], preds[c][test], real[test]], f, b=b)
        out[f"{a}_vs_{c}"] = {"diff": float(np.mean(d)), "ci": S.ci(d), "p": S.p_two_sided(d)}
    return out


def by_year(df: pd.DataFrame, var: str) -> dict:
    out = {}
    for y, g in df.groupby("year"):
        real = g[f"real_{var}"].to_numpy(float)
        cell: dict[str, float] = {"n": int(len(g))}
        for k, base in (("T1", "N1"), ("N3", "N1"), ("N4", "N1"), ("N6", "N1"), ("T1", "N6"), ("T1", "N4")):
            x, bx = g[f"{k}_{var}"].to_numpy(float), g[f"{base}_{var}"].to_numpy(float)
            cell[f"{k}|{base}"] = S.rho(x - bx, real - bx)
        for k in ("N1", "N6", "T1"):
            cell[f"mae_{k}"] = float(np.nanmedian(np.abs(g[f"{k}_{var}"] - g[f"real_{var}"])))
        out[int(y)] = cell
    return out


def heterogeneity(df: pd.DataFrame, var: str) -> dict:
    """The incremental correlation and errors in levels by firm characteristics (terciles) and revenue shock."""
    real = df[f"real_{var}"].to_numpy(float)
    groups: dict[str, pd.Series] = {}
    for c, label in (("nd_ebitda", "leverage"), ("fixed_share", "fixed_costs"), ("due_cash", "maturities")):
        x = df[c].astype(float)
        groups[label] = pd.qcut(x.rank(method="first"), 3, labels=["low", "mid", "high"])
    groups["revenue_shock"] = pd.cut(
        df["rev_change"], [-np.inf, -10, 0, 10, np.inf], labels=["fell >10%", "fell 0-10%", "rose 0-10%", "rose >10%"]
    )
    out: dict = {}
    for name, gr in groups.items():
        cells = {}
        for lev in gr.cat.categories:
            m = (gr == lev).to_numpy()
            r = real[m]
            cell: dict[str, float] = {"n": int(m.sum())}
            for k, base in (("T1", "N1"), ("T1", "N6"), ("N3", "N1"), ("N6", "N1")):
                x, bx = df[f"{k}_{var}"].to_numpy(float)[m], df[f"{base}_{var}"].to_numpy(float)[m]
                cell[f"{k}|{base}"] = S.rho(x - bx, r - bx)
            for k in ("N1", "N6", "T1"):
                cell[f"mae_{k}"] = float(np.nanmedian(np.abs(df[f"{k}_{var}"].to_numpy(float)[m] - r)))
            cells[str(lev)] = cell
        out[name] = cells
    return out


def decisions(df: pd.DataFrame, firms: np.ndarray, b: int) -> dict:
    """AUC of the twin's event probabilities (and of each loop ablation) against a static runway rule with the
    same inputs, an opening-balance-sheet score and the FCF margin, plus out-of-sample combined logits."""
    out: dict = {}
    for e in EVENTS:
        y = df[f"ev_{e}"].to_numpy(float)
        m = np.isfinite(y)
        if m.sum() < 200 or np.nansum(y) < 20:
            continue
        col, sign = STATIC[e]
        preds = {
            "twin": df[f"pb_full_{e}"].to_numpy(float),
            "static": sign * df[f"st_{col}"].to_numpy(float),
            "formula": -df["health_t0"].to_numpy(float),
            "fcf_margin": -df["fcf_margin"].to_numpy(float),
        }
        for a in ABL[1:]:
            preds[a] = df[f"pb_{a}_{e}"].to_numpy(float)
        res: dict = {"n": int(m.sum()), "events": int(np.nansum(y)), "base_rate": float(np.nanmean(y)), "auc": {}}
        for k, x in preds.items():
            sel = m & np.isfinite(x)
            res["auc"][k] = S.auc(x[sel], y[sel])
        res["auc_ci_twin"] = S.ci(S.boot(S.auc, [preds["twin"][m], y[m]], firms[m], b=b))
        res["twin_minus"] = {
            k: S.paired(S.auc, preds["twin"], preds[k], y, firms, b)
            for k in ("static", "formula", "fcf_margin", *ABL[1:])
        }
        res["oos"] = _oos_events(df, preds, y, firms, b)
        out[e] = res
    return out


def _oos_events(df: pd.DataFrame, preds: dict, y: np.ndarray, firms: np.ndarray, b: int) -> dict:
    """Walk-forward logits: static rule + score + FCF margin, with and without the twin (train on years <= Y-3)."""
    import statsmodels.api as sm

    yrs = df["year"].to_numpy()
    # percentile ranks within each cutoff year: the cross-section an analyst would have seen on that day
    X = pd.DataFrame({k: _pct_by(preds[k], yrs) for k in ("static", "formula", "fcf_margin", "twin")}).fillna(0.5)
    P: dict[str, list[np.ndarray]] = {"rule_score": [], "rule_score_twin": []}
    ys, fs = [], []
    for yr in sorted(set(yrs)):
        tr, te = (yrs <= yr - 3) & np.isfinite(y), (yrs == yr) & np.isfinite(y)
        if tr.sum() < 300 or te.sum() < 30 or y[tr].sum() < 10:
            continue
        for key, cols in (
            ("rule_score", ["static", "formula", "fcf_margin"]),
            ("rule_score_twin", ["static", "formula", "fcf_margin", "twin"]),
        ):
            use = [c for c in cols if X.loc[tr, c].std() > 0]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = sm.GLM(
                    y[tr], sm.add_constant(X.loc[tr, use], has_constant="add"), family=sm.families.Binomial()
                ).fit_regularized(alpha=0.001, L1_wt=0.0)
            P[key].append(np.asarray(fit.predict(sm.add_constant(X.loc[te, use], has_constant="add"))))
        ys.append(y[te])
        fs.append(firms[te])
    if not ys:
        return {}
    yy, ff = np.concatenate(ys), np.concatenate(fs)
    P2 = {k: np.concatenate(v) for k, v in P.items()}
    return {
        "n": int(len(yy)),
        "auc": {k: S.auc(v, yy) for k, v in P2.items()},
        "delta_twin": S.paired(S.auc, P2["rule_score_twin"], P2["rule_score"], yy, ff, b),
    }


def _pct_by(x: np.ndarray, groups: np.ndarray) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for g in set(groups):
        m = groups == g
        out[m] = S.pct(x[m])
    return out


def sensitivity(df: pd.DataFrame, firms: np.ndarray, b: int) -> dict:
    """Each judgement call varied in turn: transmission (incremental rho against N1 and N6, errors in levels) and
    the baseline verdict (AUC for bankruptcy and for severe cash burn over eight quarters)."""
    names = sorted({c.split("_", 1)[1].rsplit("_cfo", 1)[0] for c in df if c.startswith("S_") and c.endswith("_cfo")})
    real = df["real_cfo"].to_numpy(float)
    bk = df["y_bk8"].to_numpy(float)
    burn = (df["y_burn8"].to_numpy(float) < -10).astype(float)
    burn[~np.isfinite(df["y_burn8"].to_numpy(float))] = np.nan
    out: dict = {}

    def row(x: np.ndarray, h: np.ndarray) -> dict:
        r: dict = {"median_ae": float(np.nanmedian(np.abs(x - real)))}
        for base in ("N1", "N6"):
            bx = df[f"{base}_cfo"].to_numpy(float)
            r[f"incr_{base}"] = S.rho(x - bx, real - bx)
        r["auc_bk"] = S.auc(-h, bk)
        r["auc_burn"] = S.auc(-h, burn)
        return r

    out["baseline"] = row(df["T1_cfo"].to_numpy(float), df["h_base"].to_numpy(float))
    for n in names:
        out[n] = row(df[f"S_{n}_cfo"].to_numpy(float), df[f"S_{n}_health"].to_numpy(float))
    return out


def section(rows: pd.DataFrame, b: int, panel: bool = True) -> dict:
    df = add_shrunk(frame(rows))
    if df.empty:
        return {}
    firms = df["ticker"].to_numpy()
    out: dict = {
        "n": int(len(df)),
        "n_firms": int(df["ticker"].nunique()),
        "n4_weights": {v: df.attrs.get(f"N4_weights_{v}") for v in ("cfo", "fcf")},
    }
    for var in ("cfo", "fcf"):
        e: dict = {"levels": levels(df, var), "incremental": incremental(df, var, firms, b)}
        e["worst_cumulative"] = {
            k: S.rho(
                df[f"{k}_{var}_w"].to_numpy(float) - df[f"N1_{var}_w"].to_numpy(float),
                df[f"real_{var}_w"].to_numpy(float) - df[f"N1_{var}_w"].to_numpy(float),
            )
            for k in MODELS[1:]
            if k != "N4"  # the shrunk margin is built from totals only
        }
        down = (df["rev_change"] < -10).to_numpy()
        e["revenue_down_10pct"] = (
            {
                "n": int(down.sum()),
                "levels": levels(df[down].reset_index(drop=True), var),
                "incremental": incremental(df[down].reset_index(drop=True), var, firms[down], max(b // 2, 50)),
            }
            if down.sum() >= 30
            else {"n": int(down.sum())}
        )
        if panel:
            e["encompassing"] = encompassing(df, var)
            e["hybrid"] = hybrid(df, var, firms, b)
            e["by_year"] = by_year(df, var)
            e["heterogeneity"] = heterogeneity(df, var)
        out[var] = e
    if panel:
        out["decisions"] = decisions(df, firms, b)
        out["sensitivity"] = sensitivity(df, firms, b)
        inc = out["cfo"]["incremental"]
        best_null = max(("N3", "N4", "N6"), key=lambda k: inc["N1"][k]["rho"])
        twin_vs_best = inc[best_null]["T1"]
        out["verdict"] = {
            # the decision rule written down before the run (docs/REVISION_PLAN.md, 2.6)
            "twin_vs_N1": inc["N1"]["T1"]["rho"],
            "best_null": best_null,
            "best_null_vs_N1": inc["N1"][best_null]["rho"],
            "null_share_of_twin": inc["N1"][best_null]["rho"] / inc["N1"]["T1"]["rho"]
            if inc["N1"]["T1"]["rho"]
            else None,
            "twin_vs_best_null": twin_vs_best["rho"],
            "twin_vs_best_null_ci": twin_vs_best.get("ci"),
            "encompassing_p_twin": out["cfo"]["encompassing"]["all"]["p"]["T1"],
        }
        v = out["verdict"]
        v["twin_vs_each_null_ci_low"] = {k: (inc[k]["T1"].get("ci") or [np.nan])[0] for k in ("N3", "N4", "N6")}
        v["transmission_claim_survives"] = bool(
            all(np.isfinite(x) and x > 0 for x in v["twin_vs_each_null_ci_low"].values())
            and v["encompassing_p_twin"] < 0.05
        )
    return out

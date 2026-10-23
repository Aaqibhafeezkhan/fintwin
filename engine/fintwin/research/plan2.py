"""Second-round tests (docs/REVISION_PLAN_2.md). Every decision rule used here was committed before the run.

1.1  revised specification: the fixed-cost prior chosen walk-forward from a grid, globally and by industry
1.2  where the over-reaction comes from: response of cash, EBITDA and capex to revenue, twin versus reality
1.3  cash forecasts: random walk + lambda * (twin - random walk), lambda from earlier origins
3    calibration: adaptive conformal inference and group-conditional scaling, learned on past errors only
4.2  timing of liquidity events (concordance), 4.3 event thresholds, 4.4 other downturns (2015-16, 2022),
4.5  mechanism of the free-cash-flow gain, 4.6 two-way (firm x year) bootstrap and Holm adjustment, 4.7 small firms
H1, H3 formal verdicts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats as S
from . import transmission as T

PRIORS = {
    "baseline": 0.35,
    "fixed_prior_low": 0.20,
    "fixed_prior_high": 0.50,
    "prior_share_05": 0.05,
    "prior_share_10": 0.10,
    "prior_share_15": 0.15,
    "prior_share_25": 0.25,
    "prior_share_30": 0.30,
    "prior_share_45": 0.45,
    "prior_none": None,
}


# ---------------------------------------------------------------- frame of everything this module needs
def frame(panel: pd.DataFrame) -> pd.DataFrame:
    recs = []
    for r in panel.itertuples():
        st = r.st if isinstance(r.st, dict) else {}
        if not st.get("real_cfo"):
            continue
        rev = np.asarray(st["rev"], float)
        m = st.get("m", {})
        rec: dict = {
            "ticker": r.ticker,
            "year": r.year,
            "industry": getattr(r, "industry", ""),
            "rev_change": float(rev.sum() / 2 - 100),
            "log_rev": getattr(r, "log_rev", np.nan),
            "y_bk8": getattr(r, "y_bk8", np.nan),
            "y_burn8": getattr(r, "y_burn8", np.nan),
            "h_base": getattr(r, "h_base", np.nan),
            "health_t0": getattr(r, "health_t0", np.nan),
        }
        for k, key in (
            ("real_cfo", "real_cfo"),
            ("twin_cfo", "twin_cfo"),
            ("real_fcf", "real_fcf"),
            ("twin_fcf", "twin_fcf"),
            ("real_ebitda", "real_ebitda"),
            ("twin_ebitda", "twin_ebitda"),
            ("real_capex", "real_capex"),
            ("twin_capex", "twin_capex"),
            ("ols_cfo", "ols_cfo"),
            ("ols_fcf", "ols_fcf"),
            ("dyn_cfo", "dyn_cfo"),
        ):
            v = st.get(key)
            rec[k] = float(np.sum(np.asarray(v, float))) if v is not None else np.nan
        for var in ("cfo", "fcf"):
            mv = m.get(f"{var}16")
            rec[f"N3_{var}"] = float(mv) * rev.sum() if mv is not None else np.nan
        rec["N3_capex"] = rec["N3_cfo"] - rec["N3_fcf"]
        rec["N5_capex"] = rec["ols_cfo"] - rec["ols_fcf"]
        for name, v in (st.get("sens") or {}).items():
            rec[f"S_{name}_cfo"] = float(np.sum(np.asarray(v["cfo"], float)))
            rec[f"S_{name}_health"] = v.get("health")
        rec["S_baseline_cfo"], rec["S_baseline_health"] = rec["twin_cfo"], rec["h_base"]
        rc = st.get("realized_cont") or {}
        for k, v in rc.items():
            rec[f"rc_{k}"] = np.nan if v is None else float(v)
        probs = st.get("probs") or {}
        for abl in ("full", "no_loops"):
            pb = probs.get(abl) or {}
            for ev, curve in (pb.get("timing") or {}).items():
                if curve:
                    rec[f"tm_{abl}_{ev}"] = float(curve[-1])
                    rec[f"tmx_{abl}_{ev}"] = float(np.sum(1 - np.asarray(curve)))  # expected event-free quarters
            for ev, g in (pb.get("grid") or {}).items():
                for x, val in g.items():
                    rec[f"gr_{abl}_{ev}_{x}"] = val
        stt = st.get("static") or {}
        rec["st_cash_min"] = stt.get("cash_min")
        rec["st_fin_need"] = stt.get("fin_need")
        recs.append(rec)
    df = pd.DataFrame(recs)
    for c in df.columns:
        if c not in ("ticker", "industry"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _mae(x: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.median(np.abs(x[m] - y[m]))) if m.any() else np.nan


# ---------------------------------------------------------------- 1.1 revised specification
def revised_spec(df: pd.DataFrame, firms: np.ndarray, b: int) -> dict:
    """For each test year choose the prior with the lowest median error on earlier years (globally, and within each
    industry with at least 300 earlier firm-years); evaluate on the test year only."""
    real = df["real_cfo"].to_numpy(float)
    names = [n for n in PRIORS if f"S_{n}_cfo" in df]
    yrs, ind = df["year"].to_numpy(), df["industry"].to_numpy()
    out: dict = {"grid_median_ae": {n: _mae(df[f"S_{n}_cfo"].to_numpy(float), real) for n in names}}
    for scope in ("global", "industry"):
        pred = np.full(len(df), np.nan)
        health = np.full(len(df), np.nan)
        chosen: dict = {}
        for y in sorted(set(yrs)):
            past = yrs < y
            if past.sum() < 500:
                continue
            groups = [None] if scope == "global" else sorted(set(ind[yrs == y]))
            for g in groups:
                pg = past & ((ind == g) if g is not None else True)
                if pg.sum() < 300:
                    pg = past
                err = {n: _mae(df[f"S_{n}_cfo"].to_numpy(float)[pg], real[pg]) for n in names}
                best = min(err, key=lambda k: err[k])
                te = (yrs == y) & ((ind == g) if g is not None else True)
                pred[te] = df[f"S_{best}_cfo"].to_numpy(float)[te]
                health[te] = df[f"S_{best}_health"].to_numpy(float)[te]
                chosen[f"{int(y)}{'' if g is None else ':' + str(g)}"] = best
        test = np.isfinite(pred) & np.isfinite(real)
        base = df["twin_cfo"].to_numpy(float)

        def med(u, t):
            return float(np.median(np.abs(u - t)))

        d = S.boot(lambda u, v, t: med(u, t) - med(v, t), [pred[test], base[test], real[test]], firms[test], b=b)
        bk = df["y_bk8"].to_numpy(float)
        auc_new = S.auc(-health[test], bk[test])
        auc_old = S.auc(-df["h_base"].to_numpy(float)[test], bk[test])
        out[scope] = {
            "n": int(test.sum()),
            "median_ae_revised": med(pred[test], real[test]),
            "median_ae_baseline": med(base[test], real[test]),
            "diff": {"diff": float(np.mean(d)), "ci": S.ci(d), "p": S.p_two_sided(d)},
            "auc_bk_revised": auc_new,
            "auc_bk_baseline": auc_old,
            "chosen": chosen,
        }
        out[scope]["accepted"] = bool(out[scope]["diff"]["ci"][1] < 0 and (auc_old - auc_new) <= 0.01)
    return out


# ---------------------------------------------------------------- 1.2 over-reaction
def overreaction(df: pd.DataFrame) -> dict:
    """Slope of each 8-quarter total (pp of trailing revenue) on the revenue change, twin and reality (OLS, winsorized)."""
    out: dict = {}
    x = df["rev_change"].to_numpy(float)
    for var in ("cfo", "ebitda", "capex"):
        res: dict = {}
        for who in ("real", "twin"):
            y = df[f"{who}_{var}"].to_numpy(float)
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 50:
                raise ValueError(f"{who}_{var}: not enough observations")
            lo, hi = np.nanpercentile(y[m], [1, 99])
            xl, xh = np.nanpercentile(x[m], [1, 99])
            slope = np.polyfit(np.clip(x[m], xl, xh), np.clip(y[m], lo, hi), 1)[0]
            res[who] = float(slope)
        res["ratio"] = res["twin"] / res["real"] if res["real"] else None
        out[var] = res
    return out


# ---------------------------------------------------------------- 1.3 cash forecasts
def cash_hybrid(fc: pd.DataFrame) -> dict:
    from ..backtest.scoring import crps_gaussian

    g = fc[(fc["var"] == "cash_like") & fc["rw_mu"].notna() & fc["q"].notna()].copy()
    if g.empty:
        return {}
    g["q50"] = [q[2] for q in g["q"]]
    g["origin_ts"] = pd.to_datetime(g["origin"])
    lam_grid = np.round(np.arange(0, 1.01, 0.05), 2)
    pred, lams = np.full(len(g), np.nan), {}
    y, rw, tw, sc = (g[c].to_numpy(float) for c in ("y", "rw_mu", "q50", "scale"))
    oy = g["origin_ts"].dt.year.to_numpy()
    for yr in sorted(set(oy)):
        past = oy < yr - 1  # forecasts whose four quarters were all reported before this origin
        if past.sum() < 200:
            continue
        err = [np.mean(np.abs(rw[past] + lam * (tw[past] - rw[past]) - y[past]) / sc[past]) for lam in lam_grid]
        lam = float(lam_grid[int(np.argmin(err))])
        lams[int(yr)] = lam
        te = oy == yr
        pred[te] = rw[te] + lam * (tw[te] - rw[te])
    sd = g["rw_sd"].to_numpy(float)
    m = (
        np.isfinite(pred)
        & np.isfinite(sd)
        & (sd > 0)
        & np.isfinite(g["crps_rw"].to_numpy(float))
        & np.isfinite(g["crps_twin"].to_numpy(float))
        & np.isfinite(sc)
        & (sc > 0)
    )
    crps_h = np.array([crps_gaussian(a, s_, t) for a, s_, t in zip(pred[m], sd[m], y[m], strict=True)])
    crps_rw = g["crps_rw"].to_numpy(float)[m]
    crps_tw = g["crps_twin"].to_numpy(float)[m]
    firms = g["ticker"].to_numpy()[m]
    s_ = sc[m]
    d = S.boot(lambda a, b_: 1 - np.mean(a) / np.mean(b_), [crps_h / s_, crps_rw / s_], firms, b=300)
    return {
        "n": int(m.sum()),
        "lambda": lams,
        "skill_hybrid_vs_rw": float(1 - np.mean(crps_h / s_) / np.mean(crps_rw / s_)),
        "skill_hybrid_ci": S.ci(d),
        "skill_twin_vs_rw": float(1 - np.mean(crps_tw / s_) / np.mean(crps_rw / s_)),
        "accepted": bool(S.ci(d)[1] >= 0 and (1 - np.mean(crps_h / s_) / np.mean(crps_rw / s_)) >= 0),
    }


# ---------------------------------------------------------------- 3 calibration
def calibration(fc: pd.DataFrame, panel: pd.DataFrame) -> dict:
    """Adaptive conformal inference (Gibbs and Candes 2021) on normalized errors in the order targets were reported,
    and group-conditional rescaling with factors learned only from already-reported errors."""
    from .calibration import REPORT_LAG, _norm

    feats = panel[["ticker", "year", "log_rev", "rev_vol"]].drop_duplicates(["ticker", "year"])
    out: dict = {}
    for var, g in fc[fc["q"].notna()].groupby("var"):
        d = _norm(g).merge(feats, on=["ticker", "year"], how="left")
        d["size_t"] = pd.qcut(d["log_rev"].rank(method="first"), 3, labels=False)
        d["vol_t"] = pd.qcut(d["rev_vol"].rank(method="first"), 3, labels=False)
        d["stress"] = d["target_ts"].between("2020-03-01", "2021-03-31")
        d["seen"] = d["target_ts"] + REPORT_LAG
        d = d.sort_values("origin_ts").reset_index(drop=True)
        res: dict = {}
        # (a) group-conditional split conformal: factor per (size tercile, volatility tercile) from reported errors
        c90 = np.full(len(d), np.nan)
        for o in sorted(d["origin_ts"].unique()):
            past = d[d["seen"] <= o]
            cur = d["origin_ts"] == o
            if len(past) < 200:
                continue
            for (st_, vt), idx in d[cur].groupby(["size_t", "vol_t"]).groups.items():
                pg = past[(past["size_t"] == st_) & (past["vol_t"] == vt)]
                pool = pg if len(pg) >= 100 else past
                c90[idx] = float(np.quantile(pool["s90"], 0.9))
        d["cond_hit"] = d["s90"] <= c90
        # (b) adaptive conformal: alpha_t updated after each reported error (gamma = 0.005), quantile of past scores
        # forecasts are issued in yearly batches, so alpha is updated once per batch of newly reported errors with
        # their average miscoverage (Gibbs and Candes 2021, eq. 2, with the batch error rate), gamma = 0.05
        alpha, gamma, hits, widths = 0.10, 0.05, np.full(len(d), np.nan), np.full(len(d), np.nan)
        seen_ts = d["seen"].to_numpy()
        used = np.zeros(len(d), bool)
        for o in sorted(d["origin_ts"].unique()):
            new = (~used) & (seen_ts <= o)
            judged = new & np.isfinite(widths)
            if judged.any():
                alpha = float(np.clip(alpha + gamma * (0.10 - (1 - hits[judged].astype(float)).mean()), 0.001, 0.5))
            used |= new
            cur = np.flatnonzero((d["origin_ts"] == o).to_numpy())
            if used.sum() < 200:
                continue
            q = float(np.quantile(d.loc[used, "s90"].to_numpy(), 1 - alpha))
            widths[cur] = q
            hits[cur] = d.loc[cur, "s90"].to_numpy() <= q
        d["aci_hit"] = hits
        d["aci_w"] = widths
        ev = d[np.isfinite(c90) & np.isfinite(hits)]
        res["n"] = int(len(ev))
        res["coverage"] = {k: float(ev[f"{k}_hit"].astype(float).mean()) for k in ("cond", "aci")}
        groups = {
            "year": ev["year"],
            "size": ev["size_t"],
            "volatility": ev["vol_t"],
            "stress": ev["stress"].map({True: "2020Q2-2021Q1", False: "other"}),
        }
        res["by"] = {}
        for name, gr in groups.items():
            t = ev.groupby(gr, observed=True)[["cond_hit", "aci_hit"]].agg(lambda s: float(s.astype(float).mean()))
            res["by"][name] = {str(k): {c: float(v) for c, v in r.items()} for k, r in t.iterrows()}
        cells = [v for grp in res["by"].values() for v in grp.values()]
        res["accepted"] = {m: bool(all(0.85 <= c[f"{m}_hit"] <= 0.95 for c in cells)) for m in ("cond", "aci")}
        res["width_vs_plain"] = float(np.nanmedian(ev["aci_w"]) / np.nanmedian(c90[ev.index]))
        out[var] = res
    return out


# ---------------------------------------------------------------- 4.2 timing, 4.3 thresholds
def harrell_c(risk: np.ndarray, time: np.ndarray, event: np.ndarray) -> float:
    """Concordance of a risk score with time to event (higher risk, earlier event); ties in risk count one half."""
    m = np.isfinite(risk) & np.isfinite(time)
    r, t, e = risk[m], time[m], event[m].astype(bool)
    num = den = 0.0
    order = np.argsort(t)
    r, t, e = r[order], t[order], e[order]
    for i in range(len(t)):
        if not e[i]:
            continue
        later = t > t[i]
        den += later.sum()
        num += (r[i] > r[later]).sum() + 0.5 * (r[i] == r[later]).sum()
    return float(num / den) if den else np.nan


def timing(df: pd.DataFrame, firms: np.ndarray, b: int) -> dict:
    out: dict = {}
    for ev, static in (("cash_half", "st_cash_min"), ("debt_raise", "st_fin_need")):
        tcol = f"rc_t_{ev}"
        if tcol not in df or f"tm_full_{ev}" not in df:
            continue
        t_ev = df[tcol].to_numpy(float)
        event = np.isfinite(t_ev)
        time = np.where(event, t_ev, 9.0)  # censored after eight quarters
        risks = {
            "twin": df[f"tm_full_{ev}"].to_numpy(float),
            "no_loops": df.get(f"tm_no_loops_{ev}", pd.Series(np.nan, index=df.index)).to_numpy(float),
            "static": (-1 if static == "st_cash_min" else 1) * df[static].to_numpy(float),
        }
        res: dict = {k: harrell_c(v, time, event) for k, v in risks.items()}
        idx = np.random.default_rng(1).choice(len(df), min(len(df), 6000), replace=False)  # C is O(n^2)
        d = S.boot(
            lambda a, c_, t_, e_: harrell_c(a, t_, e_) - harrell_c(c_, t_, e_),
            [risks["twin"][idx], risks["no_loops"][idx], time[idx], event[idx].astype(float)],
            firms[idx],
            b=b,
        )
        res["twin_minus_no_loops"] = {"diff": float(np.nanmean(d)), "ci": S.ci(d)}
        res["events"] = int(event.sum())
        out[ev] = res
    return out


def thresholds(df: pd.DataFrame) -> dict:
    rc = {
        "cash": ("rc_cash_min_ratio", lambda v, x: v < x),
        "debt": ("rc_debt_raise_ratio", lambda v, x: v > x),
        "div": ("rc_div_ratio", lambda v, x: v < 1 - x),
        "capex": ("rc_capex_ratio", lambda v, x: v < 1 - x),
    }
    out: dict = {}
    for ev, (col, rule) in rc.items():
        if col not in df:
            continue
        out[ev] = {}
        for c in [c for c in df if c.startswith(f"gr_full_{ev}_")]:
            x = float(c.rsplit("_", 1)[1])
            v = df[col].to_numpy(float)
            y = np.where(np.isfinite(v), rule(v, x).astype(float), np.nan)
            m = np.isfinite(y)
            out[ev][str(x)] = {
                "rate": float(np.nanmean(y)),
                "auc_twin": S.auc(df[c].to_numpy(float)[m], y[m]),
                "auc_no_loops": S.auc(df[c.replace("full", "no_loops")].to_numpy(float)[m], y[m])
                if c.replace("full", "no_loops") in df
                else None,
            }
    return out


# ---------------------------------------------------------------- 4.4 other downturns
def episodes(panel: pd.DataFrame, b: int) -> dict:
    """The 2020 exposure design applied to the 2015-16 commodity bust and the 2022 rate shock: each firm gets the
    leave-one-out median realized revenue shock of its industry, the twin is read at that depth."""
    import statsmodels.api as sm

    from .distress import _sic2

    out: dict = {}
    for year in (2015, 2020, 2022):
        p = panel[(panel["year"] == year)].reset_index(drop=True)
        grid = sorted(c for c in p if c.startswith("dg_"))
        if not grid or "y_rev_drop8" not in p:
            continue
        p = p[p["y_rev_drop8"].notna()].reset_index(drop=True)
        drop = p["y_rev_drop8"].astype(float)
        sic2 = _sic2(p["cik"])
        by_sic = drop.groupby(sic2).transform(T.loo_median).reindex(p.index)
        n_sic = drop.groupby(sic2).transform("count").reindex(p.index).fillna(0)
        by_ff = drop.groupby(p["industry"]).transform(T.loo_median)
        depth = np.clip(-np.where(n_sic >= 6, by_sic, by_ff) / 100, 0, 0.8)
        xs = np.array([float(c[3:]) for c in grid])
        H = p[grid].to_numpy(float)
        h = np.array(
            [
                np.interp(dd, xs, hh) if np.isfinite(dd) and np.isfinite(hh).all() else np.nan
                for dd, hh in zip(depth, H, strict=True)
            ]
        )
        res: dict = {"n": int(len(p)), "median_depth": float(np.nanmedian(depth))}
        for o in ("y_burn8", "y_abn_burn8"):
            sev = -p[o].to_numpy(float)
            fcf = -p["fcf_margin"].to_numpy(float)
            d = pd.DataFrame({"y": S.pct(sev), "exp": S.pct(depth), "twin": S.pct(-h), "fcf": S.pct(fcf)}).dropna()
            m = sm.OLS(d["y"], sm.add_constant(d[["exp", "twin", "fcf"]])).fit(cov_type="HC3")
            res[o] = {
                "rho_twin_at_exposure": S.rho(-h, sev),
                "rho_exposure": S.rho(depth, sev),
                "t": {k: float(m.tvalues[k]) for k in ("exp", "twin", "fcf")},
                "n": int(m.nobs),
            }
        out[str(year)] = res
    gen = [out[y]["y_abn_burn8"]["t"]["twin"] > 2 for y in ("2015", "2022") if y in out]
    out["generalizes"] = bool(len(gen) == 2 and all(gen))
    return out


# ---------------------------------------------------------------- 4.5 FCF mechanism
def _combo(b_: np.ndarray, adj: np.ndarray, real: np.ndarray, yrs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Walk-forward combination base + lambda * (adjuster - base), lambda chosen on earlier years."""
    pr = np.full(len(b_), np.nan)
    for y in sorted(set(yrs)):
        tr = (yrs < y) & np.isfinite(b_) & np.isfinite(adj) & np.isfinite(real)
        if tr.sum() < 200:
            continue
        err = [
            np.mean(np.abs(np.clip(b_[tr] + lam * (adj[tr] - b_[tr]), lo, hi) - np.clip(real[tr], lo, hi)))
            for lam in T.LAMBDAS
        ]
        lam = float(T.LAMBDAS[int(np.argmin(err))])
        te = yrs == y
        pr[te] = b_[te] + lam * (adj[te] - b_[te])
    return pr


def fcf_mechanism(df: pd.DataFrame) -> dict:
    """Out-of-sample gain of N3 + lambda(twin - N3) over N3 + lambda(regression - N3), for capex and operating cash
    flow separately; the share of the free-cash-flow gain that comes from capex."""
    out: dict = {}
    for var, base, null in (
        ("cfo", "N3_cfo", "ols_cfo"),
        ("capex", "N3_capex", "N5_capex"),
        ("fcf", "N3_fcf", "ols_fcf"),
    ):
        real = df[f"real_{var}"].to_numpy(float)
        b_, tw, nl = df[base].to_numpy(float), df[f"twin_{var}"].to_numpy(float), df[null].to_numpy(float)
        yrs = df["year"].to_numpy()
        lo, hi = np.nanpercentile(real, [1, 99])

        pt, pn = _combo(b_, tw, real, yrs, lo, hi), _combo(b_, nl, real, yrs, lo, hi)
        m = np.isfinite(pt) & np.isfinite(pn) & np.isfinite(real)
        e_t = np.mean(np.abs(np.clip(pt[m], lo, hi) - np.clip(real[m], lo, hi)))
        e_n = np.mean(np.abs(np.clip(pn[m], lo, hi) - np.clip(real[m], lo, hi)))
        out[var] = {"mae_twin_combo": float(e_t), "mae_null_combo": float(e_n), "gain": float(e_n - e_t)}
    g_fcf = out["fcf"]["gain"]
    out["capex_share_of_fcf_gain"] = float(out["capex"]["gain"] / g_fcf) if g_fcf else None
    out["capex_hypothesis_holds"] = bool(
        out["capex_share_of_fcf_gain"] is not None and out["capex_share_of_fcf_gain"] > 0.5
    )
    return out


# ---------------------------------------------------------------- 4.6 two-way bootstrap, Holm
def boot_two_way(stat, cols: list[np.ndarray], firms: np.ndarray, years: np.ndarray, b: int = 300) -> np.ndarray:
    """Pigeonhole bootstrap: resample firms and years independently and keep the firm-years in both draws."""
    rng = np.random.default_rng(11)
    fu, yu = pd.unique(firms), pd.unique(years)
    fi = {f: np.flatnonzero(firms == f) for f in fu}
    out = np.empty(b)
    for k in range(b):
        fs = rng.choice(fu, len(fu))
        ys = rng.choice(yu, len(yu))
        ycount = pd.Series(ys).value_counts()
        idx = np.concatenate([fi[f] for f in fs])
        mult = ycount.reindex(years[idx]).fillna(0).to_numpy(int)
        idx = np.repeat(idx, mult)
        out[k] = stat(*(c[idx] for c in cols))
    return out


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted((p, k) for k, p in pvals.items() if p is not None and np.isfinite(p))
    m, out, running = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def robustness_stats(tdf: pd.DataFrame, b: int) -> dict:
    """Key transmission statistics with firm x year clustering."""
    firms, years = tdf["ticker"].to_numpy(), tdf["year"].to_numpy()
    real, t1, n3 = (tdf[c].to_numpy(float) for c in ("real_cfo", "T1_cfo", "N3_cfo"))
    d = boot_two_way(S.rho, [t1 - n3, real - n3], firms, years, b)
    return {"incr_twin_vs_16q": S.rho(t1 - n3, real - n3), "ci_two_way": S.ci(d)}


# ---------------------------------------------------------------- 4.7 small firms
def small_firms(panel_all: pd.DataFrame, b: int) -> dict:
    lr = panel_all["log_rev"].astype(float)
    small = panel_all[(lr >= np.log(10e6)) & (lr < np.log(50e6))].reset_index(drop=True)
    if len(small) < 300:
        return {"n": int(len(small))}
    tr = T.section(small, b, panel=False)
    bk = small["y_bk8"].to_numpy(float)
    return {
        "n": int(len(small)),
        "n_firms": int(small["ticker"].nunique()),
        "incr_twin_vs_16q": tr.get("cfo", {}).get("incremental", {}).get("N3", {}).get("T1", {}).get("rho"),
        "median_ae": {k: tr.get("cfo", {}).get("levels", {}).get(k, {}).get("median_ae") for k in ("N3", "T1")},
        "auc_bk_twin": S.auc(-small["h_base"].to_numpy(float), bk),
        "auc_bk_formula": S.auc(-small["health_t0"].to_numpy(float), bk),
        "bk_events": int(np.nansum(bk)),
    }


# ---------------------------------------------------------------- verdicts
def verdicts(res: dict) -> dict:
    out: dict = {}
    bp = res.get("bankruptcy_panel", {}).get("all", {}).get("predictors", {})
    tf = (bp.get("formula") or {}).get("twin_minus") or {}
    out["H1_accepted"] = bool(tf and tf["ci"][0] > 0)
    dec = res.get("transmission", {}).get("panel", {}).get("decisions", {})
    wins = sum(1 for e in dec.values() if (e.get("twin_minus", {}).get("no_loops", {}).get("ci") or [0])[0] > 0)
    tim = res.get("plan2", {}).get("timing", {})
    c_ok = any((v.get("twin_minus_no_loops", {}).get("ci") or [0])[0] > 0 for v in tim.values())
    out["H3_auc_wins"] = wins
    out["H3_accepted"] = bool(wins >= 2 and c_ok)
    return out


def _safe(fn, *args) -> dict:
    """Run one analysis; a failure (e.g. outcomes missing in an older run) is recorded instead of stopping the rest."""
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def section(panel_all: pd.DataFrame, panel: pd.DataFrame, fc: pd.DataFrame, b: int) -> dict:
    df = frame(panel)
    firms = df["ticker"].to_numpy() if len(df) else np.array([])
    out: dict = {
        "revised_spec": _safe(revised_spec, df, firms, b),
        "overreaction": _safe(overreaction, df),
        "cash_hybrid": _safe(cash_hybrid, fc),
        "calibration": _safe(calibration, fc, panel),
        "timing": _safe(timing, df, firms, max(b // 5, 50)),
        "thresholds": _safe(thresholds, df),
        "episodes": _safe(episodes, panel, b),
        "fcf_mechanism": _safe(fcf_mechanism, df),
        "small_firms": _safe(small_firms, panel_all, b),
    }
    out["two_way"] = _safe(lambda: robustness_stats(T.add_shrunk(T.frame(panel)), b))
    return out

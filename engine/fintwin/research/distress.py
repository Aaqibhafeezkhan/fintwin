"""Bankruptcy tests on the census, the hard task among already-weak firms, and fragility versus exposure in 2020.

The first version of the paper compared 27 prominent Chapter 11 filers of 2020 with today's S&P 500, a task that
size alone nearly solves and in which the survivors are known to have survived. Here the event is any Item 1.03
8-K, the population is every non-financial XBRL filer alive at the cutoff, and a second test asks the question
practitioners care about: among firms that already look weak, which ones fail?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats as S

DATA = S.DATA


def _risk(df: pd.DataFrame, health: str, pb: str | None) -> pd.DataFrame:
    R = S.risk_frame(df, health, pb)
    if "h_base" in df and health != "h_base":
        R["twin_base"] = -df["h_base"].astype(float)
    return R


def _weak(df: pd.DataFrame, by: str | None) -> np.ndarray:
    """Already weak at the cutoff: bottom quintile of Altman's Z'' (within the cutoff year) or negative FCF margin."""
    z = df["z2"].astype(float)
    q = z.groupby(df[by]).transform(lambda s: s.quantile(0.2)) if by else z.quantile(0.2)
    return ((z <= q) | (df["fcf_margin"].astype(float) < 0)).to_numpy()


def auc_table(df: pd.DataFrame, y: np.ndarray, R: pd.DataFrame, firms: np.ndarray | None, b: int) -> dict:
    out: dict = {"n": int(np.isfinite(y).sum()), "events": int(np.nansum(y)), "predictors": {}}
    twin = R["twin"].to_numpy(float)
    for k in R.columns:
        x = R[k].to_numpy(float)
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() < 30 or y[m].sum() < 3:
            continue
        out["predictors"][k] = {
            "label": S.LABELS.get(k, k),
            "auc": S.auc(x[m], y[m]),
            "auc_ci": S.ci(S.boot(S.auc, [x[m], y[m]], None if firms is None else firms[m], b=b)),
            "n_events": int(y[m].sum()),
            "twin_minus": None if k == "twin" else S.paired(S.auc, twin, x, y, firms, b),
        }
    return out


def bankruptcy_2020(xs: pd.DataFrame, b: int) -> dict:
    """Chapter 11 / 7 petitions from 20 February 2020 to the end of 2021, every firm alive on the cutoff."""
    df = xs[np.isfinite(xs["bk_2020"].astype(float))].reset_index(drop=True)
    y = df["bk_2020"].to_numpy(float)
    R = _risk(df, "h_pandemic", "pb_pandemic")
    out = {"all": auc_table(df, y, R, None, b)}
    weak = _weak(df, None)
    out["weak"] = auc_table(df[weak].reset_index(drop=True), y[weak], R[weak].reset_index(drop=True), None, b)
    out["firms"] = df.loc[y == 1, ["ticker", "name", "sector", "h_pandemic", "h_base", "z2", "log_rev"]].to_dict(
        "records"
    )
    return out


def bankruptcy_panel(p: pd.DataFrame, b: int) -> dict:
    """Bankruptcy within eight quarters, every cutoff 2014-2024, all firms and the already-weak ones."""
    df = p[np.isfinite(p["y_bk8"].astype(float))].reset_index(drop=True)
    y = df["y_bk8"].to_numpy(float)
    firms = df["ticker"].to_numpy()
    R = _risk(df, "h_base", "pb_base")
    R["twin_rec"] = -df["h_rec"].astype(float)
    out = {"all": auc_table(df, y, R, firms, b)}
    weak = _weak(df, "year")
    out["weak"] = auc_table(df[weak].reset_index(drop=True), y[weak], R[weak].reset_index(drop=True), firms[weak], b)
    out["weak"]["share_of_events"] = float(y[weak].sum() / max(y.sum(), 1))
    out["by_year"] = {
        int(yr): {"n": int((df["year"] == yr).sum()), "events": int(y[(df["year"] == yr).to_numpy()].sum())}
        for yr in sorted(df["year"].unique())
    }
    return out


# ---------------------------------------------------------------- 2020: fragility versus exposure
def _sic2(ciks: pd.Series) -> pd.Series:
    if not (DATA / "universe_edgar.csv").exists():
        return pd.Series(np.nan, index=ciks.index)
    u = pd.read_csv(DATA / "universe_edgar.csv", usecols=["cik", "sic"])
    m = {int(c): float(s) for c, s in zip(u["cik"], u["sic"], strict=True) if pd.notna(s)}
    return ciks.map(lambda c: m[int(c)] // 100 if pd.notna(c) and int(c) in m else np.nan)


def exposure(xs: pd.DataFrame, b: int) -> dict:
    """Give each company its industry's realized 2020 revenue shock (leave-one-out median of peers' worst
    year-on-year revenue change, 2-digit SIC with at least five peers, else the Fama-French industry) and read the
    twin's stress score at that depth from the precomputed grid. If the twin's mechanics are right, knowing the
    exposure should let it rank who burned cash; comparing it with the exposure alone shows what fragility adds.
    """
    from .transmission import loo_median

    df = xs[xs["real_rev_drop"].notna()].reset_index(drop=True)
    grid = sorted(c for c in df if c.startswith("grid_"))
    if not grid:
        return {}
    df["sic2"] = _sic2(df["cik"])
    drop = df["real_rev_drop"].astype(float)
    by_sic = drop.groupby(df["sic2"]).transform(loo_median).reindex(df.index)
    n_sic = drop.groupby(df["sic2"]).transform("count").reindex(df.index).fillna(0)
    by_ff = drop.groupby(df["sector"]).transform(loo_median)
    shock = np.where(n_sic >= 6, by_sic, by_ff)
    depth = np.clip(-shock / 100, 0.0, 0.8)
    xs_depth = np.array([float(c[5:]) for c in grid])
    H = df[grid].to_numpy(float)
    h_exp = np.array(
        [
            np.interp(d, xs_depth, h) if np.isfinite(d) and np.isfinite(h).all() else np.nan
            for d, h in zip(depth, H, strict=True)
        ]
    )
    out: dict = {"n": int(len(df)), "median_depth": float(np.nanmedian(depth))}
    for outcome in ("real_burn", "real_abn_burn"):
        sev = -df[outcome].to_numpy(float)
        preds = {
            "twin_at_exposure": -h_exp,
            "exposure_only": depth,
            "twin_uniform": -df["h_pandemic"].to_numpy(float),
            "fcf_margin": -df["fcf_margin"].to_numpy(float),
        }
        res: dict = {}
        for k, x in preds.items():
            res[k] = {"rho": S.rho(x, sev), "ci": S.ci(S.boot(S.rho, [x, sev], b=b))}
        res["twin_at_exposure_minus_exposure"] = S.paired(S.rho, preds["twin_at_exposure"], depth, sev, None, b)
        res["twin_at_exposure_minus_fcf"] = S.paired(
            S.rho, preds["twin_at_exposure"], preds["fcf_margin"], sev, None, b
        )
        # what fragility adds to exposure: partial rank correlation, controlling for the exposure
        import statsmodels.api as sm

        d = pd.DataFrame(
            {"y": S.pct(sev), "exp": S.pct(depth), "twin": S.pct(-h_exp), "fcf": S.pct(preds["fcf_margin"])}
        ).dropna()
        m = sm.OLS(d["y"], sm.add_constant(d[["exp", "twin", "fcf"]])).fit(cov_type="HC3")
        res["regression"] = {k: {"coef": float(m.params[k]), "t": float(m.tvalues[k])} for k in ("exp", "twin", "fcf")}
        res["regression"]["n"] = int(m.nobs)
        out[outcome] = res
    return out

"""Large-sample validation, one company per process (memory-friendly), then pooled aggregation.

    uv run python -m fintwin.backtest.batch AAPL        # per-company: rolling-origin cases + COVID cross-section row
    uv run python -m fintwin.backtest.batch --aggregate # pool everything -> web/public/data/calibration.json

Rolling-origin design: for every company and every yearly cutoff (15 Feb 2013 ... 15 Feb 2025) the twin is
calibrated on point-in-time filings and forecasts the next 4 quarters. Online conformal calibration then
rescales interval widths using only forecasts made at *earlier* cutoffs, so the calibrated coverage is itself
out-of-sample.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ..data.facts import load_company
from ..data.fred import macro_quarterly
from ..model.sd_model import simulate
from ..scenarios.presets import DEFAULT_LEVERS, PRESETS, build_scenario
from ..stochastic.calibrate import calibrate
from ..stochastic.mc import summarize
from ..stochastic.shocks import draw_shocks
from .scoring import crps_gaussian, crps_samples

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "batch"
OUT = Path(__file__).resolve().parents[3] / "web" / "public" / "data" / "calibration.json"
ORIGINS = [f"{y}-02-15" for y in range(2013, 2026)]
H = 4
Q = [5, 25, 50, 75, 95]

# S&P 100-style large caps outside financials, plus the travel / leisure names most exposed to 2020.
UNIVERSE_XL = [
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NVDA",
    "TSLA",
    "AVGO",
    "ORCL",
    "ADBE",
    "CRM",
    "CSCO",
    "INTC",
    "AMD",
    "QCOM",
    "TXN",
    "IBM",
    "ACN",
    "INTU",
    "NFLX",
    "DIS",
    "CMCSA",
    "T",
    "VZ",
    "TMUS",
    "CHTR",
    "WMT",
    "COST",
    "HD",
    "LOW",
    "TGT",
    "NKE",
    "SBUX",
    "MCD",
    "KO",
    "PEP",
    "PG",
    "CL",
    "MDLZ",
    "PM",
    "MO",
    "KHC",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "LLY",
    "BMY",
    "AMGN",
    "GILD",
    "UNH",
    "CVS",
    "MDT",
    "ABT",
    "TMO",
    "DHR",
    "BA",
    "LMT",
    "RTX",
    "GD",
    "CAT",
    "DE",
    "HON",
    "MMM",
    "GE",
    "UPS",
    "FDX",
    "UNP",
    "EMR",
    "CVX",
    "COP",
    "NEE",
    "DUK",
    "SO",
    "LIN",
    "DOW",
    "BKNG",
    "CCL",
    "RCL",
    "NCLH",
    "DAL",
    "UAL",
    "AAL",
    "LUV",
    "MAR",
    "HLT",
    "M",
    "KSS",
    "MGM",
    "LVS",
    "WYNN",
    "EXPE",
    "ABNB",
    "UBER",
]


def _realized(full: pd.DataFrame, after: pd.Timestamp) -> pd.DataFrame:
    r = full[full.index > after + pd.Timedelta(days=20)].head(H).copy()
    r["cash_like"] = r["cash"] + r["short_investments"]
    return r


def _baseline(hist: pd.DataFrame, var: str, h: int) -> tuple[float, float]:
    if var == "revenue":
        s = hist["revenue"].dropna()
        same = s.iloc[-4 + ((h - 1) % 4)]
        yoy = np.log(s / s.shift(4)).dropna().tail(20)
        return float(same), float(same * yoy.std() * np.sqrt(int(np.ceil(h / 4))))
    s = (hist["cash"] + hist["short_investments"]).dropna()
    return float(s.iloc[-1]), float(s.diff().tail(20).std() * np.sqrt(h))


def _vintage(hist, origin: str | None, macro) -> dict:
    """The twin as it stood at one point in time: horizon-12 parameters and its baseline verdict."""
    p12 = calibrate(hist, macro, 12)
    sm = summarize(simulate(p12, build_scenario({}, 12), draw_shocks(p12, 1500, 12, seed=5), DEFAULT_LEVERS))
    return {
        "asof": origin or "latest",
        "last_quarter": hist.quarters.index[-1].date().isoformat(),
        "health": sm["health_score"],
        "health_p10": sm["health_p10"],
        "p_breach": sm["p_breach"],
        "params": {k: v for k, v in p12.items() if k != "_sources"},
    }


def company_cases(ticker: str, n_paths: int = 2000) -> dict:
    full_data = load_company(ticker)
    full = full_data.quarters
    cases, skipped, vintages = [], {}, []
    for origin in ORIGINS:
        try:
            hist = load_company(ticker, asof=origin)
            if len(hist.quarters) < 16:
                skipped[origin] = "fewer than 16 quarters of history"
                continue
            vintages.append(_vintage(hist, origin, macro_quarterly(origin)))
            real = _realized(full, hist.quarters.index[-1])
            if len(real) < H:
                skipped[origin] = "not enough realized quarters yet"
                continue
            p = calibrate(hist, macro_quarterly(origin), H)
            eps = draw_shocks(p, n_paths, H, seed=11)
            sims = {
                flag: simulate(p, build_scenario({}, H), eps, {**DEFAULT_LEVERS, "recessions": flag})
                for flag in (True, False)
            }
            for var, key in (("revenue", "revenue"), ("cash_like", "cash")):
                for h in range(H):
                    y = float(real[var].iloc[h])
                    if not np.isfinite(y):
                        continue
                    mu_b, sd_b = _baseline(hist.quarters, var, h + 1)
                    row = {
                        "origin": origin,
                        "var": var,
                        "h": h + 1,
                        "y": y,
                        "target": str(real.index[h].date()),
                        "crps_baseline": crps_gaussian(mu_b, sd_b, y),
                    }
                    for flag, out in sims.items():
                        x = out[key][:, h]
                        tag = "reg" if flag else "noreg"
                        row[f"q_{tag}"] = np.percentile(x, Q).tolist()
                        row[f"pit_{tag}"] = float(np.mean(x <= y))
                        row[f"crps_{tag}"] = crps_samples(x, y)
                    cases.append(row)
        except Exception as e:  # keep going: report why a cutoff could not be used
            skipped[origin] = f"{type(e).__name__}: {e}"
    try:
        vintages.append(_vintage(full_data, None, macro_quarterly()))
    except Exception as e:
        skipped["latest"] = f"{type(e).__name__}: {e}"
    cash_like = full["cash"] + full["short_investments"]
    timeline = {
        "ticker": ticker,
        "series": {
            "dates": [d.date().isoformat() for d in full.index],
            "revenue": full["revenue"].round(0).tolist(),
            "cash": cash_like.round(0).tolist(),
            "debt": full["total_debt"].round(0).tolist(),
        },
        "vintages": vintages,
    }
    return {
        "ticker": ticker,
        "cases": cases,
        "skipped": skipped,
        "covid": covid_row(ticker, full),
        "timeline": timeline,
    }


def covid_row(ticker: str, full: pd.DataFrame) -> dict | None:
    """Pre-COVID twin under the demand-freeze scenario vs realized 2020-21 cash burn."""
    try:
        cutoff = "2020-02-20"
        hist = load_company(ticker, asof=cutoff)
        if len(hist.quarters) < 16:
            return None
        p = calibrate(hist, macro_quarterly(cutoff), 8)
        eps = draw_shocks(p, 2000, 8, seed=7)
        st = summarize(simulate(p, build_scenario(PRESETS["pandemic"]["knobs"], 8), eps, DEFAULT_LEVERS))
        win = full[(full.index > pd.Timestamp("2020-01-15")) & (full.index <= pd.Timestamp("2021-07-15"))]
        fcf = (win["cfo"] - win["capex"]).fillna(0).cumsum()
        rev_ttm = float(hist.quarters["revenue"].tail(4).sum())
        if not len(fcf):
            return None
        return {
            "ticker": ticker,
            "name": hist.name,
            "health_stress": st["health_score"],
            "p_breach_stress": st["p_breach"],
            "realized_min_cum_fcf_pct_rev": float(fcf.min() / rev_ttm * 100),
            "realized_debt_raise_pct_rev": float((win["total_debt"].max() - p["debt0"]) / rev_ttm * 100),
        }
    except Exception:
        return None


def _scores(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    q = np.array(df[f"q_{tag}"].tolist())
    y = df["y"].values
    half90, half50 = (q[:, 4] - q[:, 0]) / 2, (q[:, 3] - q[:, 1]) / 2
    return pd.DataFrame(
        {
            "s90": np.abs(y - q[:, 2]) / np.maximum(half90, 1e-9),
            "s50": np.abs(y - q[:, 2]) / np.maximum(half50, 1e-9),
            "hit90": (y >= q[:, 0]) & (y <= q[:, 4]),
            "hit50": (y >= q[:, 1]) & (y <= q[:, 3]),
        },
        index=df.index,
    )


def aggregate() -> dict:
    files = sorted(CACHE.glob("*.json"))
    per = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    df = pd.DataFrame([c | {"ticker": r["ticker"]} for r in per for c in r["cases"]])
    df["year"] = df["origin"].str[:4].astype(int)
    res: dict = {
        "n_companies": int(df["ticker"].nunique()),
        "n_forecasts": int(len(df)),
        "origins": ORIGINS,
        "horizon": H,
        "vars": {},
    }
    for var, g in df.groupby("var"):
        g = g.copy()
        sc = _scores(g, "reg")
        g = g.join(sc)
        # online conformal: the scale factor for origin 15 Feb Y uses only forecasts whose target quarter had been
        # reported by then (quarter end + 75 days), so no error is used before it was observable
        conf90, conf50, factors = [], [], {}
        target = pd.to_datetime(g["target"]) if "target" in g else pd.to_datetime(g["year"].astype(str) + "-01-01")
        for year, gy in g.groupby("year"):
            seen = target + pd.Timedelta(days=75) <= pd.Timestamp(f"{year}-02-15")
            past = g[(g["year"] < year) & seen]
            if len(past) < 40:
                continue
            c90, c50 = float(np.quantile(past["s90"], 0.9)), float(np.quantile(past["s50"], 0.5))
            factors[int(year)] = {"c90": c90, "c50": c50}
            conf90 += list(gy["s90"] <= c90)
            conf50 += list(gy["s50"] <= c50)
        eval_mask = g["year"].isin(list(factors))
        pit = np.histogram(g["pit_reg"], bins=10, range=(0, 1))[0] / len(g)
        by_year = {
            int(y): {
                "cov90": float(gy["hit90"].mean()),
                "n": int(len(gy)),
                "skill": float(1 - gy["crps_reg"].mean() / gy["crps_baseline"].mean()),
            }
            for y, gy in g.groupby("year")
        }
        res["vars"][var] = {
            "n": int(len(g)),
            "raw": {
                "coverage90": float(g.loc[eval_mask, "hit90"].mean()),
                "coverage50": float(g.loc[eval_mask, "hit50"].mean()),
            },
            "conformal": {"coverage90": float(np.mean(conf90)), "coverage50": float(np.mean(conf50))},
            "conformal_factors": factors,
            "crps_skill_vs_naive": float(1 - g["crps_reg"].mean() / g["crps_baseline"].mean()),
            "median_case_skill": float((1 - g["crps_reg"] / g["crps_baseline"]).median()),
            "share_cases_beating_naive": float((g["crps_reg"] < g["crps_baseline"]).mean()),
            "regime_ablation": {
                "crps_with": float(g["crps_reg"].mean()),
                "crps_without": float(g["crps_noreg"].mean()),
                "improvement_pct": float((1 - g["crps_reg"].mean() / g["crps_noreg"].mean()) * 100),
            },
            "pit_hist": pit.round(4).tolist(),
            "by_year": by_year,
            "by_horizon": {int(h): float(gh["hit90"].mean()) for h, gh in g.groupby("h")},
        }
    rows = [r["covid"] for r in per if r.get("covid")]
    xs = pd.DataFrame(rows)
    rho, pval = spearmanr(xs["health_stress"], xs["realized_min_cum_fcf_pct_rev"])
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(2000):
        b = xs.sample(len(xs), replace=True, random_state=int(rng.integers(1_000_000_000)))
        boot.append(spearmanr(b["health_stress"], b["realized_min_cum_fcf_pct_rev"])[0])
    # decile view: realized burn of the twin's most vs least fragile fifth
    xs["quintile"] = pd.qcut(xs["health_stress"].rank(method="first"), 5, labels=False)
    quint = xs.groupby("quintile")["realized_min_cum_fcf_pct_rev"].median().round(1).tolist()
    severe = (xs["realized_min_cum_fcf_pct_rev"] < -10).groupby(xs["quintile"]).mean().round(3).tolist()
    res["cross_section"] = {
        "n": int(len(xs)),
        "spearman": float(rho),
        "p_value": float(pval),
        "ci95": [float(np.nanpercentile(boot, 2.5)), float(np.nanpercentile(boot, 97.5))],
        "quintile_median_burn": quint,
        "quintile_share_severe_burn": severe,
        "rows": rows,
    }
    res["skipped"] = {r["ticker"]: r["skipped"] for r in per if r["skipped"]}
    OUT.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    return res


if __name__ == "__main__":
    warnings.simplefilter("ignore")
    arg = sys.argv[1]
    if arg == "--aggregate":
        r = aggregate()
        print(json.dumps({k: v for k, v in r.items() if k not in ("vars", "cross_section", "skipped")}))
        for var, v in r["vars"].items():
            print(
                var,
                {
                    k: v[k]
                    for k in (
                        "n",
                        "raw",
                        "conformal",
                        "crps_skill_vs_naive",
                        "share_cases_beating_naive",
                        "regime_ablation",
                    )
                },
            )
        cs = r["cross_section"]
        print(
            "cross-section",
            {
                k: cs[k]
                for k in ("n", "spearman", "p_value", "ci95", "quintile_median_burn", "quintile_share_severe_burn")
            },
        )
    else:
        CACHE.mkdir(parents=True, exist_ok=True)
        t = arg.upper()
        res = company_cases(t)
        (CACHE / f"{t}.json").write_text(json.dumps(res), encoding="utf-8")
        print(f"{t}: {len(res['cases'])} cases, {len(res['skipped'])} skipped, covid={'yes' if res['covid'] else 'no'}")

"""Global (Sobol) sensitivity of the transmission result to every assumed parameter at once (plan 2, item 4.1).

    python -m fintwin.research sobol-shard 3 16   # -> .cache/sobol/<key>_<year>.json
    python -m fintwin.research sobol-stats        # -> docs/paper/sobol_assumptions.json

The one-at-a-time analysis varies each judgement call alone. Here all eight vary jointly over wide ranges in a Saltelli
design shared by every firm-year, so interactions show up. For a random sample of firm-years (cutoffs 2016-2022), each
design point recalibrates the twin, feeds it the realized revenue, and records its eight-quarter operating cash flow.
The outputs are the median absolute error across firm-years and the incremental correlation against the four-quarter
margin, each as a function of the design point; Sobol indices (Saltelli 2010, Jansen 1999) decompose their variance.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = [
    ("fixed_share_prior", 0.02, 0.60, "calib", "Fixed-cost prior"),
    ("prior_weight", 0.0, 10.0, "calib", "Weight of the prior"),
    ("revolver_share", 0.02, 0.20, "calib", "Credit line when untagged"),
    ("growth_shrink", 0.0, 1.0, "calib", "Weight on own trend growth"),
    ("beta_shrink", 0.0, 1.0, "calib", "Weight on own GDP beta"),
    ("access_hi", 1.0, 3.0, "p", "Coverage below which access is cut"),
    ("cut_speed", 0.0, 0.10, "p", "Restructuring speed"),
    ("cut_floor", 0.70, 1.00, "p", "Restructuring floor"),
]
N_BASE = 64
N_SAMPLE = 320
CACHE = Path(__file__).resolve().parents[2] / ".cache" / "sobol"
OUT = Path(__file__).resolve().parents[3] / "docs" / "paper" / "sobol_assumptions.json"


def design(n_base: int = N_BASE, seed: int = 41) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    rng = np.random.default_rng(seed)
    lo = np.array([f[1] for f in FACTORS])
    hi = np.array([f[2] for f in FACTORS])
    k = len(FACTORS)
    A = lo + rng.random((n_base, k)) * (hi - lo)
    B = lo + rng.random((n_base, k)) * (hi - lo)
    AB = [np.where(np.arange(k) == i, B, A) for i in range(k)]
    return A, B, AB


def points() -> np.ndarray:
    A, B, AB = design()
    return np.vstack([A, B, *AB])


def sample(seed: int = 7) -> list[tuple[str, int]]:
    from .__main__ import research_tickers

    rng = np.random.default_rng(seed)
    keys = research_tickers()
    return [(keys[i], int(rng.integers(2016, 2023))) for i in rng.choice(len(keys), 4 * N_SAMPLE, replace=False)]


def _one(key: str, year: int, X: np.ndarray) -> dict | None:
    from ..data.facts import load_company
    from ..data.fred import macro_quarterly
    from ..model.sd_model import simulate
    from ..scenarios.presets import DEFAULT_LEVERS, build_scenario
    from ..stochastic.shocks import draw_shocks
    from .experiments import _margin, _ttm, calibrate, usable

    origin = f"{year}-02-15"
    hist = load_company(key, asof=origin)
    if not usable(hist, origin):
        return None
    full = load_company(key).quarters
    pre = hist.quarters
    nxt = full[full.index > pre.index[-1] + pd.Timedelta(days=20)].head(8)
    rev_ttm = _ttm(pre, "revenue")
    if len(nxt) < 8 or nxt["revenue"].isna().any() or nxt["cfo"].isna().any() or not rev_ttm > 50e6:
        return None
    m4 = _margin(pre, pre["cfo"], 4)
    if not np.isfinite(m4):
        return None
    rev = nxt["revenue"].to_numpy(float)
    macro = macro_quarterly(origin)
    twin = []
    for x in X:
        calib = {f[0]: float(v) for f, v in zip(FACTORS, x, strict=True) if f[3] == "calib"}
        pv = {f[0]: float(v) for f, v in zip(FACTORS, x, strict=True) if f[3] == "p"}
        p = {**calibrate(hist, macro, 12, calib), "sector_tol": 1.0}
        p["access_icr"] = (pv["access_hi"], 0.53 * pv["access_hi"])
        p["cut_speed"], p["cut_floor"] = pv["cut_speed"], pv["cut_floor"]
        scn = build_scenario({}, 12)
        override = np.full(12, np.nan)
        override[:8] = rev
        scn["revenue_override"] = override
        sim = simulate(p, scn, draw_shocks(p, 200, 12, seed=3), DEFAULT_LEVERS)
        twin.append(float(np.median(sim["cfo"][:, :8], axis=0).sum() / rev_ttm * 100))
    return {
        "key": key,
        "year": year,
        "real": float(nxt["cfo"].sum() / rev_ttm * 100),
        "n1": float(m4 * rev.sum() / rev_ttm * 100),
        "twin": twin,
    }


def shard(i: int, n: int) -> None:
    from ..export import _clean

    CACHE.mkdir(parents=True, exist_ok=True)
    X = points()
    done = 0
    for k, (key, year) in enumerate(sample()):
        if k % n != i or done >= N_SAMPLE // n:
            continue
        out = CACHE / f"{key}_{year}.json"
        if out.exists():
            done += 1
            continue
        try:
            r = _one(key, year, X)
        except Exception as e:  # a firm that cannot be loaded is skipped
            print(f"  {key} {year}: {type(e).__name__}: {e}", flush=True)
            continue
        if r is None:
            continue
        out.write_text(json.dumps(_clean(r)), encoding="utf-8")
        done += 1
        print(f"  {key} {year} done ({done})", flush=True)


def indices(f: np.ndarray, n_base: int, k: int, rng: np.random.Generator, n_boot: int = 500) -> list[dict]:
    fA, fB = f[:n_base], f[n_base : 2 * n_base]
    fAB = [f[(2 + i) * n_base : (3 + i) * n_base] for i in range(k)]

    def est(idx):
        a, b = fA[idx], fB[idx]
        var = np.var(np.concatenate([a, b]), ddof=1)
        s1 = np.array([np.mean(b * (g[idx] - a)) / var for g in fAB])
        st = np.array([0.5 * np.mean((a - g[idx]) ** 2) / var for g in fAB])
        return s1, st

    s1, st = est(np.arange(n_base))
    boot = [est(rng.integers(0, n_base, n_base)) for _ in range(n_boot)]
    b1, bt = np.array([b[0] for b in boot]), np.array([b[1] for b in boot])
    return [
        {
            "factor": FACTORS[i][0],
            "label": FACTORS[i][4],
            "range": [FACTORS[i][1], FACTORS[i][2]],
            "S1": float(s1[i]),
            "ST": float(st[i]),
            "S1_ci": np.percentile(b1[:, i], [2.5, 97.5]).tolist(),
            "ST_ci": np.percentile(bt[:, i], [2.5, 97.5]).tolist(),
        }
        for i in range(k)
    ]


def stats() -> dict:
    from scipy.stats import spearmanr

    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CACHE.glob("*.json"))]
    real = np.array([r["real"] for r in rows])
    n1 = np.array([r["n1"] for r in rows])
    T = np.array([r["twin"] for r in rows])  # firm-years x design points
    mae = np.median(np.abs(T - real[:, None]), axis=0)
    incr = np.array([spearmanr(T[:, j] - n1, real - n1)[0] for j in range(T.shape[1])])
    rng = np.random.default_rng(3)
    k = len(FACTORS)
    out = {
        "n_firm_years": int(len(rows)),
        "n_points": int(T.shape[1]),
        "median_ae": {
            "mean": float(mae.mean()),
            "min": float(mae.min()),
            "max": float(mae.max()),
            "indices": indices(mae, N_BASE, k, rng),
        },
        "incremental": {
            "mean": float(incr.mean()),
            "min": float(incr.min()),
            "max": float(incr.max()),
            "indices": indices(incr, N_BASE, k, rng),
        },
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out

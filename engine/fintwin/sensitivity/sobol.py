"""Variance-based global sensitivity (Sobol indices) of the health score to the stress knobs.

One-at-a-time tornado charts miss interactions (a rate shock hurts far more when revenue is also falling).
Sobol indices decompose the variance of the output over the *joint* scenario space:
  S1_i = first-order share of variance explained by knob i alone (Saltelli 2010 estimator)
  ST_i = total share including all interactions (Jansen 1999 estimator)
Common random numbers keep the Monte Carlo noise out of the decomposition.
"""

from __future__ import annotations

import numpy as np

from ..model.sd_model import simulate
from ..scenarios.presets import DEFAULT_LEVERS, build_scenario
from ..stochastic.shocks import draw_shocks

FACTORS = [
    ("sales_depth", 0.0, 0.5, "Revenue shock"),
    ("rate_bp", -100.0, 400.0, "Interest rates"),
    ("spread_bp", 0.0, 600.0, "Credit spreads"),
    ("cost_pp", 0.0, 6.0, "Variable costs"),
    ("refi_freeze", 0.0, 4.0, "Debt-market freeze"),
    ("dio_days", 0.0, 60.0, "Inventory build-up"),
]
INTEGER = {"refi_freeze"}


def _evaluate(p: dict, X: np.ndarray, eps: np.ndarray) -> np.ndarray:
    T = p["horizon"]
    out = np.empty(len(X))
    for i, row in enumerate(X):
        knobs = {k: (round(v) if k in INTEGER else float(v)) for (k, *_), v in zip(FACTORS, row, strict=True)}
        res = simulate(p, build_scenario(knobs, T), eps, DEFAULT_LEVERS)
        out[i] = res["health"].mean()
    return out


def sobol(p: dict, n_base: int = 256, n_paths: int = 300, seed: int = 5, n_boot: int = 200) -> dict:
    k = len(FACTORS)
    rng = np.random.default_rng(seed)
    lo = np.array([f[1] for f in FACTORS])
    hi = np.array([f[2] for f in FACTORS])
    A = lo + rng.random((n_base, k)) * (hi - lo)
    B = lo + rng.random((n_base, k)) * (hi - lo)
    eps = draw_shocks(p, n_paths, p["horizon"], seed=seed)
    fA, fB = _evaluate(p, A, eps), _evaluate(p, B, eps)
    fAB = [_evaluate(p, np.where(np.arange(k) == i, B, A), eps) for i in range(k)]

    def indices(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a, b = fA[idx], fB[idx]
        var = np.var(np.concatenate([a, b]), ddof=1)
        if var < 1e-12:
            return np.zeros(k), np.zeros(k)
        s1 = np.array([np.mean(b * (f[idx] - a)) / var for f in fAB])
        st = np.array([0.5 * np.mean((a - f[idx]) ** 2) / var for f in fAB])
        return s1, st

    s1, st = indices(np.arange(n_base))
    boot = [indices(rng.integers(0, n_base, n_base)) for _ in range(n_boot)]
    b1, bt = np.array([b[0] for b in boot]), np.array([b[1] for b in boot])
    rows = []
    for i, (key, _, _, label) in enumerate(FACTORS):
        rows.append(
            {
                "knob": key,
                "label": label,
                "range": [float(lo[i]), float(hi[i])],
                "S1": float(np.clip(s1[i], 0, st[i] if st[i] > 0 else 1)),
                "ST": float(max(st[i], 0)),
                "S1_ci": np.percentile(b1[:, i], [5, 95]).clip(0).tolist(),
                "ST_ci": np.percentile(bt[:, i], [5, 95]).clip(0).tolist(),
            }
        )
    rows.sort(key=lambda r: -r["ST"])
    out_sd = float(np.std(np.concatenate([fA, fB]), ddof=1))
    # interaction share: variance not explained by first-order effects
    return {
        "rows": rows,
        "output_sd": out_sd,
        "interaction_share": float(max(0.0, 1 - sum(r["S1"] for r in rows))),
        "n_runs": int(n_base * (k + 2)),
        "insensitive": out_sd < 1.0,
    }

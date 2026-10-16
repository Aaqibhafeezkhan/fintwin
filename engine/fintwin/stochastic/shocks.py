"""Standardized shock generation: correlated, fat-tailed, unit-variance draws.

Columns: 0 = demand (revenue growth), 1 = variable-cost margin, 2 = short rate, 3 = discretionary financing.
Kept separate from the model core so both engines can be fed identical shocks in parity tests.
"""
from __future__ import annotations

import numpy as np


def draw_shocks(p: dict, n_paths: int, horizon: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_paths, horizon, 4))
    rho = p["rho_gm"]
    z[:, :, 1] = rho * z[:, :, 0] + np.sqrt(1 - rho**2) * z[:, :, 1]
    df = p["t_df"]
    if df < 30:
        # Student-t via a shared chi-square mixing variable per path-quarter, rescaled to unit variance.
        w = rng.chisquare(df, (n_paths, horizon, 1)) / df
        z[:, :, :2] = z[:, :, :2] / np.sqrt(w) * np.sqrt((df - 2) / df)
    return z

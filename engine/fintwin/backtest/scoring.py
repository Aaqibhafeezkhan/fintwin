"""Probabilistic forecast scoring: interval coverage, PIT and CRPS."""

from __future__ import annotations

import numpy as np


def crps_samples(samples: np.ndarray, y: float) -> float:
    """CRPS of an empirical forecast distribution: E|X - y| - 0.5 E|X - X'| (sorted-sample formula)."""
    x = np.sort(np.asarray(samples, float))
    n = len(x)
    term1 = np.mean(np.abs(x - y))
    i = np.arange(1, n + 1)
    term2 = np.sum((2 * i - n - 1) * x) / (n * n)
    return float(term1 - term2)


def crps_gaussian(mu: float, sigma: float, y: float) -> float:
    from scipy.stats import norm

    sigma = max(sigma, 1e-12)
    z = (y - mu) / sigma
    return float(sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi)))


def pit(samples: np.ndarray, y: float) -> float:
    return float(np.mean(np.asarray(samples) <= y))


def interval_hit(samples: np.ndarray, y: float, level: float) -> bool:
    lo, hi = np.percentile(samples, [50 - level / 2, 50 + level / 2])
    return bool(lo <= y <= hi)

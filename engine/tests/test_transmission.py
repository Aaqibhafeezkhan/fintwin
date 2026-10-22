"""The transmission test must not reward a predictor for being smoother than the four-quarter rule."""

import numpy as np
import pandas as pd

from fintwin.research import transmission as T


def _rows(twin_kind: str, n_firms: int = 150, years=range(2014, 2024), seed: int = 0) -> pd.DataFrame:
    """Firms whose true cash margin is persistent; the 4-quarter margin is that plus transitory noise.

    `smooth`: the twin is just the 16-quarter margin (no knowledge of where cash goes).
    `informed`: the twin also knows a firm-year shock to cash conversion that no margin rule sees.
    """
    rng = np.random.default_rng(seed)
    recs = []
    for f in range(n_firms):
        mu = rng.normal(0.12, 0.05)
        for y in years:
            info = rng.normal(0, 0.03)
            m16 = mu + rng.normal(0, 0.005)
            m4 = mu + rng.normal(0, 0.04)
            m8 = 0.5 * (m4 + m16)
            rev = np.full(8, 25.0) * rng.uniform(0.8, 1.2)
            real = (mu + info) * rev + rng.normal(0, 0.5, 8)
            twin_m = m16 + rng.normal(0, 0.01) + (info if twin_kind == "informed" else 0.0)  # with model noise
            st = {
                "rev": rev.tolist(),
                "real_cfo": real.tolist(),
                "real_fcf": (real - 1).tolist(),
                "m": {"cfo4": m4, "cfo8": m8, "cfo16": m16, "fcf4": m4 - 0.04, "fcf8": m8 - 0.04, "fcf16": m16 - 0.04},
                "ols_cfo": (m16 * rev).tolist(),
                "ols_fcf": (m16 * rev - 1).tolist(),
                "dyn_cfo": (m16 * rev).tolist(),
                "dyn_fcf": (m16 * rev - 1).tolist(),
                "twin_cfo": (twin_m * rev).tolist(),
                "twin_fcf": (twin_m * rev - 1).tolist(),
                "noloops_cfo": (twin_m * rev).tolist(),
                "noloops_fcf": (twin_m * rev - 1).tolist(),
            }
            recs.append({"ticker": f"F{f}", "year": y, "industry": ["A", "B", "C"][f % 3], "st": st,
                         "nd_ebitda": rng.normal(), "fixed_share": rng.uniform(), "due_cash": rng.uniform(),
                         "health_t0": 50.0, "fcf_margin": m4, "z2": 3.0, "log_rev": 20.0, "h_base": 60.0,
                         "y_bk8": 0.0, "y_burn8": 0.0})
    return pd.DataFrame(recs)


def test_smoother_predictor_passes_old_test_but_not_the_new_one():
    res = T.section(_rows("smooth"), b=40)
    inc = res["cfo"]["incremental"]
    assert inc["N1"]["T1"]["rho"] > 0.3  # the old statistic is fooled by smoothing
    assert abs(inc["N3"]["T1"]["rho"]) < 0.15  # against the 16-quarter margin there is nothing left
    assert res["verdict"]["transmission_claim_survives"] is False


def test_informed_predictor_survives_every_null():
    res = T.section(_rows("informed"), b=40)
    inc = res["cfo"]["incremental"]
    assert inc["N3"]["T1"]["rho"] > 0.3 and inc["N6"]["T1"]["rho"] > 0.3
    assert res["cfo"]["encompassing"]["all"]["p"]["T1"] < 0.01
    assert res["cfo"]["hybrid"]["mae_w"]["N1+T1"] < res["cfo"]["hybrid"]["mae_w"]["N1"]
    assert res["verdict"]["transmission_claim_survives"] is True


def test_loo_median_excludes_own_value():
    s = pd.Series([1.0, 2.0, 3.0, 100.0, np.nan])
    out = T.loo_median(s)
    assert out.iloc[0] == 3.0 and out.iloc[3] == 2.0 and np.isnan(out.iloc[4])


def test_shrinkage_weight_uses_only_earlier_years():
    df = T.add_shrunk(T.frame(_rows("smooth", n_firms=60)))
    w = df.attrs["N4_weights_cfo"]
    assert w[2014] == 0.5  # no earlier year to learn from
    assert set(w) == set(range(2014, 2024))

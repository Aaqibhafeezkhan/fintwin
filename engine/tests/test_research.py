import numpy as np

from fintwin.data.edgar import ticker_to_cik
from fintwin.model.sd_model import simulate
from fintwin.research.stats import auc, pct, rho
from fintwin.scenarios.presets import DEFAULT_LEVERS, PRESETS, build_scenario
from fintwin.stochastic.shocks import draw_shocks
from fintwin.universe import classify


def test_auc_and_ranks():
    y = np.array([0, 0, 1, 1, 0, 1], float)
    assert auc(np.array([1, 2, 5, 6, 3, 4.0]), y) == 1.0
    assert auc(-np.array([1, 2, 5, 6, 3, 4.0]), y) == 0.0
    assert np.isnan(auc(np.ones(3), np.zeros(3)))
    assert pct(np.array([3.0, np.nan, 1.0]))[1] != pct(np.array([3.0, np.nan, 1.0]))[1]  # NaN preserved
    assert rho(np.arange(10.0), np.arange(10.0) ** 2) > 0.99


def test_loop_switches_default_on_and_bite(params):
    scn = build_scenario(PRESETS["pandemic"]["knobs"], 12)
    eps = draw_shocks(params, 300, 12, seed=1)
    base = simulate(params, scn, eps, DEFAULT_LEVERS)
    same = simulate(params, scn, eps, {**DEFAULT_LEVERS, "loop_r1": True, "loop_r2": True})
    assert np.array_equal(base["cash"], same["cash"])  # the product never changes
    off = simulate(params, scn, eps, {**DEFAULT_LEVERS, "loop_r1": False, "loop_r2": False})
    assert np.abs(off["identity_gap"]).max() < 1e-6


def test_delisted_lookup_is_offline():
    assert ticker_to_cik("HTZ~2020") == (1657853, "Hertz Global Holdings")
    assert classify("CHK~2020")[0] == "Energy"

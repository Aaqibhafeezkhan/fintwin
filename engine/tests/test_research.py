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


def _synthetic_research(tmp_path, n=120, bankrupt=12):
    """Research JSONs where a latent fragility drives both the twin's score and realized burn."""
    import json

    rng = np.random.default_rng(0)
    sectors = ["Energy", "Industrials", "Consumer Discretionary", "Information Technology"]
    for i in range(n + bankrupt):
        frag = rng.uniform()
        bk = i >= n
        h = 80 - 70 * frag + rng.normal(0, 8)
        feats = {
            k: float(rng.normal())
            for k in (
                "z2",
                "o_score",
                "zmijewski",
                "nd_ebitda",
                "icr",
                "cash_rev",
                "current_ratio",
                "static_cover",
                "rev_vol",
                "fixed_share",
                "log_rev",
            )
        }
        run = {"health": h, "p_breach": float(frag > 0.7), "health_p10": h - 10}
        rec = {
            "ticker": f"T{i}" + ("~2020" if bk else ""),
            "bankrupt_2020": bk,
            "errors": {},
            "covid": {
                "ticker": f"T{i}",
                "name": f"Firm {i}",
                "sector": sectors[i % 4],
                "scenarios": {
                    k: run for k in ("base", "rates_200", "sales_20", "recession", "pandemic", "credit_crunch")
                },
                "ablations": {k: run for k in ("full", "no_r1", "no_r2", "no_b1", "no_b2", "no_loops")},
                "sector_adjusted": run,
                "features": feats,
                "realized": {}
                if bk
                else {
                    "burn": float(-30 * frag + rng.normal(0, 4)),
                    "rev_drop": float(-60 * rng.uniform()),
                    "debt_raise": 1.0,
                    "cash_min_ratio": 1.0,
                    "div_payer": True,
                    "div_cut": bool(frag > 0.6),
                },
            },
            "panel": []
            if bk
            else [
                {
                    "origin": f"{y}-02-15",
                    "base": run,
                    "recession": run,
                    "features": feats,
                    "outcome": {
                        "burn8": float(-30 * frag + rng.normal(0, 6)),
                        "icr0": 3.0,
                        "icr_min": float(4 - 4 * frag),
                        "div_payer": True,
                        "div_cut": bool(rng.uniform() < frag / 2),
                    },
                }
                for y in range(2013, 2024)
            ],
            "forecasts": []
            if bk
            else [
                {
                    "origin": "2019-02-15",
                    "var": v,
                    "h": h_,
                    "scale": 100.0,
                    "crps_twin": float(rng.uniform(1, 2)),
                    "crps_rw": float(rng.uniform(1.5, 2.5)),
                    "crps_ets": float(rng.uniform(1.5, 2.5)),
                    "pit_ets": 0.5,
                }
                for v in ("revenue", "cash_like")
                for h_ in range(1, 5)
            ],
        }
        (tmp_path / f"T{i}.json").write_text(json.dumps(rec))
    return tmp_path


def test_stats_pipeline_recovers_planted_signal(tmp_path, monkeypatch):
    import fintwin.research.stats as st

    monkeypatch.setattr(st, "OUT", tmp_path / "research.json")
    monkeypatch.setattr(st, "B", 50)
    monkeypatch.setattr(st, "B_PANEL", 30)
    res = st.main(_synthetic_research(tmp_path))
    c = res["covid"]
    assert c["predictors"]["twin"]["rho"] > 0.6 and abs(c["predictors"]["altman_z2"]["rho"]) < 0.3
    assert c["regression"]["t"]["twin"] > 3
    assert res["bankruptcy"]["n_bankrupt"] == 12
    sb = res["panel"]["severe_burn"]
    assert sb["univariate"]["twin"]["auc"] > 0.8
    assert sb["out_of_sample"]["benchmarks_plus_twin"]["auc"] > sb["out_of_sample"]["benchmarks"]["auc"]
    assert res["forecasts"]["revenue"]["ets"]["skill_scaled"] > 0
    assert (tmp_path / "research.json").exists()


def test_health_at_open_is_a_valid_score_near_the_first_simulated_quarter(params):
    from fintwin.research.experiments import health_at_open

    h0 = health_at_open({**params, "sector_tol": 1.0})
    assert 0 <= h0 <= 100
    out = simulate(
        {**params, "sigma_g": 0.0, "sigma_m": 0.0, "sigma_r": 0.0, "sigma_fin": 0.0},
        build_scenario({}, 4),
        np.zeros((1, 4, 5)) + [0, 0, 0, 0, 0.99],
        DEFAULT_LEVERS,
    )
    assert abs(out["health"][0, 0] - h0) < 25  # one quarter of steady-state dynamics moves the score only a little

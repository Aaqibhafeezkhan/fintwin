"""Second-round statistics: concordance, Holm, two-way bootstrap, Sobol indices and the XBRL fallback merge."""

import numpy as np

from fintwin.research import plan2


def test_harrell_c_orders_risk_and_time():
    time = np.array([1.0, 2.0, 3.0, 9.0, 9.0])
    event = np.array([1, 1, 1, 0, 0], float)
    assert plan2.harrell_c(np.array([5.0, 4.0, 3.0, 1.0, 0.0]), time, event) == 1.0
    assert plan2.harrell_c(np.array([0.0, 1.0, 3.0, 4.0, 5.0]), time, event) == 0.0
    assert plan2.harrell_c(np.ones(5), time, event) == 0.5


def test_holm_is_monotone_and_capped():
    adj = plan2.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert adj["a"] == 0.04 and adj["c"] == 0.09 and adj["b"] == 0.09 and adj["d"] == 0.5
    assert all(v <= 1 for v in adj.values())


def test_two_way_bootstrap_resamples_firms_and_years():
    rng = np.random.default_rng(0)
    firms = np.repeat(np.arange(40), 5)
    years = np.tile(np.arange(5), 40)
    x = rng.normal(size=200)
    y = x + rng.normal(scale=0.5, size=200)
    d = plan2.boot_two_way(lambda a, b: np.corrcoef(a, b)[0, 1], [x, y], firms, years, b=50)
    assert np.isfinite(d).all() and 0.7 < np.median(d) < 1.0


def test_sobol_indices_recover_a_linear_model():
    from fintwin.research.assumption_sobol import indices

    rng = np.random.default_rng(1)
    n, k = 512, 2
    A, B = rng.random((n, k)), rng.random((n, k))
    AB = [np.where(np.arange(k) == i, B, A) for i in range(k)]

    def f(x):
        return 3 * x[:, 0] + x[:, 1]

    out = indices(np.concatenate([f(A), f(B), *[f(m) for m in AB]]), n, k, rng, n_boot=20)
    assert abs(out[0]["ST"] - 0.9) < 0.1 and abs(out[1]["ST"] - 0.1) < 0.05


def test_combo_learns_weight_from_earlier_years_only():
    years = np.repeat(np.arange(2014, 2024), 100)
    real = np.random.default_rng(2).normal(size=1000)
    base = real + 1.0
    adj = real  # the adjuster is exactly right, so lambda should go to its largest value
    out = plan2._combo(base, adj, real, years, -10, 10)
    # trained on cutoffs up to Y-3 (outcomes known by Y); 200 firm-years first available for 2018
    assert np.isnan(out[years < 2018]).all() and np.allclose(out[years >= 2018], base[years >= 2018] - 1.0, atol=0.6)


def test_xbrl_fallback_merges_missing_filings(monkeypatch):
    from fintwin.data import xbrl_fallback as X

    raw = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"accn": "old", "end": "2026-03-31", "val": 1.0}]}}}}}
    monkeypatch.setattr(
        X,
        "periodic_filings",
        lambda cik: [
            {"accn": "old", "form": "10-Q", "filed": "2026-04-30", "primary": "a.htm"},
            {"accn": "new", "form": "10-Q", "filed": "2026-07-29", "primary": "b.htm"},
        ],
    )
    monkeypatch.setattr(X, "_instance_name", lambda cik, accn, primary: "b_htm.xml")
    monkeypatch.setattr(X, "_download", lambda cik, accn, name: b"x")
    monkeypatch.setattr(
        X,
        "parse_instance",
        lambda content, tags, accn, form, filed: {
            "Revenues": [
                {"start": "2026-04-01", "end": "2026-06-30", "val": 2.0, "accn": accn, "form": form, "filed": filed}
            ]
        },
    )
    out = X.augment(1, raw, {"Revenues"})
    rows = out["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert [r["accn"] for r in rows] == ["old", "new"] and out["_fallback"] == ["new"]
    monkeypatch.setenv("FINTWIN_XBRL_FALLBACK", "0")
    assert X.augment(1, {"facts": {}}, {"Revenues"}) == {"facts": {}}

import numpy as np

from fintwin.backtest.scoring import crps_gaussian, crps_samples, interval_hit, pit


def test_sample_crps_matches_closed_form_gaussian():
    rng = np.random.default_rng(0)
    x = rng.normal(2.0, 3.0, 200_000)
    for y in [-4.0, 2.0, 7.5]:
        assert abs(crps_samples(x, y) - crps_gaussian(2.0, 3.0, y)) < 0.02


def test_crps_rewards_sharp_correct_forecasts():
    rng = np.random.default_rng(1)
    assert crps_samples(rng.normal(0, 0.1, 5000), 0.0) < crps_samples(rng.normal(0, 1.0, 5000), 0.0)


def test_pit_and_intervals():
    x = np.arange(101.0)
    assert pit(x, 50.0) == 51 / 101
    assert interval_hit(x, 50.0, 90) and not interval_hit(x, 99.0, 90)

"""Tests for Monte Carlo summaries and strategy comparison."""

import numpy as np
import pytest

from f1lab.sim.engine import simulate
from f1lab.sim.montecarlo import compare_strategies, mean_interval, summarise, wilson_interval
from f1lab.sim.strategy import parse_strategy
from synthetic import make_setup, params


def test_wilson_interval_known_values() -> None:
    low, high = wilson_interval(np.array([50]), 100)
    assert (low[0], high[0]) == pytest.approx((0.4038, 0.5962), abs=1e-4)


def test_wilson_interval_at_the_edges() -> None:
    low, high = wilson_interval(np.array([0, 100]), 100)
    assert low[0] == pytest.approx(0.0, abs=1e-12)
    assert 0 < high[0] < 0.05
    assert 0.95 < low[1] < 1
    assert high[1] == pytest.approx(1.0)


def test_mean_interval_shrinks_with_more_runs() -> None:
    rng = np.random.default_rng(0)
    _, low_small, high_small = mean_interval(rng.normal(size=100))
    _, low_big, high_big = mean_interval(rng.normal(size=10_000))
    assert high_big - low_big < (high_small - low_small) / 5


def test_summary_of_a_deterministic_race() -> None:
    setup = make_setup([0.0, 1.0, 2.0])  # car0 fastest and on pole
    table = summarise(simulate(setup, params()))
    assert list(table.index) == ["car0", "car1", "car2"]
    assert table.loc["car0", "p_win"] == 1.0
    assert table.loc["car2", "mean_position"] == 3.0
    assert table.loc["car2", "p_podium"] == 1.0  # only three cars
    assert (table["p_retire"] == 0).all()


def test_summary_probabilities_have_intervals() -> None:
    setup = make_setup([0.0, 0.05, 0.1, 0.15], lap_noise_sd_s=0.8, form_sd_s=0.3)
    table = summarise(simulate(setup, params(runs=1000)))
    assert table["p_win"].sum() == pytest.approx(1.0)
    assert (table["p_win_low"] <= table["p_win"]).all()
    assert (table["p_win"] <= table["p_win_high"]).all()
    assert (table["mean_low"] < table["mean_position"]).all()


def test_compare_strategies_prefers_the_cheaper_plan() -> None:
    setup = make_setup([0.0, 0.0, 0.0])
    plans = [parse_strategy("M-5-H-15-S"), parse_strategy("M-10-H")]
    table = compare_strategies(setup, "car0", plans, params())
    assert list(table["notation"]) == ["M-5-H-15-S", "M-10-H"]
    assert table.loc[0, "delta_vs_first"] == 0.0
    assert table.loc[1, "mean_position"] < table.loc[0, "mean_position"]
    assert table.loc[1, "delta_high"] < 0  # better in every paired run


def test_compare_strategies_with_noise_has_a_paired_interval() -> None:
    setup = make_setup([0.0, 0.1, 0.2, 0.3], lap_noise_sd_s=0.6, sc_hazard=0.05)
    plans = [parse_strategy("M-10-H"), parse_strategy("S-6-M-14-H")]
    table = compare_strategies(setup, "car1", plans, params(runs=500))
    second = table.loc[1]
    assert second["delta_low"] <= second["delta_vs_first"] <= second["delta_high"]

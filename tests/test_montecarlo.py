"""Tests for Monte Carlo summaries and strategy comparison."""

import numpy as np
import pytest

from f1lab.sim.engine import SAFETY_CAR, VIRTUAL_SAFETY_CAR, simulate
from f1lab.sim.montecarlo import (
    compare_strategies,
    mean_interval,
    neutralisation_shares,
    position_histogram,
    sc_sensitivity,
    summarise,
    wilson_interval,
)
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
    assert table.loc[1, "histogram"].tolist() == [1.0, 0.0, 0.0, 0.0]  # always wins, never out


def test_compare_strategies_with_noise_has_a_paired_interval() -> None:
    setup = make_setup([0.0, 0.1, 0.2, 0.3], lap_noise_sd_s=0.6, sc_hazard=0.05)
    plans = [parse_strategy("M-10-H"), parse_strategy("S-6-M-14-H")]
    table = compare_strategies(setup, "car1", plans, params(runs=500))
    second = table.loc[1]
    assert second["delta_low"] <= second["delta_vs_first"] <= second["delta_high"]


def test_position_histogram_counts_finishes_and_retirements() -> None:
    positions = np.array([[1, 2], [2, 1], [1, 2], [2, 1]])
    retired = np.array([[False, False], [False, False], [False, True], [False, True]])
    shares = position_histogram(positions, retired, field_size=2)
    assert shares.tolist() == [[0.5, 0.5, 0.0], [0.25, 0.25, 0.5]]
    assert shares.sum(axis=1) == pytest.approx([1.0, 1.0])


def test_neutralisation_shares() -> None:
    states = np.array([[0, SAFETY_CAR, 0], [0, 0, 0], [VIRTUAL_SAFETY_CAR, 0, SAFETY_CAR], [0] * 3])
    assert neutralisation_shares(states) == (0.5, 0.25)


def test_sc_sensitivity_rows_and_safety_car_share() -> None:
    setup = make_setup([0.0, 0.0, 0.0], sc_lap1_probability=0.3, sc_hazard=0.02)
    plans = [parse_strategy("M-10-H"), parse_strategy("M-5-H-15-S")]
    table = sc_sensitivity(setup, "car1", plans, [0.0, 1.0, 2.0], params(runs=200))
    assert len(table) == 6
    shares = table.groupby("scale")["p_safety_car"]
    assert (shares.nunique() == 1).all()  # strategies at one scale share the Safety Cars
    by_scale = shares.first()
    assert by_scale[0.0] == 0.0
    assert by_scale[0.0] < by_scale[1.0] < by_scale[2.0]
    calm = table[table["scale"] == 0.0].set_index("notation")
    assert calm.loc["M-10-H", "mean_position"] < calm.loc["M-5-H-15-S", "mean_position"]

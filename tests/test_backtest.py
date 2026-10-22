"""Tests for backtesting the simulator against real results."""

import pytest
from sqlalchemy import Engine

from f1lab.sim.backtest import (
    backtest,
    best_race_craft,
    prepare_races,
    score_race,
    score_summary,
    search_race_craft,
    season_race_ids,
)
from f1lab.sim.calibration import calibrate, load_history
from f1lab.sim.engine import simulate
from f1lab.sim.montecarlo import summarise
from synthetic import actual, make_setup, params


def test_perfect_prediction_scores_perfectly() -> None:
    setup = make_setup([0.0, 1.0, 2.0])  # car0 wins, car2 last, every run
    race = score_race(setup, actual([1, 2, 3], [1, 2, 3]), params())
    assert race.spearman == pytest.approx(1.0)
    assert race.mae == 0.0
    assert race.grid_mae == 0.0
    assert list(race.table.index) == ["car0", "car1", "car2"]


def test_simulator_can_beat_the_grid() -> None:
    # car2 starts last but is much faster: the simulator sees it win, as it did.
    setup = make_setup([0.0, 0.5, -3.0])
    race = score_race(setup, actual([2, 3, 1], [1, 2, 3]), params())
    assert race.mae < race.grid_mae
    assert race.spearman > race.grid_spearman


def test_score_summary_matches_score_race() -> None:
    setup = make_setup([0.0, 0.5, -3.0], lap_noise_sd_s=0.5)
    real = actual([2, 3, 1], [1, 2, 3])
    summary = summarise(simulate(setup, params()))
    assert score_summary(setup, summary, real).mae == score_race(setup, real, params()).mae


def test_retired_drivers_are_not_scored() -> None:
    setup = make_setup([0.0, 1.0, 2.0])
    race = score_race(setup, actual([1, 2, 3], [1, 2, 3], [True, True, False]), params())
    assert race.mae == 0.0  # car2 (retired in reality) does not count


def test_overall_scores() -> None:
    setup = make_setup([0.0, 1.0, 2.0])
    prepared = [(setup, actual([1, 2, 3], [1, 2, 3])), (setup, actual([1, 3, 2], [1, 2, 3]))]
    result = backtest(prepared, params(), skipped={99: "wet"})
    overall = result.overall()
    assert overall["races"] == 2
    assert overall["mae"] == pytest.approx((0 + 2 / 3) / 2)
    assert result.skipped == {99: "wet"}
    assert len(result.summary()) == 2


def test_race_craft_search_ranks_by_error() -> None:
    # car1 is 0.8 s/lap faster from P2: it should pass, as it did in reality.
    setup = make_setup([0.0, -0.8])
    prepared = [(setup, actual([2, 1], [1, 2]))]
    search = search_race_craft(prepared, [0.5, 2.0], [0.0], params())
    assert len(search) == 2
    assert best_race_craft(search) == (0.5, 0.0)
    assert search["mae"].is_monotonic_increasing


def test_races_that_cannot_be_simulated_are_skipped(loaded: Engine) -> None:
    calibration, models = calibrate(load_history(loaded, [2024]))
    assert season_race_ids(loaded, [2024]) == [202401, 202421]
    prepared, skipped = prepare_races(loaded, [202401, 202421], calibration, models)
    assert prepared == []
    assert set(skipped) == {202401, 202421}  # trimmed fixture stints; wet São Paulo
    assert "dry-only" in skipped[202421] or "No tyre model" in skipped[202421]

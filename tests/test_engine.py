"""Tests for the race engine on hand-built setups with known outcomes."""

import numpy as np
import pytest
from sqlalchemy import Engine

from f1lab.db import schema
from f1lab.sim.calibration import calibrate, load_history
from f1lab.sim.engine import SAFETY_CAR, SimulationParams, simulate
from f1lab.sim.setup import RaceSetup, SetupError, race_setup
from f1lab.sim.strategy import StrategyError, parse_strategy
from synthetic import complete_stints, make_setup, params


def winner(setup: RaceSetup, **overrides: object) -> set[str]:
    result = simulate(setup, params(**overrides))
    return {setup.drivers[i] for i in np.argmin(result.positions, axis=1)}


def test_much_faster_car_overtakes() -> None:
    assert winner(make_setup([0.0, -1.0])) == {"car1"}


def test_slightly_faster_car_is_held_behind() -> None:
    assert winner(make_setup([0.0, -0.3])) == {"car0"}


def test_dirty_air_slows_the_follower() -> None:
    setup = make_setup([0.0, 0.0])
    clean = simulate(setup, params())
    dirty = simulate(setup, params(dirty_air_penalty_s=0.4))
    gap = lambda r: (r.total_time_s[:, 1] - r.total_time_s[:, 0]).mean()  # noqa: E731
    assert gap(dirty) > gap(clean)


def test_one_stop_beats_two_stops_without_wear() -> None:
    setup = make_setup(
        [0.0, 0.0],
        strategies={"car0": parse_strategy("M-5-H-15-S"), "car1": parse_strategy("M-10-H")},
    )
    assert winner(setup) == {"car1"}


def test_safety_car_bunches_the_field() -> None:
    setup = make_setup([0.0, 0.5], sc_hazard=1.0, sc_lengths_laps=np.array([100]))
    result = simulate(setup, params(restart_gap_s=0.8))
    assert (result.track_state[:, 1:] == SAFETY_CAR).all()
    gap = result.total_time_s[:, 1] - result.total_time_s[:, 0]
    assert np.allclose(gap, 0.8)


def test_retired_cars_rank_behind_every_finisher() -> None:
    setup = make_setup(
        [0.0, 0.1, 0.2, 0.3], dnf_probability=0.5, dnf_race_fraction=np.array([0.2, 0.9])
    )
    result = simulate(setup, params(runs=500))
    for positions, retired in zip(result.positions, result.retired, strict=True):
        if retired.any() and not retired.all():
            assert positions[~retired].max() < positions[retired].min()
    assert 0.3 < result.retired.mean() < 0.7


def test_positions_are_a_permutation() -> None:
    result = simulate(make_setup([0.0, 0.1, 0.2], lap_noise_sd_s=0.5), params(runs=200))
    assert (np.sort(result.positions, axis=1) == np.arange(1, 4)).all()


def test_same_seed_same_result_other_seed_differs() -> None:
    setup = make_setup([0.0, 0.05, 0.1], lap_noise_sd_s=0.6, form_sd_s=0.3)
    first, again = simulate(setup, params(seed=1)), simulate(setup, params(seed=1))
    other = simulate(setup, params(seed=2))
    assert np.array_equal(first.positions, again.positions)
    assert not np.array_equal(first.positions, other.positions)


def test_common_random_numbers_across_strategies() -> None:
    setup = make_setup(
        [0.0, 0.1, 0.2],
        lap_noise_sd_s=0.5,
        sc_hazard=0.05,
        dnf_probability=0.2,
        dnf_race_fraction=np.array([0.3, 0.6]),
    )
    other = setup.with_strategy("car0", parse_strategy("S-6-M-14-H"))
    base, alternative = simulate(setup, params()), simulate(other, params())
    assert np.array_equal(base.track_state, alternative.track_state)
    assert np.array_equal(base.retired, alternative.retired)


def test_illegal_strategy_is_rejected() -> None:
    setup = make_setup([0.0, 0.0]).with_strategy("car0", parse_strategy("M-10-M"))
    with pytest.raises(StrategyError):
        simulate(setup, params())


def test_unknown_driver_cannot_change_strategy() -> None:
    with pytest.raises(SetupError):
        make_setup([0.0]).with_strategy("nobody", parse_strategy("M-10-H"))


def test_race_setup_from_the_database(loaded: Engine) -> None:
    calibration, models = calibrate(load_history(loaded, [2024]))
    complete_stints(loaded, 202401, laps=57)
    setup = race_setup(loaded, 202401, calibration, models)
    assert setup.race_laps == 57
    assert len(setup.drivers) == 20
    assert setup.drivers[0] == "max_verstappen"  # pole and P1 on the grid
    assert setup.strategies["max_verstappen"].notation() == "S3-17-H-37-S"
    pole = setup.level_s[0]
    assert pole == setup.level_s.min()  # the pole sitter is the fastest on paper
    result = simulate(setup, SimulationParams(runs=200))
    assert result.positions.shape == (200, 20)


def test_wet_race_is_rejected(loaded: Engine) -> None:
    calibration, models = calibrate(load_history(loaded, [2024]))
    with pytest.raises(SetupError, match=r"No tyre model|dry-only"):
        race_setup(loaded, 202421, calibration, models)


def test_compound_without_any_model_is_rejected(loaded: Engine) -> None:
    # Fitted on the fixtures only, Bahrain has no MEDIUM and no other circuit to borrow from.
    calibration, models = calibrate(load_history(loaded, [2024]))
    complete_stints(loaded, 202401, laps=57)
    with loaded.begin() as conn:
        conn.execute(
            schema.stints.update()
            .where(schema.stints.c.race_id == 202401)
            .where(schema.stints.c.driver_id == "leclerc")
            .where(schema.stints.c.stint == 1)
            .values(compound="MEDIUM")
        )
    with pytest.raises(SetupError, match="MEDIUM"):
        race_setup(loaded, 202401, calibration, models)

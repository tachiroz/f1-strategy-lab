"""Tests for simulator calibration: each estimator on data with a known answer."""

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Engine

from f1lab.config import MIN_CIRCUIT_PIT_STOPS
from f1lab.models.degradation import driver_levels, fit_circuits
from f1lab.models.neutralisation import GREEN, Neutralisation, Period
from f1lab.sim.calibration import (
    SC,
    VSC,
    calibrate,
    estimate_grid_slot,
    estimate_neutralisations,
    estimate_pit_losses,
    estimate_quali_pace,
    estimate_retirements,
    load_history,
)

START = pd.Timestamp("2025-01-01 12:00:00", tz="UTC")
LAP_S = 90.0


def race_laps(drivers: int, laps: int, race_id: int = 1, circuit: str = "ring") -> pd.DataFrame:
    """Every driver laps in 90 s on mediums; no pit stops yet."""
    rows = [
        {
            "race_id": race_id,
            "circuit_id": circuit,
            "driver_id": f"d{number:02d}",
            "lap": lap,
            "start_time_utc": START + pd.Timedelta(seconds=(lap - 1) * LAP_S),
            "lap_time_s": LAP_S,
            "is_pit_in_lap": False,
            "is_pit_out_lap": False,
            "compound": "MEDIUM",
            "neutralised": False,
        }
        for number in range(drivers)
        for lap in range(1, laps + 1)
    ]
    return pd.DataFrame(rows)


def add_stop(laps: pd.DataFrame, driver: str, lap: int, in_extra: float, out_extra: float) -> None:
    """Make ``driver`` pit at the end of ``lap`` losing in_extra + out_extra seconds."""
    mine = laps["driver_id"] == driver
    laps.loc[mine & (laps["lap"] == lap), ["is_pit_in_lap"]] = True
    laps.loc[mine & (laps["lap"] == lap), "lap_time_s"] += in_extra
    laps.loc[mine & (laps["lap"] == lap + 1), ["is_pit_out_lap"]] = True
    laps.loc[mine & (laps["lap"] == lap + 1), "lap_time_s"] += out_extra


def test_grid_slot() -> None:
    first = race_laps(drivers=10, laps=1)
    results = pd.DataFrame({"race_id": 1, "driver_id": first["driver_id"], "grid": range(1, 11)})
    first["lap_time_s"] = LAP_S + 0.5 * results["grid"].to_numpy()
    assert estimate_grid_slot(first, results) == pytest.approx(0.5)


def test_pit_losses_relative_to_the_field() -> None:
    drivers = MIN_CIRCUIT_PIT_STOPS + 5
    laps = race_laps(drivers=drivers, laps=10)
    for number in range(drivers - 2):  # two drivers never pit: they are the field
        add_stop(laps, f"d{number:02d}", lap=5, in_extra=8.0, out_extra=14.0)
    states = pd.Series(GREEN, index=laps.index)
    rain = pd.Series(False, index=laps.index)
    per_circuit, everything, sc_ratio, vsc_ratio = estimate_pit_losses(laps, states, rain)
    assert np.allclose(everything, 22.0)
    assert np.allclose(per_circuit["ring"], 22.0)
    assert (sc_ratio, vsc_ratio) == (1.0, 1.0)  # no stops under SC/VSC


def test_pit_losses_under_safety_car_are_cheaper() -> None:
    laps = race_laps(drivers=6, laps=10)
    add_stop(laps, "d00", lap=3, in_extra=8.0, out_extra=14.0)
    add_stop(laps, "d01", lap=6, in_extra=5.0, out_extra=6.0)
    states = pd.Series(GREEN, index=laps.index)
    states[laps["lap"].isin([6, 7])] = SC
    rain = pd.Series(False, index=laps.index)
    _, everything, sc_ratio, _ = estimate_pit_losses(laps, states, rain)
    assert np.allclose(everything, 22.0)  # only the green stop is a sample
    assert sc_ratio == pytest.approx(11.0 / 22.0)


def test_neutralisation_frequencies_and_lengths() -> None:
    laps = pd.concat([race_laps(2, 50, race_id=r, circuit=c) for r, c in ((1, "a"), (2, "b"))])
    results = pd.DataFrame(
        {"race_id": [1, 2], "driver_id": "d00", "laps": [50, 50], "circuit_id": ["a", "b"]}
    )
    at = START + pd.Timedelta(seconds=20 * LAP_S + 10)  # during lap 21
    periods = {
        1: [
            Period(
                Neutralisation.SAFETY_CAR,
                START + pd.Timedelta(seconds=10),
                START + pd.Timedelta(seconds=10 + 4 * LAP_S),
            ),
            Period(Neutralisation.SAFETY_CAR, at, at + pd.Timedelta(seconds=5 * LAP_S)),
        ],
        2: [Period(Neutralisation.VIRTUAL_SAFETY_CAR, at, at + pd.Timedelta(seconds=LAP_S))],
    }
    stats = estimate_neutralisations(laps, periods, results)
    assert stats[SC].lap1_probability == 0.5  # one of two races
    assert stats[SC].hazard_all == pytest.approx(1 / 98)  # one later SC over 2 x 49 laps
    assert stats[SC].hazard["a"] > stats[SC].hazard_all > stats[SC].hazard["b"]
    assert sorted(stats[SC].lengths_laps) == [4, 5]
    assert list(stats[VSC].lengths_laps) == [1]


def test_retirements() -> None:
    results = pd.DataFrame(
        {
            "race_id": 1,
            "laps": [50, 50, 25, 10, 0, 50],
            "status": [
                "Finished",
                "Lapped",
                "Retired",
                "Accident",
                "Did not start",
                "Disqualified",
            ],
        }
    )
    probability, fractions = estimate_retirements(results)
    # The DNS is not a starter; the DSQ started and did not retire.
    assert probability == pytest.approx(2 / 5)
    assert sorted(fractions) == [0.2, 0.5]


def test_quali_pace_slope_is_positive(synthetic_laps: pd.DataFrame) -> None:
    models = fit_circuits(synthetic_laps)
    levels = pd.concat(
        driver_levels(models["testring"], race) for _, race in synthetic_laps.groupby("race_id")
    ).reset_index()
    levels["position"] = levels.groupby("race_id")["level_s"].rank(method="first")
    slope, form_sd = estimate_quali_pace(synthetic_laps, models, levels)
    assert slope > 0
    assert form_sd < levels["level_s"].std()


def test_calibrate_on_recorded_races(loaded: Engine) -> None:
    calibration, models = calibrate(load_history(loaded, [2024]))
    assert set(models) == {"bahrain"}  # São Paulo 2024 was wet: no clean laps
    assert calibration.seasons == (2024,)
    assert 0 < calibration.dnf_probability < 1
    assert len(calibration.pit_losses("bahrain")) > 0  # falls back to all circuits
    sc_hazard, vsc_hazard = calibration.hazards("unknown circuit")
    assert (sc_hazard, vsc_hazard) == (calibration.sc_hazard_all, calibration.vsc_hazard_all)

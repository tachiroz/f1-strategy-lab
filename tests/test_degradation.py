"""Tests for the per-circuit degradation model, on synthetic laps with known parameters."""

import pandas as pd
import pytest

from f1lab.config import MIN_COMPOUND_LAPS
from f1lab.models.degradation import (
    driver_levels,
    fit_circuit,
    fit_circuits,
    parameters_table,
    predict,
)
from synthetic import (
    TRUE_DEGRADATION_S_PER_LAP,
    TRUE_FUEL_S_PER_LAP,
    TRUE_OFFSET_S,
    make_synthetic_laps,
)


def test_recovers_fuel_offsets_and_degradation(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps)
    assert model.reference_compound == "MEDIUM"
    assert model.fuel_s_per_lap.value == pytest.approx(TRUE_FUEL_S_PER_LAP, abs=0.005)
    for compound, slope in TRUE_DEGRADATION_S_PER_LAP.items():
        assert model.degradation_s_per_lap[compound].value == pytest.approx(slope, abs=0.005)
    for compound, offset in TRUE_OFFSET_S.items():
        assert model.compound_offset_s[compound].value == pytest.approx(offset, abs=0.05)
    assert model.residual_sd_s == pytest.approx(0.15, abs=0.02)


def test_confidence_intervals_bracket_the_estimates(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps)
    for estimate in [model.fuel_s_per_lap, *model.degradation_s_per_lap.values()]:
        assert estimate.low < estimate.value < estimate.high
    fuel = model.fuel_s_per_lap
    assert fuel.low < TRUE_FUEL_S_PER_LAP < fuel.high


def test_predictions_match_lap_times(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps)
    predicted = predict(model, synthetic_laps, driver_levels(model, synthetic_laps))
    mae = (synthetic_laps["lap_time_s"] - predicted).abs().mean()
    assert mae < 0.15  # noise sd 0.15 -> MAE about 0.12


def test_no_degradation_ablation(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps, with_degradation=False)
    assert model.degradation_s_per_lap == {}
    predicted = predict(model, synthetic_laps, driver_levels(model, synthetic_laps))
    assert predicted.notna().all()
    assert (synthetic_laps["lap_time_s"] - predicted).abs().mean() > 0.3


def test_rare_compound_is_left_out(synthetic_laps: pd.DataFrame) -> None:
    soft = synthetic_laps[synthetic_laps["compound"] == "SOFT"]
    rare = pd.concat(
        [synthetic_laps[synthetic_laps["compound"] != "SOFT"], soft.head(MIN_COMPOUND_LAPS - 1)]
    )
    model = fit_circuit(rare)
    assert model.compounds == ["HARD", "MEDIUM"]
    assert model.relative_pace(soft).isna().all()


def test_single_stint_races_are_not_identifiable(synthetic_laps: pd.DataFrame) -> None:
    # Like Spa 2025: every driver on one compound from lap 2 to the flag, so tyre
    # age = lap - 2 for everyone and fuel cannot be separated from degradation.
    one_stint = synthetic_laps.assign(compound="MEDIUM", tyre_age=synthetic_laps["lap"] - 2)
    with pytest.raises(ValueError, match="not identifiable"):
        fit_circuit(one_stint)


def test_one_circuit_per_fit(synthetic_laps: pd.DataFrame) -> None:
    other = make_synthetic_laps(circuit_id="other", seed=8)
    with pytest.raises(ValueError, match="one circuit"):
        fit_circuit(pd.concat([synthetic_laps, other]))


def test_fit_circuits_skips_circuits_without_data(synthetic_laps: pd.DataFrame) -> None:
    tiny = make_synthetic_laps(circuit_id="tiny", drivers=1, seasons=(2023,)).head(10)
    models = fit_circuits(pd.concat([synthetic_laps, tiny]))
    assert list(models) == ["testring"]


def test_parameters_table(synthetic_laps: pd.DataFrame) -> None:
    table = parameters_table(fit_circuits(synthetic_laps).values())
    assert list(table["compound"]) == ["HARD", "MEDIUM", "SOFT"]
    soft = table.set_index("compound").loc["SOFT"]
    assert soft["degradation_low"] < soft["degradation_s_per_lap"] < soft["degradation_high"]
    assert soft["reference_compound"] == "MEDIUM"

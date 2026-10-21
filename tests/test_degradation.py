"""Tests for the per-circuit degradation model, on synthetic laps with known parameters."""

import pandas as pd
import pytest

from f1lab.config import MIN_COMPOUND_LAPS
from f1lab.models.degradation import (
    Z_SCORE,
    CircuitModel,
    Estimate,
    driver_levels,
    fit_circuit,
    fit_circuits,
    parameters_table,
    pool_degradation,
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


def make_model(circuit_id: str, slopes: dict[str, tuple[float, float]]) -> CircuitModel:
    """A circuit model with given degradation (value, standard error) per compound."""
    return CircuitModel(
        circuit_id=circuit_id,
        seasons=(2024,),
        n_laps=100,
        reference_compound="MEDIUM",
        fuel_s_per_lap=Estimate(-0.05, -0.06, -0.04),
        compound_offset_s={c: Estimate(0.0, 0.0, 0.0) for c in slopes},
        degradation_s_per_lap={
            c: Estimate(v, v - Z_SCORE * se, v + Z_SCORE * se) for c, (v, se) in slopes.items()
        },
    )


def test_age_cap_holds_wear_beyond_the_data(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps)
    soft_max = model.max_tyre_age["SOFT"]
    assert soft_max == synthetic_laps.loc[synthetic_laps["compound"] == "SOFT", "tyre_age"].max()
    lap = pd.DataFrame({"lap": [30, 30], "compound": "SOFT", "tyre_age": [soft_max, soft_max + 20]})
    capped = model.relative_pace(lap)
    assert capped.iloc[1] == pytest.approx(capped.iloc[0])
    extrapolated = model.relative_pace(lap, cap_age=False)
    slope = model.degradation_s_per_lap["SOFT"].value
    assert extrapolated.iloc[1] - extrapolated.iloc[0] == pytest.approx(20 * slope)


def test_fixed_degradation_recovers_fuel_and_offsets(synthetic_laps: pd.DataFrame) -> None:
    fixed = {c: Estimate(v, v, v) for c, v in TRUE_DEGRADATION_S_PER_LAP.items()}
    model = fit_circuit(synthetic_laps, fixed_degradation=fixed)
    assert model.degradation_s_per_lap == fixed
    assert model.fuel_s_per_lap.value == pytest.approx(TRUE_FUEL_S_PER_LAP, abs=0.005)
    for compound, offset in TRUE_OFFSET_S.items():
        assert model.compound_offset_s[compound].value == pytest.approx(offset, abs=0.05)


def test_fixed_degradation_makes_single_stint_races_identifiable(
    synthetic_laps: pd.DataFrame,
) -> None:
    one_stint = synthetic_laps.assign(compound="MEDIUM", tyre_age=synthetic_laps["lap"] - 2)
    model = fit_circuit(one_stint, fixed_degradation={"MEDIUM": Estimate(0.07, 0.06, 0.08)})
    assert model.compounds == ["MEDIUM"]


def test_pooling_moves_noisy_circuits_most() -> None:
    models = {
        "a": make_model("a", {"SOFT": (0.10, 0.005)}),
        "b": make_model("b", {"SOFT": (0.12, 0.005)}),
        "c": make_model("c", {"SOFT": (0.08, 0.005)}),
        "noisy": make_model("noisy", {"SOFT": (0.40, 0.15)}),
    }
    pooled = pool_degradation(models)
    for precise in ("a", "b", "c"):
        assert pooled[precise]["SOFT"].value == pytest.approx(
            models[precise].degradation_s_per_lap["SOFT"].value, abs=0.005
        )
    assert pooled["noisy"]["SOFT"].value < 0.2  # pulled from 0.40 towards ~0.10
    assert (
        pooled["noisy"]["SOFT"].low < pooled["noisy"]["SOFT"].value < pooled["noisy"]["SOFT"].high
    )


def test_identical_circuits_pool_to_their_common_value() -> None:
    models = {c: make_model(c, {"HARD": (0.05, 0.01)}) for c in ("a", "b", "c")}
    assert {round(m["HARD"].value, 6) for m in pool_degradation(models).values()} == {0.05}


def test_compounds_at_too_few_circuits_are_not_pooled() -> None:
    models = {
        "a": make_model("a", {"SOFT": (0.10, 0.01), "HARD": (0.02, 0.01)}),
        "b": make_model("b", {"SOFT": (0.12, 0.01), "HARD": (0.30, 0.10)}),
        "c": make_model("c", {"SOFT": (0.08, 0.01)}),
    }
    pooled = pool_degradation(models)
    assert pooled["b"]["HARD"] == models["b"].degradation_s_per_lap["HARD"]


def test_pooled_fit_of_a_single_circuit_keeps_its_slopes(synthetic_laps: pd.DataFrame) -> None:
    raw = fit_circuits(synthetic_laps)["testring"]
    pooled = fit_circuits(synthetic_laps, pooled=True)["testring"]
    for compound, estimate in raw.degradation_s_per_lap.items():
        assert pooled.degradation_s_per_lap[compound] == estimate
    assert pooled.fuel_s_per_lap.value == pytest.approx(raw.fuel_s_per_lap.value, abs=1e-6)

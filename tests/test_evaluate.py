"""Tests for the hold-out evaluation, on synthetic laps with known parameters."""

import pandas as pd
import pytest

from f1lab.models.evaluate import FINAL_VARIANT, Variant, evaluate
from synthetic import make_synthetic_laps


def test_full_model_beats_both_baselines(synthetic_laps: pd.DataFrame) -> None:
    result = evaluate(synthetic_laps, train_seasons=(2023, 2024), test_seasons=(2025,))
    mae = result.mae()["mae_s"]
    assert mae[FINAL_VARIANT] < 0.15  # noise sd 0.15 -> MAE about 0.12
    assert mae[FINAL_VARIANT] < mae[Variant.NO_DEGRADATION] < mae[Variant.DRIVER_MEAN]
    for variant in (Variant.PER_CIRCUIT, Variant.PER_CIRCUIT_CAPPED, Variant.POOLED):
        assert mae[variant] < mae[Variant.NO_DEGRADATION]
    assert result.coverage == 1.0


def test_models_never_see_the_test_season(synthetic_laps: pd.DataFrame) -> None:
    result = evaluate(synthetic_laps, train_seasons=(2023, 2024), test_seasons=(2025,))
    assert result.models["testring"].seasons == (2023, 2024)
    assert set(result.predictions["season"]) == {2025}


def test_unknown_circuit_and_compound_are_skipped(synthetic_laps: pd.DataFrame) -> None:
    new_circuit = make_synthetic_laps(circuit_id="new", seasons=(2025,), seed=3)
    unseen = synthetic_laps[synthetic_laps["season"] == 2025].head(3).assign(compound="WET")
    laps = pd.concat([synthetic_laps, new_circuit, unseen], ignore_index=True)
    result = evaluate(laps, train_seasons=(2023, 2024), test_seasons=(2025,))
    assert result.skipped_laps == len(new_circuit) + len(unseen)
    assert set(result.predictions["circuit_id"]) == {"testring"}
    assert result.coverage == pytest.approx(
        len(result.predictions) / (len(result.predictions) + result.skipped_laps)
    )


def test_mae_by_compound(synthetic_laps: pd.DataFrame) -> None:
    by_compound = evaluate(synthetic_laps).mae(by="compound")
    assert list(by_compound.index) == ["HARD", "MEDIUM", "SOFT"]
    assert list(by_compound.columns) == [variant.value for variant in Variant]
    assert FINAL_VARIANT in by_compound.columns


def test_empty_test_set(synthetic_laps: pd.DataFrame) -> None:
    result = evaluate(synthetic_laps, train_seasons=(2023,), test_seasons=(2030,))
    assert result.predictions.empty
    assert result.coverage == 0.0

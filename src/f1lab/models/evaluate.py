"""Hold-out evaluation of the tyre model: train on past seasons, test on a later one.

Fuel, compound and degradation parameters come only from the training seasons
of the same circuit. Each driver's level in a test race is estimated from that
race (the simulator will know it too), so the errors measure how well the model
explains the change of pace *within* a race.

All variants are scored on exactly the same test laps:

* driver mean: each driver's mean lap time in the race (no fuel, no tyres);
* fuel + compound: the model without tyre-age slopes;
* degradation per circuit / pooled, each with and without the tyre-age cap.

``FINAL_VARIANT`` (pooled slopes + age cap) is the one used downstream; the
others are kept as an ablation that justifies it.
"""

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from f1lab.config import TEST_SEASONS, TRAIN_SEASONS
from f1lab.models.degradation import CircuitModel, driver_levels, fit_circuits, predict


class Variant(StrEnum):
    """Compared predictors; values are the prediction column names."""

    DRIVER_MEAN = "driver mean"
    NO_DEGRADATION = "fuel + compound"
    PER_CIRCUIT = "degradation per circuit"
    PER_CIRCUIT_CAPPED = "degradation per circuit, age cap"
    POOLED = "degradation pooled"
    POOLED_CAPPED = "degradation pooled, age cap"


VARIANTS: tuple[Variant, ...] = tuple(Variant)
FINAL_VARIANT = Variant.POOLED_CAPPED
MODEL_VARIANTS: dict[Variant, tuple[str, bool]] = {
    Variant.NO_DEGRADATION: ("no_degradation", False),
    Variant.PER_CIRCUIT: ("per_circuit", False),
    Variant.PER_CIRCUIT_CAPPED: ("per_circuit", True),
    Variant.POOLED: ("pooled", False),
    Variant.POOLED_CAPPED: ("pooled", True),
}
"""Variant -> (fitted model family, cap tyre age)."""


@dataclass(frozen=True)
class Evaluation:
    """Predictions on the test laps and the final models they came from."""

    train_seasons: tuple[int, ...]
    test_seasons: tuple[int, ...]
    models: dict[str, CircuitModel]
    predictions: pd.DataFrame
    skipped_laps: int

    def errors(self) -> pd.DataFrame:
        """Absolute error of every variant on every test lap."""
        columns = [variant.value for variant in VARIANTS]
        return self.predictions[columns].sub(self.predictions["lap_time_s"], axis=0).abs()

    def mae(self, by: str | None = None) -> pd.DataFrame:
        """Mean absolute error in seconds per variant, optionally grouped by a column."""
        errors = self.errors()
        if by is None:
            return errors.mean().to_frame("mae_s")
        return errors.groupby(self.predictions[by]).mean()

    @property
    def coverage(self) -> float:
        """Share of clean test laps the models could predict."""
        predicted = len(self.predictions)
        return predicted / (predicted + self.skipped_laps) if predicted else 0.0


def evaluate(
    clean: pd.DataFrame,
    train_seasons: tuple[int, ...] = TRAIN_SEASONS,
    test_seasons: tuple[int, ...] = TEST_SEASONS,
) -> Evaluation:
    """Fit on the training seasons and predict the clean laps of the test seasons.

    Test laps on a circuit or compound the training data does not cover are
    skipped (and counted), so all variants are scored on the same laps.

    Args:
        clean: Clean laps of all seasons (see ``f1lab.models.filters.clean_laps``).
        train_seasons: Seasons used for fitting.
        test_seasons: Seasons used for scoring.

    Returns:
        Predictions of every variant and the fitted final (pooled) models.
    """
    train = clean[clean["season"].isin(train_seasons)]
    test = clean[clean["season"].isin(test_seasons)]
    families = {
        "no_degradation": fit_circuits(train, with_degradation=False),
        "per_circuit": fit_circuits(train),
        "pooled": fit_circuits(train, pooled=True),
    }

    model_columns = [variant.value for variant in MODEL_VARIANTS]
    parts = []
    for circuit_id, laps in test.groupby("circuit_id"):
        if not all(str(circuit_id) in models for models in families.values()):
            continue
        frame = laps.copy()
        for variant, (family, cap_age) in MODEL_VARIANTS.items():
            model = families[family][str(circuit_id)]
            levels = driver_levels(model, frame, cap_age=cap_age)
            frame[variant.value] = predict(model, frame, levels, cap_age=cap_age)
        parts.append(frame)

    if parts:
        predictions = pd.concat(parts)
    else:  # nothing to predict: keep the columns so the result has a stable shape
        predictions = test.iloc[0:0].assign(**{column: 0.0 for column in model_columns})
    predictions = predictions[predictions[model_columns].notna().all(axis=1)].copy()
    predictions[Variant.DRIVER_MEAN.value] = predictions.groupby(["race_id", "driver_id"])[
        "lap_time_s"
    ].transform("mean")
    return Evaluation(
        train_seasons=tuple(train_seasons),
        test_seasons=tuple(test_seasons),
        models=families["pooled"],
        predictions=predictions,
        skipped_laps=len(test) - len(predictions),
    )

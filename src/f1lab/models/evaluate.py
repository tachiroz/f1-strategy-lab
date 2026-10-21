"""Hold-out evaluation of the tyre model: train on past seasons, test on a later one.

Fuel, compound and degradation parameters come only from the training seasons
of the same circuit. Each driver's level in a test race is estimated from that
race (the simulator will know it too), so the errors measure how well the model
explains the change of pace *within* a race.

Three variants are compared on exactly the same test laps:

* driver mean: each driver's mean lap time in the race (no fuel, no tyres);
* fuel + compound: the model without tyre-age slopes;
* full: fuel + compound + degradation.
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
    FULL = "fuel + compound + degradation"


VARIANTS: tuple[Variant, ...] = tuple(Variant)


@dataclass(frozen=True)
class Evaluation:
    """Predictions on the test laps and the models they came from."""

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
        Predictions of every variant and the fitted full models.
    """
    train = clean[clean["season"].isin(train_seasons)]
    test = clean[clean["season"].isin(test_seasons)]
    full = fit_circuits(train, with_degradation=True)
    no_degradation = fit_circuits(train, with_degradation=False)

    parts = []
    for circuit_id, laps in test.groupby("circuit_id"):
        if circuit_id not in full or circuit_id not in no_degradation:
            continue
        frame = laps.copy()
        for variant, models in ((Variant.FULL, full), (Variant.NO_DEGRADATION, no_degradation)):
            model = models[str(circuit_id)]
            frame[variant.value] = predict(model, frame, driver_levels(model, frame))
        parts.append(frame)

    model_columns = [Variant.FULL.value, Variant.NO_DEGRADATION.value]
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
        models=full,
        predictions=predictions,
        skipped_laps=len(test) - len(predictions),
    )

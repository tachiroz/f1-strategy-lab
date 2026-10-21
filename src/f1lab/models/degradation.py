"""Tyre degradation model: one OLS regression per circuit.

For the clean laps of a circuit (all seasons given):

    lap_time = level[race, driver] + fuel * lap
               + offset[compound] + degradation[compound] * tyre_age + noise

* ``level`` is a fixed effect per driver and race: car, driver and the conditions
  of the day;
* ``fuel`` is the change per lap of the race, i.e. fuel burn-off plus track
  evolution (the two cannot be told apart from lap times alone);
* ``offset`` is the pace of a compound relative to the reference compound;
* ``degradation`` is the time lost per lap of tyre age, per compound.

Fuel and degradation are separable because tyre age resets at every pit stop
while the lap number keeps increasing.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from f1lab.config import CONFIDENCE_LEVEL, MIN_COMPOUND_LAPS, REFERENCE_COMPOUND

FUEL = "fuel"
LEVEL_PREFIX = "level:"
OFFSET_PREFIX = "offset:"
DEGRADATION_PREFIX = "degradation:"


@dataclass(frozen=True)
class Estimate:
    """A coefficient with its confidence interval."""

    value: float
    low: float
    high: float


@dataclass(frozen=True)
class CircuitModel:
    """Fitted tyre and fuel parameters of one circuit."""

    circuit_id: str
    seasons: tuple[int, ...]
    n_laps: int
    reference_compound: str
    fuel_s_per_lap: Estimate
    compound_offset_s: dict[str, Estimate]
    degradation_s_per_lap: dict[str, Estimate] = field(default_factory=dict)
    compound_laps: dict[str, int] = field(default_factory=dict)
    residual_sd_s: float = float("nan")

    @property
    def compounds(self) -> list[str]:
        """Compounds the model can predict."""
        return sorted(self.compound_offset_s)

    def relative_pace(self, laps: pd.DataFrame) -> pd.Series:
        """Lap time relative to the driver's level: fuel + compound offset + degradation.

        Laps on a compound the model does not know get NaN.
        """
        offset = laps["compound"].map({c: e.value for c, e in self.compound_offset_s.items()})
        slope = laps["compound"].map({c: e.value for c, e in self.degradation_s_per_lap.items()})
        if not self.degradation_s_per_lap:
            slope = slope.fillna(0.0).where(offset.notna())
        age = laps["tyre_age"].astype(float)
        return self.fuel_s_per_lap.value * laps["lap"] + offset + slope * age


def _estimate(result: sm.regression.linear_model.RegressionResults, name: str) -> Estimate:
    """Read one coefficient and its confidence interval from a fitted OLS."""
    low, high = result.conf_int(alpha=1 - CONFIDENCE_LEVEL).loc[name]
    return Estimate(float(result.params[name]), float(low), float(high))


def design_matrix(
    laps: pd.DataFrame, compounds: list[str], reference: str, *, with_degradation: bool
) -> pd.DataFrame:
    """Build the regression design matrix with readable column names."""
    race_driver = laps["race_id"].astype(str) + ":" + laps["driver_id"].astype(str)
    columns = {
        f"{LEVEL_PREFIX}{key}": (race_driver == key).astype(float)
        for key in sorted(race_driver.unique())
    }
    columns[FUEL] = laps["lap"].astype(float)
    for compound in compounds:
        is_compound = (laps["compound"] == compound).astype(float)
        if compound != reference:
            columns[f"{OFFSET_PREFIX}{compound}"] = is_compound
        if with_degradation:
            columns[f"{DEGRADATION_PREFIX}{compound}"] = is_compound * laps["tyre_age"].astype(
                float
            )
    return pd.DataFrame(columns, index=laps.index)


def fit_circuit(laps: pd.DataFrame, *, with_degradation: bool = True) -> CircuitModel:
    """Fit the model on the clean laps of one circuit.

    Compounds with fewer than ``MIN_COMPOUND_LAPS`` laps are left out.

    Args:
        laps: Clean laps of a single circuit (``circuit_id``, ``season``,
            ``race_id``, ``driver_id``, ``lap``, ``compound``, ``tyre_age``, ``lap_time_s``).
        with_degradation: Fit per-compound tyre-age slopes; False gives the
            "no degradation" ablation used as a baseline.

    Returns:
        Fitted parameters.

    Raises:
        ValueError: If the laps cover more than one circuit or no compound has enough laps.
    """
    circuits = laps["circuit_id"].unique()
    if len(circuits) != 1:
        raise ValueError(f"Expected laps of one circuit, got {list(circuits)}")
    counts = laps["compound"].value_counts()
    compounds = sorted(counts[counts >= MIN_COMPOUND_LAPS].index)
    if not compounds:
        raise ValueError(f"{circuits[0]}: no compound has {MIN_COMPOUND_LAPS} clean laps")
    data = laps[laps["compound"].isin(compounds)]
    reference = (
        REFERENCE_COMPOUND if REFERENCE_COMPOUND in compounds else str(counts[compounds].idxmax())
    )

    design = design_matrix(data, compounds, reference, with_degradation=with_degradation)
    result = sm.OLS(data["lap_time_s"].astype(float), design).fit()

    offsets = {reference: Estimate(0.0, 0.0, 0.0)}
    offsets |= {c: _estimate(result, f"{OFFSET_PREFIX}{c}") for c in compounds if c != reference}
    degradation = (
        {c: _estimate(result, f"{DEGRADATION_PREFIX}{c}") for c in compounds}
        if with_degradation
        else {}
    )
    return CircuitModel(
        circuit_id=str(circuits[0]),
        seasons=tuple(sorted(int(s) for s in data["season"].unique())),
        n_laps=len(data),
        reference_compound=reference,
        fuel_s_per_lap=_estimate(result, FUEL),
        compound_offset_s=offsets,
        degradation_s_per_lap=degradation,
        compound_laps={c: int(counts[c]) for c in compounds},
        residual_sd_s=float(np.sqrt(result.scale)),
    )


def fit_circuits(laps: pd.DataFrame, *, with_degradation: bool = True) -> dict[str, CircuitModel]:
    """Fit one model per circuit; circuits without enough laps are skipped."""
    models = {}
    for circuit_id, circuit_laps in laps.groupby("circuit_id"):
        try:
            models[str(circuit_id)] = fit_circuit(circuit_laps, with_degradation=with_degradation)
        except ValueError:
            continue
    return models


def driver_levels(model: CircuitModel, laps: pd.DataFrame) -> pd.Series:
    """Estimate each driver's level in each race from their laps, given the model.

    The level is the mean of ``lap_time - relative_pace`` over the driver's laps
    on compounds the model knows.
    """
    residual = laps["lap_time_s"] - model.relative_pace(laps)
    return residual.groupby([laps["race_id"], laps["driver_id"]]).mean().rename("level_s")


def predict(model: CircuitModel, laps: pd.DataFrame, levels: pd.Series) -> pd.Series:
    """Predict lap times as driver level + relative pace (NaN where unknown)."""
    keys = pd.MultiIndex.from_arrays([laps["race_id"], laps["driver_id"]])
    level = pd.Series(levels.reindex(keys).to_numpy(), index=laps.index)
    return level + model.relative_pace(laps)


def parameters_table(models: Iterable[CircuitModel]) -> pd.DataFrame:
    """Flatten models into one row per circuit and compound."""
    rows = []
    for model in models:
        for compound in model.compounds:
            offset = model.compound_offset_s[compound]
            slope = model.degradation_s_per_lap.get(compound)
            rows.append(
                {
                    "circuit_id": model.circuit_id,
                    "compound": compound,
                    "laps": model.compound_laps[compound],
                    "degradation_s_per_lap": slope.value if slope else np.nan,
                    "degradation_low": slope.low if slope else np.nan,
                    "degradation_high": slope.high if slope else np.nan,
                    "offset_s": offset.value,
                    "reference_compound": model.reference_compound,
                    "fuel_s_per_lap": model.fuel_s_per_lap.value,
                    "residual_sd_s": model.residual_sd_s,
                }
            )
    return pd.DataFrame(rows)

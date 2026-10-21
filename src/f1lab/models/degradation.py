"""Tyre degradation model: one OLS regression per circuit, optionally pooled.

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

Two refinements, both checked on held-out 2025 races (see docs/models):

* **age cap**: a prediction never extrapolates wear beyond the oldest tyre the
  circuit's data contains for that compound (``CircuitModel.max_tyre_age``);
* **partial pooling**: each circuit's slope is shrunk towards the compound's
  mean over all circuits (empirical Bayes, DerSimonian-Laird), more strongly the
  noisier it is; the circuit is then refitted with the pooled slopes fixed so
  that fuel and offsets stay consistent with them.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from f1lab.config import (
    CONFIDENCE_LEVEL,
    MIN_COMPOUND_LAPS,
    MIN_POOLING_CIRCUITS,
    REFERENCE_COMPOUND,
)

FUEL = "fuel"
LEVEL_PREFIX = "level:"
OFFSET_PREFIX = "offset:"
DEGRADATION_PREFIX = "degradation:"
Z_SCORE = float(norm.ppf(0.5 + CONFIDENCE_LEVEL / 2))
"""Half-width of a confidence interval in standard errors (1.96 for 95%)."""


@dataclass(frozen=True)
class Estimate:
    """A coefficient with its confidence interval."""

    value: float
    low: float
    high: float

    @property
    def standard_error(self) -> float:
        """Standard error implied by the confidence interval."""
        return (self.high - self.low) / (2 * Z_SCORE)


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
    max_tyre_age: dict[str, int] = field(default_factory=dict)
    residual_sd_s: float = float("nan")

    @property
    def compounds(self) -> list[str]:
        """Compounds the model can predict."""
        return sorted(self.compound_offset_s)

    def relative_pace(self, laps: pd.DataFrame, *, cap_age: bool = True) -> pd.Series:
        """Lap time relative to the driver's level: fuel + compound offset + degradation.

        Args:
            laps: Laps with ``lap``, ``compound`` and ``tyre_age``.
            cap_age: Hold wear constant beyond the oldest tyre seen in the fit data
                instead of extrapolating the linear slope.

        Returns:
            Seconds per lap; NaN for compounds the model does not know.
        """
        offset = laps["compound"].map({c: e.value for c, e in self.compound_offset_s.items()})
        slope = laps["compound"].map({c: e.value for c, e in self.degradation_s_per_lap.items()})
        if not self.degradation_s_per_lap:
            slope = slope.fillna(0.0).where(offset.notna())
        age = laps["tyre_age"].astype(float)
        if cap_age and self.max_tyre_age:
            age = np.minimum(age, laps["compound"].map(self.max_tyre_age).astype(float))
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
            age = laps["tyre_age"].astype(float)
            columns[f"{DEGRADATION_PREFIX}{compound}"] = is_compound * age
    return pd.DataFrame(columns, index=laps.index)


def fit_circuit(
    laps: pd.DataFrame,
    *,
    with_degradation: bool = True,
    fixed_degradation: Mapping[str, Estimate] | None = None,
) -> CircuitModel:
    """Fit the model on the clean laps of one circuit.

    Compounds with fewer than ``MIN_COMPOUND_LAPS`` laps are left out.

    Args:
        laps: Clean laps of a single circuit (``circuit_id``, ``season``,
            ``race_id``, ``driver_id``, ``lap``, ``compound``, ``tyre_age``, ``lap_time_s``).
        with_degradation: Fit per-compound tyre-age slopes; False gives the
            "no degradation" ablation used as a baseline.
        fixed_degradation: Slopes to use instead of estimating them (pooled
            estimates); only fuel, offsets and levels are fitted then.

    Returns:
        Fitted parameters.

    Raises:
        ValueError: If the laps cover more than one circuit, no compound has enough
            laps, or the parameters are not identifiable (rank-deficient design).
    """
    circuits = laps["circuit_id"].unique()
    if len(circuits) != 1:
        raise ValueError(f"Expected laps of one circuit, got {list(circuits)}")
    counts = laps["compound"].value_counts()
    compounds = sorted(counts[counts >= MIN_COMPOUND_LAPS].index)
    if fixed_degradation is not None:
        compounds = [c for c in compounds if c in fixed_degradation]
    if not compounds:
        raise ValueError(f"{circuits[0]}: no compound has {MIN_COMPOUND_LAPS} clean laps")
    data = laps[laps["compound"].isin(compounds)]
    reference = (
        REFERENCE_COMPOUND if REFERENCE_COMPOUND in compounds else str(counts[compounds].idxmax())
    )

    target = data["lap_time_s"].astype(float)
    estimate_slopes = with_degradation and fixed_degradation is None
    if fixed_degradation is not None:
        slope = data["compound"].map({c: fixed_degradation[c].value for c in compounds})
        target = target - slope * data["tyre_age"].astype(float)
    design = design_matrix(data, compounds, reference, with_degradation=estimate_slopes)
    if np.linalg.matrix_rank(design.to_numpy()) < design.shape[1]:
        # E.g. Spa 2025: everyone ran one slick stint to the flag, so tyre age grew
        # in lockstep with the lap number and fuel cannot be told from degradation.
        raise ValueError(f"{circuits[0]}: parameters are not identifiable from these laps")
    result = sm.OLS(target, design).fit()

    offsets = {reference: Estimate(0.0, 0.0, 0.0)}
    offsets |= {c: _estimate(result, f"{OFFSET_PREFIX}{c}") for c in compounds if c != reference}
    if fixed_degradation is not None:
        degradation = {c: fixed_degradation[c] for c in compounds}
    elif with_degradation:
        degradation = {c: _estimate(result, f"{DEGRADATION_PREFIX}{c}") for c in compounds}
    else:
        degradation = {}
    return CircuitModel(
        circuit_id=str(circuits[0]),
        seasons=tuple(sorted(int(s) for s in data["season"].unique())),
        n_laps=len(data),
        reference_compound=reference,
        fuel_s_per_lap=_estimate(result, FUEL),
        compound_offset_s=offsets,
        degradation_s_per_lap=degradation,
        compound_laps={c: int(counts[c]) for c in compounds},
        max_tyre_age={c: int(age) for c, age in data.groupby("compound")["tyre_age"].max().items()},
        residual_sd_s=float(np.sqrt(result.scale)),
    )


def pool_degradation(models: Mapping[str, CircuitModel]) -> dict[str, dict[str, Estimate]]:
    """Shrink every circuit's degradation slope towards the compound's mean.

    Random-effects meta-analysis per compound (DerSimonian-Laird): with circuit
    estimates ``b_i`` and standard errors ``s_i``, the between-circuit variance
    ``tau^2`` gives the shrinkage ``k_i = tau^2 / (tau^2 + s_i^2)`` and the pooled
    slope ``mean + k_i * (b_i - mean)``. Noisy circuits move towards the mean,
    precise ones keep their own value. Compounds seen at fewer than
    ``MIN_POOLING_CIRCUITS`` circuits are left as they are.

    Args:
        models: Per-circuit models fitted with degradation.

    Returns:
        Pooled slopes per circuit and compound, with confidence intervals.
    """
    pooled = {circuit: dict(model.degradation_s_per_lap) for circuit, model in models.items()}
    compounds = sorted({c for model in models.values() for c in model.degradation_s_per_lap})
    for compound in compounds:
        circuits = [c for c, m in models.items() if compound in m.degradation_s_per_lap]
        if len(circuits) < MIN_POOLING_CIRCUITS:
            continue
        estimates = [models[c].degradation_s_per_lap[compound] for c in circuits]
        value = np.array([e.value for e in estimates])
        variance = np.array([e.standard_error for e in estimates]) ** 2

        weight = 1 / variance
        fixed_mean = (weight * value).sum() / weight.sum()
        heterogeneity = (weight * (value - fixed_mean) ** 2).sum()
        scale = weight.sum() - (weight**2).sum() / weight.sum()
        tau2 = max(0.0, (heterogeneity - (len(value) - 1)) / scale)

        random_weight = 1 / (variance + tau2)
        mean = (random_weight * value).sum() / random_weight.sum()
        shrink = tau2 / (tau2 + variance)
        posterior = mean + shrink * (value - mean)
        posterior_se = np.sqrt(shrink * variance + (1 - shrink) ** 2 / random_weight.sum())
        for circuit, centre, se in zip(circuits, posterior, posterior_se, strict=True):
            pooled[circuit][compound] = Estimate(
                float(centre), float(centre - Z_SCORE * se), float(centre + Z_SCORE * se)
            )
    return pooled


def fit_circuits(
    laps: pd.DataFrame, *, with_degradation: bool = True, pooled: bool = False
) -> dict[str, CircuitModel]:
    """Fit one model per circuit; circuits without enough laps are skipped.

    Args:
        laps: Clean laps of any number of circuits.
        with_degradation: Fit tyre-age slopes (False: the no-degradation ablation).
        pooled: Shrink the slopes across circuits (``pool_degradation``) and refit
            every circuit with its pooled slopes fixed.

    Returns:
        Models keyed by ``circuit_id``.
    """
    by_circuit = {str(circuit): group for circuit, group in laps.groupby("circuit_id")}
    models = {}
    for circuit_id, circuit_laps in by_circuit.items():
        try:
            models[circuit_id] = fit_circuit(circuit_laps, with_degradation=with_degradation)
        except ValueError:
            continue
    if not (pooled and with_degradation):
        return models
    slopes = pool_degradation(models)
    return {
        circuit_id: fit_circuit(by_circuit[circuit_id], fixed_degradation=slopes[circuit_id])
        for circuit_id in models
    }


def driver_levels(model: CircuitModel, laps: pd.DataFrame, *, cap_age: bool = True) -> pd.Series:
    """Estimate each driver's level in each race from their laps, given the model.

    The level is the mean of ``lap_time - relative_pace`` over the driver's laps
    on compounds the model knows.
    """
    residual = laps["lap_time_s"] - model.relative_pace(laps, cap_age=cap_age)
    return residual.groupby([laps["race_id"], laps["driver_id"]]).mean().rename("level_s")


def predict(
    model: CircuitModel, laps: pd.DataFrame, levels: pd.Series, *, cap_age: bool = True
) -> pd.Series:
    """Predict lap times as driver level + relative pace (NaN where unknown)."""
    keys = pd.MultiIndex.from_arrays([laps["race_id"], laps["driver_id"]])
    level = pd.Series(levels.reindex(keys).to_numpy(), index=laps.index)
    return level + model.relative_pace(laps, cap_age=cap_age)


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
                    "max_tyre_age": model.max_tyre_age.get(compound),
                    "offset_s": offset.value,
                    "reference_compound": model.reference_compound,
                    "fuel_s_per_lap": model.fuel_s_per_lap.value,
                    "residual_sd_s": model.residual_sd_s,
                }
            )
    return pd.DataFrame(rows)

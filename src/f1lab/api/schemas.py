"""Response models of the API: the JSON contract with the dashboard (``web/src/api/types.ts``).

Positions are 1-based. Probabilities are shares in [0, 1]. Intervals are 95%
confidence intervals unless a field says otherwise (``band_*`` is the 10-90%
spread of simulated positions, not a confidence interval).
"""

from pydantic import BaseModel


class Health(BaseModel):
    """Liveness check; does not touch the simulator."""

    status: str
    version: str


class Interval(BaseModel):
    """An estimate with its 95% confidence interval."""

    value: float
    low: float
    high: float


class RaceSummary(BaseModel):
    """A race in the database and whether the simulator can run it."""

    race_id: int
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str
    country: str | None
    date: str
    in_sample: bool
    """The season is part of the calibration (the simulator has seen the race)."""
    simulatable: bool
    reason: str | None
    """Why the race cannot be simulated (wet race, no tyre model)."""


class Stint(BaseModel):
    """Laps on one set of tyres."""

    compound: str
    first_lap: int
    last_lap: int


class StrategyOut(BaseModel):
    """A strategy in notation and as stints."""

    notation: str
    stints: list[Stint]
    stand_in: bool
    """The driver retired before showing a strategy; the field's most common one is used."""


class DriverEntry(BaseModel):
    """A starter of the race with the facts the dashboard shows."""

    driver_id: str
    code: str | None
    name: str
    team: str
    grid: int
    """Official grid position; 0 for a pit-lane start."""
    quali_position: int | None
    finish_position: int | None
    """Classified position; None for drivers who were not classified."""
    status: str
    strategy: StrategyOut | None


class FieldStrategy(BaseModel):
    """A strategy and how many drivers ran it."""

    notation: str
    drivers: int


class RaceDetail(RaceSummary):
    """A race with its starters and the strategies they ran."""

    race_laps: int
    drivers: list[DriverEntry]
    field_strategies: list[FieldStrategy]


class PositionStats(BaseModel):
    """Distribution of a simulated finishing position."""

    mean_position: Interval
    median_position: float
    band_low: float
    band_high: float
    finish_mean: float | None
    """Mean position over the runs in which the car finishes (None if it never does)."""
    finish_low: float | None
    finish_high: float | None
    """10-90% spread of the position over the runs in which the car finishes."""
    p_win: Interval
    p_podium: Interval
    p_points: Interval
    p_retire: float
    histogram: list[float]
    """Share of runs classified 1st, 2nd, ... last, then the share of retirements."""


class DriverOutcome(PositionStats):
    """A driver's simulated result next to the real one."""

    driver_id: str
    grid: int
    actual_position: int | None


class RaceScore(BaseModel):
    """How close the simulation came to the real result (classified finishers)."""

    finishers: int
    spearman: float | None
    grid_spearman: float | None
    mae: float
    grid_mae: float


class RaceSimulation(BaseModel):
    """Monte Carlo of a race with the strategies actually run."""

    race_id: int
    runs: int
    seed: int
    p_safety_car: float
    p_virtual_safety_car: float
    score: RaceScore | None
    drivers: list[DriverOutcome]


class StrategyOutcome(PositionStats):
    """One strategy of a driver against the same field."""

    label: str
    notation: str
    stints: list[Stint]
    is_actual: bool
    delta: Interval
    """Paired difference of the mean position to the actual strategy (negative = better)."""


class StrategyComparison(BaseModel):
    """A driver's actual strategy and the alternatives, same random numbers."""

    race_id: int
    driver_id: str
    runs: int
    strategies: list[StrategyOutcome]


class SensitivityPoint(BaseModel):
    """A strategy's result at one Safety Car frequency."""

    scale: float
    p_safety_car: float
    mean_position: Interval
    p_podium: float
    p_points: float


class SensitivitySeries(BaseModel):
    """A strategy's results across Safety Car frequencies."""

    label: str
    notation: str
    is_actual: bool
    points: list[SensitivityPoint]


class ScSensitivity(BaseModel):
    """How the strategies fare when Safety Cars are rarer or more frequent than usual."""

    race_id: int
    driver_id: str
    runs: int
    scales: list[float]
    """Multipliers of the circuit's historical SC and VSC probabilities."""
    series: list[SensitivitySeries]


class CircuitSummary(BaseModel):
    """A circuit with a tyre model."""

    circuit_id: str
    circuit_name: str
    country: str | None
    laps: int
    compounds: list[str]
    degradation_s_per_lap: dict[str, Interval]
    """Degradation slope per compound (after partial pooling across circuits)."""


class CurvePoint(BaseModel):
    """Model lap time delta at a tyre age, with the interval of the degradation slope."""

    age: int
    delta_s: float
    low: float
    high: float


class ObservedPoint(BaseModel):
    """Mean clean-lap delta at a tyre age (driver level and fuel removed)."""

    age: int
    delta_s: float
    laps: int


class TyreCompound(BaseModel):
    """Model of one compound at a circuit."""

    compound: str
    laps: int
    offset_s: Interval
    degradation_s_per_lap: Interval
    max_tyre_age: int
    curve: list[CurvePoint]
    observed: list[ObservedPoint]


class TyreModel(BaseModel):
    """Tyre and fuel model of a circuit, as the simulator uses it."""

    circuit_id: str
    circuit_name: str
    seasons: list[int]
    reference_compound: str
    fuel_s_per_lap: Interval
    residual_sd_s: float
    laps: int
    compounds: list[TyreCompound]

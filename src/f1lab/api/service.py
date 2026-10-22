"""What the API serves, computed from the database on first use and kept in memory.

The calibration (a few seconds on the calibration seasons) runs once, on the
first request that needs it. Simulation results are cached per input: the seed
is fixed, so the same request always gives the same answer.
"""

import math
import threading
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from f1lab.api.schemas import (
    CircuitSummary,
    CurvePoint,
    DriverEntry,
    DriverOutcome,
    FieldStrategy,
    Interval,
    ObservedPoint,
    RaceDetail,
    RaceScore,
    RaceSimulation,
    RaceSummary,
    ScSensitivity,
    SensitivityPoint,
    SensitivitySeries,
    Stint,
    StrategyComparison,
    StrategyOut,
    StrategyOutcome,
    TyreCompound,
    TyreModel,
)
from f1lab.config import (
    API_CACHE_SIZE,
    CALIBRATION_SEASONS,
    MAX_COMPARED_STRATEGIES,
    MIN_OBSERVED_LAPS,
    NON_STARTER_STATUSES,
    SC_SENSITIVITY_SCALES,
    SENSITIVITY_RUNS,
    SIM_RUNS,
)
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.models.degradation import CircuitModel, Estimate, driver_levels
from f1lab.models.filters import clean_laps
from f1lab.sim.backtest import actual_results, score_summary
from f1lab.sim.calibration import Calibration, calibrate, load_history
from f1lab.sim.engine import SimulationParams, simulate
from f1lab.sim.montecarlo import (
    compare_strategies,
    neutralisation_shares,
    position_histogram,
    sc_sensitivity,
    summarise,
)
from f1lab.sim.setup import ACTUAL_LABEL, STAND_IN_LABEL, RaceSetup, SetupError, race_setup
from f1lab.sim.strategy import (
    Strategy,
    StrategyError,
    parse_strategy,
    strategy_stints,
    validate_strategy,
)


class NotFoundError(LookupError):
    """A race, driver or circuit is not in the database."""


@dataclass(frozen=True)
class Calibrated:
    """Calibration and tyre models of the calibration seasons, with their clean laps."""

    calibration: Calibration
    models: dict[str, CircuitModel]
    clean_laps: pd.DataFrame


def _optional(value: float) -> float | None:
    """JSON has no NaN: missing numbers become None."""
    return None if value is None or math.isnan(value) else float(value)


def _interval(estimate: Estimate) -> Interval:
    return Interval(value=estimate.value, low=estimate.low, high=estimate.high)


def _strategy_out(strategy: Strategy, race_laps: int) -> StrategyOut:
    return StrategyOut(
        notation=strategy.notation(),
        stints=_stints(strategy, race_laps),
        stand_in=strategy.label == STAND_IN_LABEL,
    )


def _stints(strategy: Strategy, race_laps: int) -> list[Stint]:
    return [
        Stint(compound=compound, first_lap=first, last_lap=last)
        for compound, first, last in strategy_stints(strategy, race_laps)
    ]


def position_fields(stats: Mapping[str, float], histogram: np.ndarray) -> dict[str, object]:
    """Fields of ``PositionStats`` from one row of ``position_stats`` / ``summarise``."""
    return {
        "mean_position": Interval(
            value=stats["mean_position"], low=stats["mean_low"], high=stats["mean_high"]
        ),
        "median_position": stats["median_position"],
        "band_low": stats["position_low"],
        "band_high": stats["position_high"],
        "finish_mean": _optional(stats["finish_mean"]),
        "finish_low": _optional(stats["finish_low"]),
        "finish_high": _optional(stats["finish_high"]),
        **{
            f"p_{name}": Interval(
                value=stats[f"p_{name}"], low=stats[f"p_{name}_low"], high=stats[f"p_{name}_high"]
            )
            for name in ("win", "podium", "points")
        },
        "p_retire": stats["p_retire"],
        "histogram": [float(share) for share in histogram],
    }


def observed_deltas(model: CircuitModel, laps: pd.DataFrame) -> pd.DataFrame:
    """Mean clean-lap time per compound and tyre age, with driver level and fuel removed.

    The result is on the same scale as the model curve (offset + degradation x
    age); ages with fewer than ``MIN_OBSERVED_LAPS`` laps are dropped.

    Returns:
        Columns ``compound``, ``tyre_age``, ``delta_s`` and ``laps``.
    """
    known = laps[laps["compound"].isin(model.compounds)]
    levels = driver_levels(model, known)
    keys = pd.MultiIndex.from_arrays([known["race_id"], known["driver_id"]])
    level = pd.Series(levels.reindex(keys).to_numpy(), index=known.index)
    delta = known["lap_time_s"] - level - model.fuel_s_per_lap.value * known["lap"]
    grouped = (
        delta.groupby([known["compound"], known["tyre_age"]])
        .agg(["mean", "size"])
        .rename(columns={"mean": "delta_s", "size": "laps"})
        .reset_index()
    )
    return grouped[grouped["laps"] >= MIN_OBSERVED_LAPS].reset_index(drop=True)


class Lab:
    """Database, calibration and cached simulation results behind the API."""

    def __init__(
        self, db_path: Path, *, runs: int = SIM_RUNS, sensitivity_runs: int = SENSITIVITY_RUNS
    ) -> None:
        """Nothing touches the disk until the first request.

        Args:
            db_path: SQLite database written by ``python -m f1lab.ingest``.
            runs: Monte Carlo runs per race and per compared strategy.
            sensitivity_runs: Runs per point of the Safety Car sensitivity curve.
        """
        self.db_path = db_path
        self.params = SimulationParams(runs=runs)
        self.sensitivity_params = SimulationParams(runs=sensitivity_runs)
        self._lock = threading.RLock()
        self._engine: Engine | None = None
        self._calibrated: Calibrated | None = None
        self._setups: dict[int, RaceSetup | str] = {}
        self.simulation = lru_cache(maxsize=API_CACHE_SIZE)(self._simulation)
        self.compare = lru_cache(maxsize=API_CACHE_SIZE)(self._compare)
        self.sensitivity = lru_cache(maxsize=API_CACHE_SIZE)(self._sensitivity)

    @property
    def engine(self) -> Engine:
        """Engine of the database, created or upgraded on first use."""
        with self._lock:
            if self._engine is None:
                engine = create_sqlite_engine(self.db_path)
                init_db(engine)
                self._engine = engine
            return self._engine

    @property
    def calibrated(self) -> Calibrated:
        """Calibration of the simulator, computed on first use."""
        with self._lock:
            if self._calibrated is None:
                history = load_history(self.engine, CALIBRATION_SEASONS)
                calibration, models = calibrate(history)
                self._calibrated = Calibrated(calibration, models, clean_laps(history.laps))
            return self._calibrated

    def _read(self, sql: str, **params: object) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)

    def _race_row(self, race_id: int) -> pd.Series:
        races = self._read("SELECT * FROM races WHERE race_id = :race", race=race_id)
        if races.empty:
            raise NotFoundError(f"Race {race_id} is not in the database")
        return races.iloc[0]

    def _setup_or_reason(self, race_id: int) -> RaceSetup | str:
        with self._lock:
            if race_id not in self._setups:
                calibrated = self.calibrated
                try:
                    self._setups[race_id] = race_setup(
                        self.engine, race_id, calibrated.calibration, calibrated.models
                    )
                except SetupError as error:
                    self._setups[race_id] = str(error)
            return self._setups[race_id]

    def setup(self, race_id: int) -> RaceSetup:
        """Simulator input of a race.

        Raises:
            NotFoundError: If the race is not in the database.
            SetupError: If the race cannot be simulated (e.g. a wet race).
        """
        self._race_row(race_id)
        setup = self._setup_or_reason(race_id)
        if isinstance(setup, str):
            raise SetupError(setup)
        return setup

    def _summary_fields(self, row: pd.Series) -> dict[str, object]:
        setup = self._setup_or_reason(int(row["race_id"]))
        return {
            "race_id": int(row["race_id"]),
            "season": int(row["season"]),
            "round": int(row["round"]),
            "race_name": str(row["race_name"]),
            "circuit_id": str(row["circuit_id"]),
            "circuit_name": str(row["circuit_name"]),
            "country": None if pd.isna(row["country"]) else str(row["country"]),
            "date": str(row["start_time_utc"])[:10],
            "in_sample": int(row["season"]) in CALIBRATION_SEASONS,
            "simulatable": isinstance(setup, RaceSetup),
            "reason": setup if isinstance(setup, str) else None,
        }

    def races(self) -> list[RaceSummary]:
        """All races in the database, in calendar order."""
        rows = self._read("SELECT * FROM races ORDER BY race_id")
        return [RaceSummary(**self._summary_fields(row)) for _, row in rows.iterrows()]

    def race(self, race_id: int) -> RaceDetail:
        """A race with its starters, their result and their strategy."""
        row = self._race_row(race_id)
        results = self._read(
            "SELECT res.*, d.code, d.given_name, d.family_name FROM results AS res "
            "JOIN drivers AS d ON d.driver_id = res.driver_id "
            "WHERE res.race_id = :race ORDER BY res.position",
            race=race_id,
        )
        starters = results[~results["status"].isin(NON_STARTER_STATUSES)]
        quali = self._read(
            "SELECT driver_id, position FROM qualifying WHERE race_id = :race", race=race_id
        ).set_index("driver_id")["position"]
        setup = self._setup_or_reason(race_id)
        strategies = setup.strategies if isinstance(setup, RaceSetup) else {}
        race_laps = setup.race_laps if isinstance(setup, RaceSetup) else int(results["laps"].max())
        drivers = [
            DriverEntry(
                driver_id=entry.driver_id,
                code=None if pd.isna(entry.code) else str(entry.code),
                name=f"{entry.given_name} {entry.family_name}",
                team=entry.constructor_name,
                grid=int(entry.grid),
                quali_position=int(quali[entry.driver_id]) if entry.driver_id in quali else None,
                finish_position=int(entry.position) if str(entry.position_text).isdigit() else None,
                status=entry.status,
                strategy=_strategy_out(strategies[entry.driver_id], race_laps)
                if entry.driver_id in strategies
                else None,
            )
            for entry in starters.itertuples(index=False)
        ]
        counts = Counter(
            plan.notation() for plan in strategies.values() if plan.label == ACTUAL_LABEL
        )
        return RaceDetail(
            **self._summary_fields(row),
            race_laps=race_laps,
            drivers=drivers,
            field_strategies=[
                FieldStrategy(notation=notation, drivers=count)
                for notation, count in counts.most_common()
            ],
        )

    def _simulation(self, race_id: int) -> RaceSimulation:
        setup = self.setup(race_id)
        result = simulate(setup, self.params)
        summary = summarise(result)
        histograms = position_histogram(result.positions, result.retired, len(setup.drivers))
        index = {driver: i for i, driver in enumerate(setup.drivers)}
        actual = actual_results(self.engine, race_id)
        score = score_summary(setup, summary, actual)
        finishers = actual.loc[list(setup.drivers), "position_text"].astype(str).str.isdigit()
        p_safety_car, p_virtual = neutralisation_shares(result.track_state)
        drivers = [
            DriverOutcome(
                driver_id=driver,
                grid=int(actual.loc[driver, "grid"]),
                actual_position=int(actual.loc[driver, "position"]) if finishers[driver] else None,
                **position_fields(stats, histograms[index[driver]]),
            )
            for driver, stats in summary.iterrows()
        ]
        return RaceSimulation(
            race_id=race_id,
            runs=self.params.runs,
            seed=self.params.seed,
            p_safety_car=p_safety_car,
            p_virtual_safety_car=p_virtual,
            score=RaceScore(
                finishers=int(finishers.sum()),
                spearman=_optional(score.spearman),
                grid_spearman=_optional(score.grid_spearman),
                mae=score.mae,
                grid_mae=score.grid_mae,
            )
            if finishers.sum()
            else None,
            drivers=drivers,
        )

    def _driver_strategies(
        self, race_id: int, driver_id: str, alternatives: tuple[str, ...]
    ) -> tuple[RaceSetup, list[Strategy]]:
        """The race setup and the driver's actual strategy followed by the parsed alternatives.

        Raises:
            NotFoundError: If the driver did not start the race.
            StrategyError: If there are too many alternatives, or one is illegal or
                uses a compound without a tyre model at the circuit.
        """
        setup = self.setup(race_id)
        if driver_id not in setup.drivers:
            raise NotFoundError(f"{driver_id} did not start race {race_id}")
        if len(alternatives) > MAX_COMPARED_STRATEGIES - 1:
            raise StrategyError(
                f"Compare at most {MAX_COMPARED_STRATEGIES - 1} alternatives to the actual strategy"
            )
        plans = [parse_strategy(notation) for notation in alternatives]
        for plan in plans:
            validate_strategy(plan, setup.race_laps)
            unknown = sorted(set(plan.compounds) - set(setup.model.compounds))
            if unknown:
                raise StrategyError(f"No tyre model for {unknown} at {setup.circuit_id}")
        return setup, [setup.strategies[driver_id], *plans]

    def _compare(
        self, race_id: int, driver_id: str, alternatives: tuple[str, ...]
    ) -> StrategyComparison:
        setup, plans = self._driver_strategies(race_id, driver_id, alternatives)
        table = compare_strategies(setup, driver_id, plans, self.params)
        outcomes = [
            StrategyOutcome(
                label=str(row["strategy"]),
                notation=str(row["notation"]),
                stints=_stints(plan, setup.race_laps),
                is_actual=number == 0,
                delta=Interval(
                    value=row["delta_vs_first"], low=row["delta_low"], high=row["delta_high"]
                ),
                **position_fields(row, row["histogram"]),
            )
            for number, (plan, (_, row)) in enumerate(zip(plans, table.iterrows(), strict=True))
        ]
        return StrategyComparison(
            race_id=race_id, driver_id=driver_id, runs=self.params.runs, strategies=outcomes
        )

    def _sensitivity(
        self, race_id: int, driver_id: str, alternatives: tuple[str, ...]
    ) -> ScSensitivity:
        setup, plans = self._driver_strategies(race_id, driver_id, alternatives)
        table = sc_sensitivity(
            setup, driver_id, plans, SC_SENSITIVITY_SCALES, self.sensitivity_params
        )
        series = []
        for number, plan in enumerate(plans):
            rows = table.iloc[number :: len(plans)]
            series.append(
                SensitivitySeries(
                    label=plan.label or plan.notation(),
                    notation=plan.notation(),
                    is_actual=number == 0,
                    points=[
                        SensitivityPoint(
                            scale=row.scale,
                            p_safety_car=row.p_safety_car,
                            mean_position=Interval(
                                value=row.mean_position, low=row.mean_low, high=row.mean_high
                            ),
                            p_podium=row.p_podium,
                            p_points=row.p_points,
                        )
                        for row in rows.itertuples(index=False)
                    ],
                )
            )
        return ScSensitivity(
            race_id=race_id,
            driver_id=driver_id,
            runs=self.sensitivity_params.runs,
            scales=list(SC_SENSITIVITY_SCALES),
            series=series,
        )

    def _circuit_names(self) -> pd.DataFrame:
        return (
            self._read("SELECT circuit_id, circuit_name, country FROM races ORDER BY race_id")
            .drop_duplicates("circuit_id", keep="last")
            .set_index("circuit_id")
        )

    def circuits(self) -> list[CircuitSummary]:
        """Circuits with a tyre model, by name."""
        names = self._circuit_names()
        circuits = [
            CircuitSummary(
                circuit_id=circuit_id,
                circuit_name=str(names.loc[circuit_id, "circuit_name"]),
                country=None
                if pd.isna(names.loc[circuit_id, "country"])
                else str(names.loc[circuit_id, "country"]),
                laps=model.n_laps,
                compounds=model.compounds,
            )
            for circuit_id, model in self.calibrated.models.items()
        ]
        return sorted(circuits, key=lambda circuit: circuit.circuit_name)

    def tyres(self, circuit_id: str) -> TyreModel:
        """Tyre model of a circuit, its curves and the observed laps behind it."""
        calibrated = self.calibrated
        model = calibrated.models.get(circuit_id)
        if model is None:
            raise NotFoundError(f"No tyre model for circuit {circuit_id}")
        laps = calibrated.clean_laps[calibrated.clean_laps["circuit_id"] == circuit_id]
        observed = observed_deltas(model, laps)
        compounds = []
        for compound in model.compounds:
            offset = model.compound_offset_s[compound]
            slope = model.degradation_s_per_lap.get(compound, Estimate(0.0, 0.0, 0.0))
            ages = np.arange(model.max_tyre_age[compound] + 1)
            points = observed[observed["compound"] == compound]
            compounds.append(
                TyreCompound(
                    compound=compound,
                    laps=model.compound_laps[compound],
                    offset_s=_interval(offset),
                    degradation_s_per_lap=_interval(slope),
                    max_tyre_age=int(ages[-1]),
                    curve=[
                        CurvePoint(
                            age=int(age),
                            delta_s=offset.value + slope.value * age,
                            low=offset.value + slope.low * age,
                            high=offset.value + slope.high * age,
                        )
                        for age in ages
                    ],
                    observed=[
                        ObservedPoint(age=int(row.tyre_age), delta_s=row.delta_s, laps=row.laps)
                        for row in points.itertuples(index=False)
                    ],
                )
            )
        return TyreModel(
            circuit_id=circuit_id,
            circuit_name=str(self._circuit_names().loc[circuit_id, "circuit_name"]),
            seasons=list(model.seasons),
            reference_compound=model.reference_compound,
            fuel_s_per_lap=_interval(model.fuel_s_per_lap),
            residual_sd_s=model.residual_sd_s,
            laps=model.n_laps,
            compounds=compounds,
        )

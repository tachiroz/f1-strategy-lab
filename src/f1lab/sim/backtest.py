"""Backtest: simulate past races as they were set up and compare with what happened.

For every dry race the simulator gets what was known before the start
(qualifying, grid) plus the strategies the drivers actually ran, and the mean
simulated position of each classified finisher, over the runs in which that
driver finishes, is compared with the real one:
Spearman rank correlation and mean absolute error in positions. The naive
baseline "finish where you started" is scored the same way.

The same machinery calibrates the two race-craft parameters the data cannot
give directly (pace advantage needed to overtake, dirty-air loss): a grid search
on the calibration seasons only; the test season stays untouched.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from itertools import product

import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import Engine, bindparam, text

from f1lab.models.degradation import CircuitModel
from f1lab.sim.calibration import Calibration
from f1lab.sim.engine import SimulationParams, simulate
from f1lab.sim.montecarlo import summarise
from f1lab.sim.setup import RaceSetup, SetupError, race_setup


@dataclass(frozen=True)
class RaceBacktest:
    """Simulated vs actual result of one race."""

    race_id: int
    race_name: str
    table: pd.DataFrame
    spearman: float
    grid_spearman: float
    mae: float
    grid_mae: float


@dataclass(frozen=True)
class Backtest:
    """Backtest of several races."""

    races: list[RaceBacktest]
    skipped: dict[int, str]

    def summary(self) -> pd.DataFrame:
        """One row per race with simulator and grid-baseline scores."""
        return pd.DataFrame(
            [
                {
                    "race_id": race.race_id,
                    "race": race.race_name,
                    "spearman": race.spearman,
                    "grid_spearman": race.grid_spearman,
                    "mae": race.mae,
                    "grid_mae": race.grid_mae,
                }
                for race in self.races
            ]
        )

    def overall(self) -> dict[str, float]:
        """Mean scores over the races, and in how many the simulator beats the grid."""
        table = self.summary()
        if table.empty:
            return {}
        return {
            "races": float(len(table)),
            "spearman": float(table["spearman"].mean()),
            "grid_spearman": float(table["grid_spearman"].mean()),
            "mae": float(table["mae"].mean()),
            "grid_mae": float(table["grid_mae"].mean()),
            "races_better_than_grid": float((table["mae"] < table["grid_mae"]).sum()),
        }


def season_race_ids(engine: Engine, seasons: Sequence[int]) -> list[int]:
    """Race ids of the seasons, in calendar order."""
    query = text("SELECT race_id FROM races WHERE season IN :seasons ORDER BY race_id")
    with engine.connect() as conn:
        rows = conn.execute(
            query.bindparams(bindparam("seasons", expanding=True)), {"seasons": list(seasons)}
        )
        return [int(race_id) for race_id in rows.scalars()]


def actual_results(engine: Engine, race_id: int) -> pd.DataFrame:
    """Real finishing position, classification and grid of every driver of a race."""
    with engine.connect() as conn:
        return pd.read_sql(
            text(
                "SELECT driver_id, position, position_text, grid FROM results WHERE race_id = :race"
            ),
            conn,
            params={"race": race_id},
        ).set_index("driver_id")


def score_race(setup: RaceSetup, actual: pd.DataFrame, params: SimulationParams) -> RaceBacktest:
    """Simulate one race and compare the mean simulated position with reality."""
    return score_summary(setup, summarise(simulate(setup, params)), actual)


def score_summary(setup: RaceSetup, summary: pd.DataFrame, actual: pd.DataFrame) -> RaceBacktest:
    """Compare a simulated race (``summarise`` output) with its actual result.

    Only classified finishers are scored, on the simulated position conditional
    on finishing (``finish_mean``); the grid baseline uses the starting slot.
    """
    table = summary.join(actual)
    table["grid_slot"] = pd.Series(setup.grid, index=list(setup.drivers))
    finishers = table[table["position_text"].astype(str).str.isdigit()]
    return RaceBacktest(
        race_id=setup.race_id,
        race_name=setup.race_name,
        table=table,
        spearman=float(spearmanr(finishers["finish_mean"], finishers["position"]).statistic),
        grid_spearman=float(spearmanr(finishers["grid_slot"], finishers["position"]).statistic),
        mae=float((finishers["finish_mean"] - finishers["position"]).abs().mean()),
        grid_mae=float((finishers["grid_slot"] - finishers["position"]).abs().mean()),
    )


def prepare_races(
    engine: Engine,
    race_ids: Iterable[int],
    calibration: Calibration,
    models: dict[str, CircuitModel],
) -> tuple[list[tuple[RaceSetup, pd.DataFrame]], dict[int, str]]:
    """Build setups and actual results; races that cannot be simulated are skipped."""
    prepared, skipped = [], {}
    for race_id in race_ids:
        try:
            prepared.append(
                (race_setup(engine, race_id, calibration, models), actual_results(engine, race_id))
            )
        except SetupError as error:
            skipped[race_id] = str(error)
    return prepared, skipped


def backtest(
    prepared: Sequence[tuple[RaceSetup, pd.DataFrame]],
    params: SimulationParams,
    skipped: dict[int, str] | None = None,
) -> Backtest:
    """Score every prepared race with the given parameters."""
    races = [score_race(setup, actual, params) for setup, actual in prepared]
    return Backtest(races=races, skipped=dict(skipped or {}))


def search_race_craft(
    prepared: Sequence[tuple[RaceSetup, pd.DataFrame]],
    overtake_deltas: Sequence[float],
    dirty_air_penalties: Sequence[float],
    params: SimulationParams,
) -> pd.DataFrame:
    """Grid-search the race-craft parameters by mean position error.

    Returns:
        One row per combination with mean Spearman and MAE, best (lowest MAE) first.
    """
    rows = []
    for delta, penalty in product(overtake_deltas, dirty_air_penalties):
        trial = replace(params, overtake_delta_s=delta, dirty_air_penalty_s=penalty)
        scores = backtest(prepared, trial).overall()
        rows.append({"overtake_delta_s": delta, "dirty_air_penalty_s": penalty} | scores)
    return pd.DataFrame(rows).sort_values(["mae", "spearman"], ascending=[True, False])


def best_race_craft(search: pd.DataFrame) -> tuple[float, float]:
    """Return ``(overtake delta, dirty-air penalty)`` of the best search row."""
    best = search.iloc[0]
    return float(best["overtake_delta_s"]), float(best["dirty_air_penalty_s"])

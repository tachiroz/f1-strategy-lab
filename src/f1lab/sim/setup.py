"""Inputs of one simulated race, built from the database and the calibration.

A ``RaceSetup`` holds plain numbers only, so tests can build one by hand.
Drivers' pace comes from qualifying (known before the start); strategies are
the ones actually run unless the caller supplies others.
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from f1lab.config import DRY_COMPOUNDS, NON_STARTER_STATUSES, PIT_LANE_START_GRID
from f1lab.models.degradation import CircuitModel, Estimate
from f1lab.sim.calibration import Calibration
from f1lab.sim.strategy import Strategy, StrategyError, strategy_from_stints


class SetupError(ValueError):
    """A race cannot be simulated (unknown circuit, missing data, wet race)."""


@dataclass(frozen=True)
class RaceSetup:
    """Everything the engine needs to simulate one race."""

    race_id: int
    race_name: str
    circuit_id: str
    race_laps: int
    drivers: tuple[str, ...]
    grid: np.ndarray
    level_s: np.ndarray
    strategies: dict[str, Strategy]
    model: CircuitModel
    lap_noise_sd_s: float
    form_sd_s: float
    grid_slot_s: float
    pit_loss_samples_s: np.ndarray
    sc_pit_ratio: float
    vsc_pit_ratio: float
    sc_lap1_probability: float
    vsc_lap1_probability: float
    sc_hazard: float
    vsc_hazard: float
    sc_lengths_laps: np.ndarray
    vsc_lengths_laps: np.ndarray
    dnf_probability: float
    dnf_race_fraction: np.ndarray

    def with_strategy(self, driver_id: str, strategy: Strategy) -> "RaceSetup":
        """Return a copy where one driver runs another strategy."""
        if driver_id not in self.drivers:
            raise SetupError(f"{driver_id} does not start this race")
        return replace(self, strategies={**self.strategies, driver_id: strategy})


def with_fallback_compounds(model: CircuitModel, models: dict[str, CircuitModel]) -> CircuitModel:
    """Fill compounds a circuit never saw with the median parameters of all circuits.

    Used when a strategy puts a car on a compound without history at the circuit.
    """
    offsets = dict(model.compound_offset_s)
    slopes = dict(model.degradation_s_per_lap)
    max_age = dict(model.max_tyre_age)
    for compound in {c for m in models.values() for c in m.compound_offset_s} - set(offsets):
        known = [m for m in models.values() if compound in m.degradation_s_per_lap]
        offset = float(np.median([m.compound_offset_s[compound].value for m in known]))
        slope = float(np.median([m.degradation_s_per_lap[compound].value for m in known]))
        offsets[compound] = Estimate(offset, offset, offset)
        slopes[compound] = Estimate(slope, slope, slope)
        max_age[compound] = int(np.median([m.max_tyre_age[compound] for m in known]))
    return replace(
        model, compound_offset_s=offsets, degradation_s_per_lap=slopes, max_tyre_age=max_age
    )


def _read(engine: Engine, sql: str, race_id: int) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params={"race": race_id})


def race_setup(
    engine: Engine,
    race_id: int,
    calibration: Calibration,
    models: dict[str, CircuitModel],
) -> RaceSetup:
    """Build the setup of a race from the database.

    Pace: ``calibration.quali_s_per_position`` times the qualifying position
    (relative to the median). Grid: the actual starting grid, pit-lane starters
    at the back. Strategies: the ones the drivers actually ran.

    Raises:
        SetupError: If the circuit has no tyre model, a starter used wet tyres,
            or a starter's strategy cannot be rebuilt.
    """
    race = _read(engine, "SELECT * FROM races WHERE race_id = :race", race_id)
    if race.empty:
        raise SetupError(f"Race {race_id} is not in the database")
    circuit_id = str(race.loc[0, "circuit_id"])
    if circuit_id not in models:
        raise SetupError(f"No tyre model for {circuit_id}")
    results = _read(engine, "SELECT * FROM results WHERE race_id = :race", race_id)
    starters = results[~results["status"].isin(NON_STARTER_STATUSES)].copy()
    qualifying = _read(engine, "SELECT * FROM qualifying WHERE race_id = :race", race_id)
    stints = _read(engine, "SELECT * FROM stints WHERE race_id = :race", race_id)
    pit_stops = _read(engine, "SELECT * FROM pit_stops WHERE race_id = :race", race_id)

    used = set(stints.loc[stints["driver_id"].isin(starters["driver_id"]), "compound"].dropna())
    if not used <= set(DRY_COMPOUNDS):
        raise SetupError(
            f"{race.loc[0, 'race_name']}: {sorted(used - set(DRY_COMPOUNDS))} tyres used; "
            "the simulator is dry-only"
        )

    back = starters["grid"].max() + 1
    starters["start"] = starters["grid"].where(starters["grid"] != PIT_LANE_START_GRID, back)
    starters = starters.sort_values(["start", "position"]).reset_index(drop=True)
    starters["grid_slot"] = np.arange(1, len(starters) + 1)

    quali = qualifying.set_index("driver_id")["position"]
    quali_position = starters["driver_id"].map(quali).fillna(quali.max() + 1 if len(quali) else 1)
    level = calibration.quali_s_per_position * (quali_position - quali_position.median())

    strategies = {}
    for driver_id in starters["driver_id"]:
        try:
            strategies[driver_id] = strategy_from_stints(
                stints[stints["driver_id"] == driver_id],
                pit_stops[pit_stops["driver_id"] == driver_id],
                label="actual",
            )
        except StrategyError as error:
            raise SetupError(f"{driver_id}: {error}") from error

    model = with_fallback_compounds(models[circuit_id], models)
    unknown = {c for s in strategies.values() for c in s.compounds} - set(model.compounds)
    if unknown:
        raise SetupError(f"No tyre model for {sorted(unknown)} at {circuit_id}")
    sc_hazard, vsc_hazard = calibration.hazards(circuit_id)
    return RaceSetup(
        race_id=race_id,
        race_name=f"{race.loc[0, 'race_name']} {race.loc[0, 'season']}",
        circuit_id=circuit_id,
        race_laps=int(results["laps"].max()),
        drivers=tuple(starters["driver_id"]),
        grid=starters["grid_slot"].to_numpy(),
        level_s=level.to_numpy(dtype=float),
        strategies=strategies,
        model=model,
        lap_noise_sd_s=model.residual_sd_s,
        form_sd_s=calibration.form_sd_s,
        grid_slot_s=calibration.grid_slot_s,
        pit_loss_samples_s=calibration.pit_losses(circuit_id),
        sc_pit_ratio=calibration.sc_pit_ratio,
        vsc_pit_ratio=calibration.vsc_pit_ratio,
        sc_lap1_probability=calibration.sc_lap1_probability,
        vsc_lap1_probability=calibration.vsc_lap1_probability,
        sc_hazard=sc_hazard,
        vsc_hazard=vsc_hazard,
        sc_lengths_laps=calibration.sc_length_laps,
        vsc_lengths_laps=calibration.vsc_length_laps,
        dnf_probability=calibration.dnf_probability,
        dnf_race_fraction=calibration.dnf_race_fraction,
    )

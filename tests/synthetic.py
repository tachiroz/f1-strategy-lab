"""Synthetic test data with known answers.

* clean laps with known fuel, compound offset and degradation parameters, to
  check that the tyre model recovers them;
* hand-built race setups (no noise unless asked) for the simulator.
"""

import numpy as np
import pandas as pd
from sqlalchemy import Engine, insert, select

from f1lab.db import schema
from f1lab.models.degradation import CircuitModel, Estimate
from f1lab.sim.engine import SimulationParams
from f1lab.sim.setup import RaceSetup
from f1lab.sim.strategy import parse_strategy

TRUE_FUEL_S_PER_LAP = -0.06
TRUE_OFFSET_S = {"SOFT": -0.8, "MEDIUM": 0.0, "HARD": 0.5}
TRUE_DEGRADATION_S_PER_LAP = {"SOFT": 0.12, "MEDIUM": 0.07, "HARD": 0.04}
STRATEGIES = [  # (compound, first lap of the stint), race laps 2..50
    [("SOFT", 2), ("HARD", 16)],
    [("MEDIUM", 2), ("HARD", 23)],
    [("SOFT", 2), ("MEDIUM", 13), ("SOFT", 31)],
    [("HARD", 2), ("MEDIUM", 29)],
    [("MEDIUM", 2), ("SOFT", 19), ("MEDIUM", 33)],
]
LAST_LAP = 50
QUALIFYING_SOFT_AGE = 3
BASE_LAP_S = 90.0
LEVEL_SD_S = 0.6


def make_synthetic_laps(
    seasons: tuple[int, ...] = (2023, 2024, 2025),
    drivers: int = 12,
    noise_s: float = 0.15,
    circuit_id: str = "testring",
    seed: int = 7,
) -> pd.DataFrame:
    """Return clean laps of one race per season at one circuit."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in seasons:
        for number in range(drivers):
            level = BASE_LAP_S + rng.normal(0, LEVEL_SD_S)
            stints = STRATEGIES[number % len(STRATEGIES)]
            for index, (compound, first_lap) in enumerate(stints):
                last_lap = stints[index + 1][1] - 1 if index + 1 < len(stints) else LAST_LAP
                start_age = QUALIFYING_SOFT_AGE if index == 0 and compound == "SOFT" else 0
                for lap in range(first_lap, last_lap + 1):
                    age = start_age + lap - first_lap
                    lap_time = (
                        level
                        + TRUE_FUEL_S_PER_LAP * lap
                        + TRUE_OFFSET_S[compound]
                        + TRUE_DEGRADATION_S_PER_LAP[compound] * age
                        + rng.normal(0, noise_s)
                    )
                    rows.append(
                        {
                            "race_id": season * 100 + 1,
                            "season": season,
                            "round": 1,
                            "circuit_id": circuit_id,
                            "race_name": f"{circuit_id} {season}",
                            "driver_id": f"driver_{number:02d}",
                            "lap": lap,
                            "compound": compound,
                            "tyre_age": age,
                            "lap_time_s": lap_time,
                        }
                    )
    laps = pd.DataFrame(rows)
    laps["tyre_age"] = laps["tyre_age"].astype("Int64")
    return laps


FLAT = Estimate(0.0, 0.0, 0.0)
COMPOUNDS = ("SOFT", "MEDIUM", "HARD")


def flat_model() -> CircuitModel:
    """No fuel effect, no compound offsets, no degradation: pace = driver level."""
    return CircuitModel(
        circuit_id="ring",
        seasons=(2024,),
        n_laps=1,
        reference_compound="MEDIUM",
        fuel_s_per_lap=FLAT,
        compound_offset_s=dict.fromkeys(COMPOUNDS, FLAT),
        degradation_s_per_lap=dict.fromkeys(COMPOUNDS, FLAT),
        max_tyre_age=dict.fromkeys(COMPOUNDS, 100),
    )


def make_setup(levels: list[float], laps: int = 20, **overrides: object) -> RaceSetup:
    """A deterministic race: no noise, no SC/VSC, no retirements unless overridden."""
    drivers = tuple(f"car{i}" for i in range(len(levels)))
    values: dict[str, object] = {
        "race_id": 1,
        "race_name": "Test GP 2025",
        "circuit_id": "ring",
        "race_laps": laps,
        "drivers": drivers,
        "grid": np.arange(1, len(levels) + 1),
        "level_s": np.array(levels, dtype=float),
        "strategies": {driver: parse_strategy("M-10-H") for driver in drivers},
        "model": flat_model(),
        "lap_noise_sd_s": 0.0,
        "form_sd_s": 0.0,
        "grid_slot_s": 0.5,
        "pit_loss_samples_s": np.array([20.0]),
        "sc_pit_ratio": 0.5,
        "vsc_pit_ratio": 0.8,
        "sc_lap1_probability": 0.0,
        "vsc_lap1_probability": 0.0,
        "sc_hazard": 0.0,
        "vsc_hazard": 0.0,
        "sc_lengths_laps": np.array([3]),
        "vsc_lengths_laps": np.array([1]),
        "dnf_probability": 0.0,
        "dnf_race_fraction": np.array([0.5]),
    }
    values.update(overrides)
    return RaceSetup(**values)


def params(**overrides: object) -> SimulationParams:
    base = {"runs": 50, "overtake_delta_s": 0.5, "dirty_air_penalty_s": 0.0}
    return SimulationParams(**{**base, **overrides})


def complete_stints(engine: Engine, race_id: int, laps: int) -> None:
    """Give drivers trimmed out of the fixtures a one-stop on the compounds the model knows."""
    with engine.begin() as conn:
        drivers = set(
            conn.execute(
                select(schema.results.c.driver_id).where(schema.results.c.race_id == race_id)
            ).scalars()
        )
        have = set(
            conn.execute(
                select(schema.stints.c.driver_id).where(schema.stints.c.race_id == race_id)
            ).scalars()
        )
        rows = [
            row
            for driver in sorted(drivers - have)
            for row in (
                {
                    "race_id": race_id,
                    "driver_id": driver,
                    "stint": 1,
                    "compound": "SOFT",
                    "lap_start": 1,
                    "lap_end": laps // 2,
                    "tyre_age_at_start": 0,
                },
                {
                    "race_id": race_id,
                    "driver_id": driver,
                    "stint": 2,
                    "compound": "HARD",
                    "lap_start": laps // 2 + 1,
                    "lap_end": laps,
                    "tyre_age_at_start": 0,
                },
            )
        ]
        conn.execute(insert(schema.stints), rows)


def actual(
    positions: list[int], grid: list[int], classified: list[bool] | None = None
) -> pd.DataFrame:
    """Real results of cars car0..carN: finishing position, classification, grid."""
    classified = classified or [True] * len(positions)
    return pd.DataFrame(
        {
            "position": positions,
            "position_text": [
                str(p) if c else "R" for p, c in zip(positions, classified, strict=True)
            ],
            "grid": grid,
        },
        index=[f"car{i}" for i in range(len(positions))],
    )

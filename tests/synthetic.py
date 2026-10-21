"""Synthetic clean laps with known fuel, compound offset and degradation parameters.

Used to check that the tyre model recovers the parameters it was given.
"""

import numpy as np
import pandas as pd

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

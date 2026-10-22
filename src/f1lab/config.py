"""Project-wide configuration: filesystem paths and shared constants.

All tunable values live here so that the rest of the code has no magic numbers.
"""

import os
from pathlib import Path

from f1lab import __version__

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
"""Repository root (two levels above ``src/f1lab``)."""

DATA_DIR_ENV_VAR: str = "F1LAB_DATA_DIR"
"""Environment variable that overrides the default data directory."""

DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"
CACHE_DIR_NAME: str = "cache"
DB_FILE_NAME: str = "f1lab.sqlite"

# --- Database -----------------------------------------------------------------
SCHEMA_VERSION: int = 2
"""Bump together with any change to f1lab.db.schema and add a step to db.engine.MIGRATIONS."""

RACE_ID_SEASON_MULTIPLIER: int = 100
"""race_id = season * 100 + round, e.g. 202401 for round 1 of 2024."""

DATA_QUALITY_SQL: Path = PROJECT_ROOT / "sql" / "data_quality.sql"

# --- HTTP -------------------------------------------------------------------
HTTP_TIMEOUT_S: float = 30.0
HTTP_MAX_RETRIES: int = 4
HTTP_BACKOFF_S: float = 2.0
"""Base delay for exponential backoff on 429 / 5xx / connection errors."""
HTTP_RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
USER_AGENT: str = f"f1-strategy-lab/{__version__}"

# --- Jolpica-F1: schedule, results, pit stops ---------------------------------
JOLPICA_BASE_URL: str = "https://api.jolpi.ca/ergast/f1"
JOLPICA_CACHE_DIR_NAME: str = "jolpica"
JOLPICA_PAGE_LIMIT: int = 100
"""Maximum page size the API accepts."""
JOLPICA_MIN_INTERVAL_S: float = 0.5
"""Documented limits: 4 requests/s burst, 500 requests/hour sustained."""

# --- OpenF1: laps, stints, weather, race control ------------------------------
OPENF1_BASE_URL: str = "https://api.openf1.org/v1"
OPENF1_CACHE_DIR_NAME: str = "openf1"
OPENF1_MIN_INTERVAL_S: float = 2.0
"""Free tier: 3 requests/s and 30 requests/min, so at most one request every 2 s."""
OPENF1_FIRST_SEASON: int = 2023
"""OpenF1 has lap and tyre data from this season on."""
OPENF1_RACE_SESSION_NAME: str = "Race"
OPENF1_EMPTY_STATUS: int = 404
OPENF1_EMPTY_DETAIL: str = "No results found."
"""OpenF1 answers an empty filter result with 404 and this detail message."""

# --- Ingestion ----------------------------------------------------------------
SESSION_MATCH_TOLERANCE_DAYS: int = 1
"""Jolpica and OpenF1 race dates may differ by a day (e.g. Las Vegas 2024)."""
DEFAULT_SEASONS: tuple[int, ...] = (2023, 2024, 2025)

# --- Race control vocabulary (verified on 2023-2025 OpenF1 messages) -----------
RC_SC_DEPLOYED: str = "SAFETY CAR DEPLOYED"
RC_SC_ENDING: str = "SAFETY CAR IN THIS LAP"
RC_VSC_DEPLOYED: str = "VIRTUAL SAFETY CAR DEPLOYED"
RC_VSC_ENDING: str = "VIRTUAL SAFETY CAR ENDING"
RC_SESSION_STARTED: str = "SESSION STARTED"
RC_FLAG_RED: str = "RED"
RC_FLAG_CHEQUERED: str = "CHEQUERED"
RC_TRACK_SCOPE: str = "Track"
RC_GREEN_FLAGS: frozenset[str] = frozenset({"CLEAR", "GREEN"})
"""A track-wide CLEAR/GREEN after "IN THIS LAP" / "ENDING" marks the actual restart."""

# --- Tyre model (stage 3) -----------------------------------------------------
DRY_COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")
FIRST_MODEL_LAP: int = 2
"""Lap 1 starts from the grid and is not representative of race pace."""
NEUTRALISATION_RECOVERY_LAPS: int = 1
"""Laps after a SC/VSC/red flag period that are also dropped (restart, cold tyres)."""
OUTLIER_MAX_SLOWDOWN: float = 0.05
"""Drop laps more than 5% slower than the driver's median otherwise clean lap of the race."""
MIN_CLEAN_LAPS_PER_DRIVER: int = 5
"""Drivers with fewer clean laps in a race are left out (too little to estimate their pace)."""
MIN_COMPOUND_LAPS: int = 30
"""A compound needs this many clean laps at a circuit to get its own offset and slope."""
REFERENCE_COMPOUND: str = "MEDIUM"
"""Compound offsets are relative to this one (or to the most used one if it is absent)."""
MIN_POOLING_CIRCUITS: int = 3
"""Partial pooling of a compound's degradation needs estimates from at least this many circuits."""
TRAIN_SEASONS: tuple[int, ...] = (2023, 2024)
TEST_SEASONS: tuple[int, ...] = (2025,)
CONFIDENCE_LEVEL: float = 0.95
SHOWCASE_MIN_DRIVER_LAPS: int = 30
"""A race is shown in the actual-vs-model chart only if one driver has this many test laps."""
MODEL_REPORT_DIR: Path = PROJECT_ROOT / "docs" / "models"
SIM_REPORT_DIR: Path = PROJECT_ROOT / "docs" / "sim"
MODEL_LAPS_SQL: Path = PROJECT_ROOT / "sql" / "model_laps.sql"

# --- Simulator (stage 4) ------------------------------------------------------
COMPOUND_CODES: dict[str, str] = {"S": "SOFT", "M": "MEDIUM", "H": "HARD"}
"""Letters of the strategy notation, e.g. "S3-15-H-38-M"."""
MIN_DRY_COMPOUNDS: int = 2
"""Sporting rule: a dry race must use at least two different dry compounds."""
RED_FLAG_STOP_S: float = 300.0
"""A recorded 'pit stop' longer than this is a tyre change under red flag (free)."""
FINISHED_STATUSES: frozenset[str] = frozenset({"Finished", "Lapped"})
NON_STARTER_STATUSES: frozenset[str] = frozenset({"Did not start", "Withdrew"})
DISQUALIFIED_STATUS: str = "Disqualified"
"""Disqualified cars finished on track: neither a retirement nor a non-starter."""
PIT_LOSS_PERCENTILES: tuple[float, float] = (1.0, 99.0)
"""Pit losses outside these percentiles (repairs, penalties served) are dropped."""
MIN_CIRCUIT_PIT_STOPS: int = 20
"""Fewer green-flag stops at a circuit: sample pit losses from all circuits instead."""
SC_PRIOR_RACES: float = 2.0
"""Shrinkage of per-circuit SC/VSC hazards: weight of the all-circuit rate in races."""
FIRST_RACE_LAP: int = 1
CALIBRATION_SEASONS: tuple[int, ...] = (2023, 2024)
"""Seasons the simulator learns from; races of later seasons are simulated out of sample."""

SIM_RUNS: int = 5000
SIM_SEED: int = 20261021
"""Fixed seed: the same command always gives the same distribution."""
MIN_FOLLOW_GAP_S: float = 0.3
"""Closest a car can follow another at the line when it cannot pass (assumption)."""
DIRTY_AIR_GAP_S: float = 1.0
"""Within this gap behind another car a driver loses time in its wake (DRS window)."""
SC_RESTART_GAP_S: float = 0.8
"""Gap between consecutive cars after a Safety Car restart (assumption)."""
OVERTAKE_DELTA_S: float = 1.5
"""Pace advantage per lap needed to pass the car ahead (python -m f1lab.sim race-craft)."""
DIRTY_AIR_PENALTY_S: float = 1.0
"""Time lost per lap in dirty air; upper end of the plausible range (see docs/sim/race_craft.md)."""
PIT_LANE_START_GRID: int = 0
"""Jolpica grid value of a car starting from the pit lane."""
PODIUM_POSITIONS: int = 3
POINTS_POSITIONS: int = 10
"""Finishing positions that score points (2023-2025 regulations)."""
RACE_CRAFT_OVERTAKE_DELTAS_S: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0)
RACE_CRAFT_DIRTY_AIR_PENALTIES_S: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
"""Search grid, fixed before searching to physically plausible values: passing needs at
most ~2 s/lap of pace advantage and dirty air costs at most ~1 s/lap."""
RACE_CRAFT_SEARCH_RUNS: int = 500
BACKTEST_SEASONS: tuple[int, ...] = (2025,)
"""Seasons scored out of sample (never used for calibration)."""
POSITION_BAND: tuple[float, float] = (0.1, 0.9)
"""Quantiles of the simulated finishing position shown as a band (80% of runs)."""

# --- API and dashboard (stage 5) ----------------------------------------------
API_PREFIX: str = "/api"
MAX_COMPARED_STRATEGIES: int = 3
"""The actual strategy plus up to two alternatives."""
SC_SENSITIVITY_SCALES: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0, 3.0)
"""Multipliers of the circuit's SC and VSC probabilities on the sensitivity chart."""
SENSITIVITY_RUNS: int = 1000
"""Runs per point of the sensitivity chart (5 scales x up to 3 strategies per request)."""
API_CACHE_SIZE: int = 128
"""Simulation results kept in memory per kind of request (the seed is fixed)."""
MIN_OBSERVED_LAPS: int = 5
"""An observed point of the degradation chart needs at least this many clean laps."""


def get_data_dir() -> Path:
    """Return the directory for local data (FastF1 cache, SQLite database).

    The ``F1LAB_DATA_DIR`` environment variable takes precedence over the
    default ``<project root>/data``. The directory is not created.

    Returns:
        Absolute path to the data directory.
    """
    override = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(override).expanduser().resolve() if override else DEFAULT_DATA_DIR


def get_cache_dir() -> Path:
    """Return the FastF1 cache directory inside the data directory."""
    return get_data_dir() / CACHE_DIR_NAME


def get_db_path() -> Path:
    """Return the path to the SQLite database file inside the data directory."""
    return get_data_dir() / DB_FILE_NAME

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
SCHEMA_VERSION: int = 1
"""Bump together with any change to f1lab.db.schema."""

RACE_ID_SEASON_MULTIPLIER: int = 100
"""race_id = season * 100 + round, e.g. 202401 for round 1 of 2024."""

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

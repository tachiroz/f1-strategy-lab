"""Project-wide configuration: filesystem paths and shared constants.

All tunable values live here so that the rest of the code has no magic numbers.
"""

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
"""Repository root (two levels above ``src/f1lab``)."""

DATA_DIR_ENV_VAR: str = "F1LAB_DATA_DIR"
"""Environment variable that overrides the default data directory."""

DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"
CACHE_DIR_NAME: str = "cache"
DB_FILE_NAME: str = "f1lab.sqlite"


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

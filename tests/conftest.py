"""Shared pytest fixtures."""

from pathlib import Path

import pytest
from sqlalchemy import Engine

from f1lab.db.engine import create_sqlite_engine, init_db


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """Return an engine for an empty, initialised SQLite database in a temp dir."""
    db_engine = create_sqlite_engine(tmp_path / "test.sqlite")
    init_db(db_engine)
    return db_engine

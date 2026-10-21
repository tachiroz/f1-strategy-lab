"""SQLite engine creation and database initialisation."""

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, insert, inspect, select

from f1lab.config import SCHEMA_VERSION
from f1lab.db.schema import metadata, schema_meta

SCHEMA_VERSION_KEY = "schema_version"


class SchemaVersionError(RuntimeError):
    """The database was created by a different version of the schema."""


def create_sqlite_engine(db_path: Path) -> Engine:
    """Create an engine for a SQLite file with foreign keys enforced.

    The parent directory is created if it does not exist.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy engine; every new connection runs ``PRAGMA foreign_keys = ON``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: sqlite3.Connection, _record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


def read_schema_version(engine: Engine) -> int | None:
    """Return the schema version stored in the database, or None for a new database."""
    if not inspect(engine).has_table(schema_meta.name):
        return None
    with engine.connect() as conn:
        stored = conn.execute(
            select(schema_meta.c.value).where(schema_meta.c.key == SCHEMA_VERSION_KEY)
        ).scalar_one_or_none()
    return None if stored is None else int(stored)


def init_db(engine: Engine) -> None:
    """Create missing tables and record the schema version.

    Safe to call on every start: existing tables and data are left untouched.

    Args:
        engine: Engine of the target database.

    Raises:
        SchemaVersionError: If the database was created by another schema version.
    """
    stored = read_schema_version(engine)
    if stored is not None and stored != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Database schema version is {stored}, the code expects {SCHEMA_VERSION}. "
            "The database only caches public data: delete it and load again."
        )
    metadata.create_all(engine)
    if stored is None:
        with engine.begin() as conn:
            conn.execute(
                insert(schema_meta).values(key=SCHEMA_VERSION_KEY, value=str(SCHEMA_VERSION))
            )

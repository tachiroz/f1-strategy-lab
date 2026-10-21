"""SQLite engine creation, database initialisation and schema migrations."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, event, insert, inspect, select, update

from f1lab.config import SCHEMA_VERSION
from f1lab.db import schema
from f1lab.db.schema import metadata, schema_meta

SCHEMA_VERSION_KEY = "schema_version"


class SchemaVersionError(RuntimeError):
    """The database was created by a newer version of the schema than the code knows."""


def _create_qualifying(conn: Connection) -> None:
    """Version 2: add the ``qualifying`` table."""
    schema.qualifying.create(conn, checkfirst=True)


MIGRATIONS: dict[int, Callable[[Connection], None]] = {
    2: _create_qualifying,
}
"""Upgrade steps: ``MIGRATIONS[n]`` turns a version ``n - 1`` database into version ``n``."""


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
    """Create a new database or upgrade an existing one to ``SCHEMA_VERSION``.

    Safe to call on every start: existing data is kept, missing upgrade steps
    run in order inside one transaction.

    Args:
        engine: Engine of the target database.

    Raises:
        SchemaVersionError: If the database is newer than the code.
    """
    stored = read_schema_version(engine)
    if stored is None:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                insert(schema_meta).values(key=SCHEMA_VERSION_KEY, value=str(SCHEMA_VERSION))
            )
        return
    if stored > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Database schema version is {stored}, the code only knows up to {SCHEMA_VERSION}. "
            "Update the code, or delete the database (it only caches public data) and load again."
        )
    if stored == SCHEMA_VERSION:
        return
    with engine.begin() as conn:
        for version in range(stored + 1, SCHEMA_VERSION + 1):
            MIGRATIONS[version](conn)
        conn.execute(
            update(schema_meta)
            .where(schema_meta.c.key == SCHEMA_VERSION_KEY)
            .values(value=str(SCHEMA_VERSION))
        )

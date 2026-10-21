"""Tests for the database schema and initialisation."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from f1lab.config import SCHEMA_VERSION
from f1lab.db import schema
from f1lab.db.engine import (
    SchemaVersionError,
    create_sqlite_engine,
    init_db,
    read_schema_version,
)

EXPECTED_PRIMARY_KEYS = {
    "races": ["race_id"],
    "drivers": ["driver_id"],
    "results": ["race_id", "driver_id"],
    "pit_stops": ["race_id", "driver_id", "stop"],
    "laps": ["race_id", "driver_id", "lap"],
    "stints": ["race_id", "driver_id", "stint"],
    "weather": ["race_id", "time_utc"],
    "race_control": ["race_id", "seq"],
    "ingest_runs": ["race_id"],
    "schema_meta": ["key"],
}

RACE = {
    "race_id": 202401,
    "season": 2024,
    "round": 1,
    "race_name": "Bahrain Grand Prix",
    "circuit_id": "bahrain",
    "circuit_name": "Bahrain International Circuit",
    "start_time_utc": "2024-03-02T15:00:00Z",
}


def test_all_tables_created(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == set(EXPECTED_PRIMARY_KEYS)


@pytest.mark.parametrize(("table", "columns"), EXPECTED_PRIMARY_KEYS.items())
def test_primary_keys(engine: Engine, table: str, columns: list[str]) -> None:
    assert inspect(engine).get_pk_constraint(table)["constrained_columns"] == columns


def test_race_tables_reference_races(engine: Engine) -> None:
    for table in schema.RACE_TABLES:
        referred = {fk["referred_table"] for fk in inspect(engine).get_foreign_keys(table.name)}
        assert "races" in referred, table.name


def test_foreign_keys_are_enforced(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            insert(schema.ingest_runs).values(
                race_id=999901, loaded_at_utc="2024-01-01T00:00:00Z", row_counts="{}"
            )
        )


def test_season_round_is_unique(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(insert(schema.races).values(**RACE))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(insert(schema.races).values(**{**RACE, "race_id": 202499}))


def test_init_db_is_idempotent(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(insert(schema.races).values(**RACE))
    init_db(engine)
    with engine.connect() as conn:
        assert conn.execute(select(schema.races.c.race_id)).scalars().all() == [202401]
        assert len(conn.execute(select(schema.schema_meta)).all()) == 1


def test_schema_version_is_recorded(engine: Engine) -> None:
    assert read_schema_version(engine) == SCHEMA_VERSION


def test_new_database_has_no_version(tmp_path: Path) -> None:
    assert read_schema_version(create_sqlite_engine(tmp_path / "new.sqlite")) is None


def test_version_mismatch_is_rejected(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(update(schema.schema_meta).values(value=str(SCHEMA_VERSION + 1)))
    with pytest.raises(SchemaVersionError):
        init_db(engine)


def test_engine_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "db.sqlite"
    init_db(create_sqlite_engine(db_path))
    assert db_path.is_file()

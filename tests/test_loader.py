"""Tests for the idempotent race loader, on recorded real responses."""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, Row, func, insert, select
from sqlalchemy.exc import IntegrityError

from f1lab.db import schema
from f1lab.ingest.http import HttpError, JsonObject
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.loader import (
    LoadReport,
    LoadStatus,
    RaceLoader,
    SeasonNotSupportedError,
    UnknownRoundError,
    write_race,
)
from f1lab.ingest.openf1 import OpenF1Client
from f1lab.ingest.transform import build_race_rows, match_session

BAHRAIN_ID, SAO_PAULO_ID = 202401, 202421
DATA_TABLES = [
    t for t in schema.metadata.sorted_tables if t.name not in ("ingest_runs", "schema_meta")
]


def ticking_clock() -> Iterator[datetime]:
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    while True:
        yield moment
        moment += timedelta(hours=1)


@pytest.fixture
def loader(engine: Engine, jolpica: JolpicaClient, openf1: OpenF1Client) -> RaceLoader:
    clock = ticking_clock()
    return RaceLoader(engine, jolpica, openf1, clock=lambda: next(clock))


def snapshot(engine: Engine, race_id: int | None = None) -> dict[str, list[Row]]:
    """All rows of the data tables (optionally of one race), in a stable order."""
    with engine.connect() as conn:
        result = {}
        for table in DATA_TABLES:
            query = select(table)
            if race_id is not None and "race_id" in table.c:
                query = query.where(table.c.race_id == race_id)
            result[table.name] = sorted(conn.execute(query).all(), key=repr)
        return result


def count(engine: Engine, table: schema.Table, race_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            select(func.count()).select_from(table).where(table.c.race_id == race_id)
        ).scalar_one()


def test_load_race_writes_every_table(loader: RaceLoader, engine: Engine) -> None:
    report = loader.load_race(2024, 1)
    assert report.status is LoadStatus.LOADED
    for name, rows in report.row_counts.items():
        assert count(engine, schema.metadata.tables[name], BAHRAIN_ID) == rows, name
    with engine.connect() as conn:
        recorded = conn.execute(select(schema.ingest_runs.c.row_counts)).scalar_one()
    assert json.loads(recorded) == report.row_counts


def test_second_load_is_skipped(loader: RaceLoader, engine: Engine) -> None:
    loader.load_race(2024, 1)
    before = snapshot(engine)
    assert loader.load_race(2024, 1).status is LoadStatus.SKIPPED
    assert snapshot(engine) == before


def test_forced_reload_is_idempotent(loader: RaceLoader, engine: Engine) -> None:
    first = loader.load_race(2024, 1)
    before = snapshot(engine)
    second = loader.load_race(2024, 1, force=True)
    assert second.status is LoadStatus.LOADED
    assert second.row_counts == first.row_counts
    assert snapshot(engine) == before
    with engine.connect() as conn:
        loaded_at = conn.execute(select(schema.ingest_runs.c.loaded_at_utc)).scalars().all()
    assert loaded_at == ["2026-01-01T01:00:00+00:00"]


def test_reload_removes_stale_rows(loader: RaceLoader, engine: Engine) -> None:
    loader.load_race(2024, 1)
    with engine.begin() as conn:
        conn.execute(
            insert(schema.laps).values(
                race_id=BAHRAIN_ID, driver_id="max_verstappen", lap=999, is_pit_out_lap=False
            )
        )
    loader.load_race(2024, 1, force=True)
    with engine.connect() as conn:
        assert conn.execute(select(func.max(schema.laps.c.lap))).scalar_one() < 999


def test_reload_leaves_other_races_alone(loader: RaceLoader, engine: Engine) -> None:
    loader.load_season(2024, rounds=[1, 21])
    sao_paulo = snapshot(engine, SAO_PAULO_ID)
    loader.load_race(2024, 1, force=True)
    assert snapshot(engine, SAO_PAULO_ID) == sao_paulo


def test_drivers_are_shared_between_races(
    loader: RaceLoader, engine: Engine, jolpica: JolpicaClient
) -> None:
    loader.load_season(2024, rounds=[1, 21])
    expected = {r["Driver"]["driverId"] for rnd in (1, 21) for r in jolpica.results(2024, rnd)}
    with engine.connect() as conn:
        assert set(conn.execute(select(schema.drivers.c.driver_id)).scalars()) == expected


def test_failed_write_keeps_previous_data(
    loader: RaceLoader, engine: Engine, jolpica: JolpicaClient, openf1: OpenF1Client
) -> None:
    loader.load_race(2024, 1)
    before = snapshot(engine)
    race = next(r for r in jolpica.schedule(2024) if r["round"] == "1")
    session = match_session(race, openf1.race_sessions(2024))
    key = session["session_key"]
    rows = build_race_rows(
        race,
        session,
        results=jolpica.results(2024, 1),
        pit_stops=jolpica.pit_stops(2024, 1),
        laps=openf1.laps(key),
        stints=openf1.stints(key),
        weather=openf1.weather(key),
        race_control=openf1.race_control(key),
    )
    broken = replace(rows, laps=[*rows.laps, rows.laps[0]])  # duplicate primary key
    with pytest.raises(IntegrityError):
        write_race(engine, broken, datetime(2026, 2, 1, tzinfo=UTC))
    assert snapshot(engine) == before


def test_one_failed_race_does_not_stop_the_season(
    loader: RaceLoader, openf1: OpenF1Client, monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    real_laps = openf1.laps

    def flaky_laps(session_key: int) -> list[JsonObject]:
        if session_key == 9472:
            raise HttpError("GET laps -> HTTP 503")
        return real_laps(session_key)

    monkeypatch.setattr(openf1, "laps", flaky_laps)
    reports = loader.load_season(2024, rounds=[1, 21])
    assert [r.status for r in reports] == [LoadStatus.FAILED, LoadStatus.LOADED]
    assert reports[0].error is not None
    assert "503" in reports[0].error
    assert count(engine, schema.results, BAHRAIN_ID) == 0
    assert not loader.is_loaded(BAHRAIN_ID)


def test_race_without_results_is_not_available(
    loader: RaceLoader, jolpica: JolpicaClient, monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    monkeypatch.setattr(jolpica, "results", lambda season, round_number: [])
    report = loader.load_race(2024, 1)
    assert report.status is LoadStatus.NOT_AVAILABLE
    assert snapshot(engine)["races"] == []


def test_seasons_before_openf1_are_rejected(loader: RaceLoader) -> None:
    with pytest.raises(SeasonNotSupportedError):
        loader.load_season(2022)


def test_unknown_round_is_rejected(loader: RaceLoader) -> None:
    with pytest.raises(UnknownRoundError):
        loader.load_race(2024, 30)


def test_report_description() -> None:
    report = LoadReport(2024, 1, "Bahrain Grand Prix", LoadStatus.LOADED, {"laps": 113})
    assert report.describe() == "2024 R01 Bahrain Grand Prix: loaded (laps=113)"

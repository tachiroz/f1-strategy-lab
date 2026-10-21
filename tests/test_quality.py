"""Tests for the SQL data quality checks."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, insert

from f1lab.db import schema
from f1lab.db.quality import (
    EXIT_OK,
    EXIT_VIOLATIONS,
    QualityCheck,
    format_report,
    load_checks,
    main,
    parse_checks,
    run_checks,
)
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.loader import RaceLoader
from f1lab.ingest.openf1 import OpenF1Client

EXPECTED_CHECKS = [
    "race_without_openf1_session",
    "laps_without_result",
    "lap_beyond_race_distance",
    "classified_without_laps",
    "stint_inverted_range",
    "stint_overlap",
    "timed_lap_without_stint",
    "pit_stop_without_result",
]
FIXTURE_DRIVERS = {
    1: {"max_verstappen", "hulkenberg"},
    21: {"max_verstappen", "hulkenberg", "stroll", "sainz"},
}


@pytest.fixture
def loaded(engine: Engine, jolpica: JolpicaClient, openf1: OpenF1Client) -> Engine:
    """Database with the two recorded races loaded."""
    RaceLoader(engine, jolpica, openf1).load_season(2024, rounds=[1, 21])
    return engine


def test_parse_checks() -> None:
    source = (
        "-- header comment, ignored\n\n"
        "-- name: first\n-- Line one.\n-- Line two.\nSELECT 1\nWHERE 1 = 0;\n\n"
        "-- name: second\nSELECT 2;\n"
    )
    assert parse_checks(source) == [
        QualityCheck("first", "Line one. Line two.", "SELECT 1\nWHERE 1 = 0"),
        QualityCheck("second", "", "SELECT 2"),
    ]


def test_checks_file_defines_documented_checks() -> None:
    checks = load_checks()
    assert [check.name for check in checks] == EXPECTED_CHECKS
    assert all(check.description and check.sql.startswith(("SELECT", "WITH")) for check in checks)


def test_empty_database_passes(engine: Engine) -> None:
    assert run_checks(engine) == dict.fromkeys(EXPECTED_CHECKS, 0)


def test_recorded_races_pass_except_trimmed_laps(loaded: Engine, jolpica: JolpicaClient) -> None:
    # Fixture laps are trimmed to a few drivers, so the other classified drivers have none.
    expected_missing = sum(
        1
        for round_number, kept in FIXTURE_DRIVERS.items()
        for result in jolpica.results(2024, round_number)
        if result["positionText"].isdigit()
        and int(result["laps"]) > 0
        and result["Driver"]["driverId"] not in kept
    )
    violations = run_checks(loaded)
    assert violations.pop("classified_without_laps") == expected_missing
    assert set(violations.values()) == {0}


def test_inverted_stint_is_detected(loaded: Engine) -> None:
    with loaded.begin() as conn:
        conn.execute(
            insert(schema.stints).values(
                race_id=202401, driver_id="max_verstappen", stint=9, lap_start=40, lap_end=30
            )
        )
    assert run_checks(loaded)["stint_inverted_range"] == 1


def test_lap_beyond_distance_is_detected(loaded: Engine) -> None:
    with loaded.begin() as conn:
        conn.execute(
            insert(schema.laps).values(
                race_id=202401, driver_id="max_verstappen", lap=58, is_pit_out_lap=False
            )
        )
    assert run_checks(loaded)["lap_beyond_race_distance"] == 1


def test_format_report() -> None:
    assert format_report({"a": 0, "b": 0}) == "Data quality: all 2 checks passed"
    assert format_report({"a": 0, "b": 3}) == (
        "Data quality: 1 of 2 checks found issues\n  b: 3 row(s)"
    )


def test_main_exit_codes(loaded: Engine, tmp_path: Path) -> None:
    assert main(["--db", str(tmp_path / "empty.sqlite")]) == EXIT_OK
    assert main(["--db", str(loaded.url.database)]) == EXIT_VIOLATIONS

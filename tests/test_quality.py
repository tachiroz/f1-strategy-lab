"""Tests for the SQL data quality checks."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, delete, insert, select, update

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

EXPECTED_CHECKS = [
    "race_without_openf1_session",
    "laps_without_result",
    "lap_beyond_race_distance",
    "classified_without_laps",
    "incomplete_lap_coverage",
    "stint_inverted_range",
    "stint_overlap",
    "shared_stint_lap_without_pit_stop",
    "timed_lap_without_stint",
    "pit_stop_without_result",
]
FIXTURE_DRIVERS = {
    1: {"max_verstappen", "hulkenberg"},
    21: {"max_verstappen", "hulkenberg", "stroll", "sainz"},
}


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


def add_verstappen_stint(engine: Engine, lap_start: int, lap_end: int) -> None:
    """Add a 4th stint to Verstappen's Bahrain 2024 race (real stints: 1-17, 18-37, 38-57)."""
    with engine.begin() as conn:
        conn.execute(
            insert(schema.stints).values(
                race_id=202401,
                driver_id="max_verstappen",
                stint=4,
                compound="SOFT",
                lap_start=lap_start,
                lap_end=lap_end,
            )
        )


def set_verstappen_stint(engine: Engine, stint: int, **laps: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(schema.stints)
            .where(schema.stints.c.race_id == 202401)
            .where(schema.stints.c.driver_id == "max_verstappen")
            .where(schema.stints.c.stint == stint)
            .values(**laps)
        )


def test_verstappen_pitted_on_laps_17_and_37(loaded: Engine) -> None:
    with loaded.connect() as conn:
        laps = conn.execute(
            select(schema.pit_stops.c.lap)
            .where(schema.pit_stops.c.race_id == 202401)
            .where(schema.pit_stops.c.driver_id == "max_verstappen")
        ).scalars()
        assert sorted(laps) == [17, 37]


def test_inverted_stint_is_detected(loaded: Engine) -> None:
    add_verstappen_stint(loaded, lap_start=40, lap_end=30)
    assert run_checks(loaded)["stint_inverted_range"] == 1


def test_zero_lap_stint_is_valid(loaded: Engine) -> None:
    add_verstappen_stint(loaded, lap_start=58, lap_end=57)
    assert run_checks(loaded)["stint_inverted_range"] == 0


def test_shared_pit_lap_is_valid(loaded: Engine) -> None:
    set_verstappen_stint(loaded, 2, lap_start=17)  # in-lap 17 in both stints
    violations = run_checks(loaded)
    assert violations["stint_overlap"] == 0
    assert violations["shared_stint_lap_without_pit_stop"] == 0


def test_shared_lap_without_pit_stop_is_detected(loaded: Engine) -> None:
    set_verstappen_stint(loaded, 2, lap_end=38)  # no pit stop on lap 38
    violations = run_checks(loaded)
    assert violations["shared_stint_lap_without_pit_stop"] == 1
    assert violations["stint_overlap"] == 0


def test_real_overlap_is_detected(loaded: Engine) -> None:
    set_verstappen_stint(loaded, 2, lap_end=40)  # stint 3 starts on lap 38
    assert run_checks(loaded)["stint_overlap"] == 1


@pytest.mark.parametrize(("lap_time_s", "flagged"), [(95.1, 1), (None, 0)])
def test_lap_beyond_distance_counts_timed_laps_only(
    loaded: Engine, lap_time_s: float | None, flagged: int
) -> None:
    with loaded.begin() as conn:
        conn.execute(
            insert(schema.laps).values(
                race_id=202401,
                driver_id="max_verstappen",
                lap=58,
                lap_time_s=lap_time_s,
                is_pit_out_lap=False,
            )
        )
    assert run_checks(loaded)["lap_beyond_race_distance"] == flagged


def test_format_report() -> None:
    assert format_report({"a": 0, "b": 0}) == "Data quality: all 2 checks passed"
    assert format_report({"a": 0, "b": 3}) == (
        "Data quality: 1 of 2 checks found issues\n  b: 3 row(s)"
    )


def test_main_exit_codes(loaded: Engine, tmp_path: Path) -> None:
    assert main(["--db", str(tmp_path / "empty.sqlite")]) == EXIT_OK
    assert main(["--db", str(loaded.url.database)]) == EXIT_VIOLATIONS


def test_partial_lap_coverage_is_detected(loaded: Engine) -> None:
    # Like Miami 2025 in OpenF1: a classified driver with a block of laps missing.
    with loaded.begin() as conn:
        conn.execute(
            delete(schema.laps)
            .where(schema.laps.c.race_id == 202401)
            .where(schema.laps.c.driver_id == "max_verstappen")
            .where(schema.laps.c.lap.between(2, 24))
        )
    # Only Verstappen: the 18 drivers with no laps at all belong to classified_without_laps.
    assert run_checks(loaded)["incomplete_lap_coverage"] == 1

"""Tests for API payload -> row transformations, on recorded real responses."""

import pytest

from f1lab.ingest.http import JsonObject
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.openf1 import OpenF1Client
from f1lab.ingest.transform import (
    RaceRows,
    TransformError,
    build_race_rows,
    car_number_map,
    match_session,
    parse_duration_s,
    pit_stop_row,
    race_id_for,
    race_row,
    race_start_utc,
)

BAHRAIN, SAO_PAULO = 9472, 9636


def by_round(jolpica: JolpicaClient, round_number: int) -> JsonObject:
    return next(r for r in jolpica.schedule(2024) if int(r["round"]) == round_number)


def build(jolpica: JolpicaClient, openf1: OpenF1Client, round_number: int) -> RaceRows:
    race = by_round(jolpica, round_number)
    session = match_session(race, openf1.race_sessions(2024))
    key = session["session_key"]
    return build_race_rows(
        race,
        session,
        results=jolpica.results(2024, round_number),
        pit_stops=jolpica.pit_stops(2024, round_number),
        laps=openf1.laps(key),
        stints=openf1.stints(key),
        weather=openf1.weather(key),
        race_control=openf1.race_control(key),
    )


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("25.208", 25.208),
        ("1:14.773", 74.773),
        ("23:44.659", 1424.659),  # red flag at São Paulo 2024
        ("1:31:44.742", 5504.742),
        (" 36.604 ", 36.604),
    ],
)
def test_parse_duration(text: str, seconds: float) -> None:
    assert parse_duration_s(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "1::2", "1:2:3:4", ":30"])
def test_parse_duration_rejects_garbage(text: str) -> None:
    with pytest.raises(TransformError):
        parse_duration_s(text)


def test_race_id_is_season_and_round() -> None:
    assert race_id_for(2024, 1) == 202401
    assert race_id_for(2025, 24) == 202524


def test_race_start_requires_time() -> None:
    with pytest.raises(TransformError, match="no start time"):
        race_start_utc({"season": "1950", "round": "1", "date": "1950-05-13"})


def test_every_2024_race_matches_exactly_one_session(
    jolpica: JolpicaClient, openf1: OpenF1Client
) -> None:
    sessions = openf1.race_sessions(2024)
    keys = [match_session(race, sessions)["session_key"] for race in jolpica.schedule(2024)]
    assert len(set(keys)) == 24


def test_las_vegas_matches_despite_one_day_difference(
    jolpica: JolpicaClient, openf1: OpenF1Client
) -> None:
    vegas = next(r for r in jolpica.schedule(2024) if r["Circuit"]["circuitId"] == "vegas")
    session = match_session(vegas, openf1.race_sessions(2024))
    assert session["location"] == "Las Vegas"
    assert session["date_start"].startswith("2024-11-24")


def test_cancelled_sessions_are_ignored() -> None:
    race = {"season": "2023", "round": "6", "raceName": "Monaco", "date": "2023-05-28"}
    cancelled_imola = {
        "session_key": 1,
        "date_start": "2023-05-21T13:00:00+00:00",
        "is_cancelled": True,
    }
    monaco = {"session_key": 2, "date_start": "2023-05-28T13:00:00+00:00", "is_cancelled": False}
    assert match_session(race, [cancelled_imola, monaco])["session_key"] == 2
    with pytest.raises(TransformError, match="found 0"):
        match_session({**race, "date": "2023-05-21"}, [cancelled_imola, monaco])


def test_ambiguous_match_is_an_error() -> None:
    race = {"season": "2024", "round": "1", "raceName": "X", "date": "2024-03-02"}
    sessions = [
        {"session_key": 1, "date_start": "2024-03-01T15:00:00+00:00"},
        {"session_key": 2, "date_start": "2024-03-02T15:00:00+00:00"},
    ]
    with pytest.raises(TransformError, match="found 2"):
        match_session(race, sessions)


def test_race_row(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    race = by_round(jolpica, 1)
    row = race_row(race, match_session(race, openf1.race_sessions(2024)))
    assert row["race_id"] == 202401
    assert row["start_time_utc"] == "2024-03-02T15:00:00Z"
    assert row["openf1_session_key"] == BAHRAIN
    assert row["circuit_id"] == "bahrain"


def test_car_numbers_come_from_the_race_not_permanent_numbers(jolpica: JolpicaClient) -> None:
    results = jolpica.results(2024, 1)
    verstappen = next(r for r in results if r["Driver"]["driverId"] == "max_verstappen")
    assert verstappen["number"] != verstappen["Driver"]["permanentNumber"]
    assert car_number_map(results)[1] == "max_verstappen"


def test_duplicate_car_numbers_are_rejected(jolpica: JolpicaClient) -> None:
    results = jolpica.results(2024, 1)
    with pytest.raises(TransformError, match="Duplicate"):
        car_number_map([results[0], results[0]])


def test_bahrain_row_counts(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    rows = build(jolpica, openf1, 1)
    counts = rows.row_counts()
    assert counts["results"] == 20
    assert counts["pit_stops"] == 43
    # Fixtures keep Verstappen and Hülkenberg (lapped): OpenF1 laps match Jolpica laps.
    kept = {"max_verstappen", "hulkenberg"}
    assert counts["laps"] == sum(int(r["laps"]) for r in rows.results if r["driver_id"] in kept)
    assert counts["weather"] == 157
    assert counts["race_control"] == 71
    assert len(rows.drivers) == 20


def test_results_of_dns_and_dsq(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    results = {r["driver_id"]: r for r in build(jolpica, openf1, 21).results}
    stroll, hulkenberg = results["stroll"], results["hulkenberg"]
    assert (stroll["position_text"], stroll["race_time_ms"], stroll["fastest_lap"]) == (
        "W",
        None,
        None,
    )
    assert (hulkenberg["position_text"], hulkenberg["laps"]) == ("D", 0)
    assert results["max_verstappen"]["race_time_ms"] is not None


def test_red_flag_pit_stops_are_kept(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    durations = [row["duration_s"] for row in build(jolpica, openf1, 21).pit_stops]
    assert max(durations) > 20 * 60


def test_pit_stop_without_duration_is_kept(jolpica: JolpicaClient) -> None:
    # Real Jolpica data, British GP 2024: Tsunoda's stop has an empty duration.
    rows = [pit_stop_row(202412, stop) for stop in jolpica.pit_stops(2024, 12)]
    missing = [row for row in rows if row["duration_s"] is None]
    assert [(r["driver_id"], r["lap"], r["stop"]) for r in missing] == [("tsunoda", 27, 1)]
    assert all(isinstance(r["duration_s"], float) for r in rows if r not in missing)


def test_laps_keep_missing_timing_as_none(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    laps = {(r["driver_id"], r["lap"]): r for r in build(jolpica, openf1, 21).laps}
    sainz_lap_1 = laps[("sainz", 1)]
    assert sainz_lap_1["lap_time_s"] is None
    assert sainz_lap_1["start_time_utc"] is None
    assert isinstance(laps[("max_verstappen", 10)]["lap_time_s"], float)


def test_stints_of_driver_who_did_not_start(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    stints = [r for r in build(jolpica, openf1, 21).stints if r["driver_id"] == "stroll"]
    assert [(s["compound"], s["lap_start"], s["lap_end"]) for s in stints] == [
        ("INTERMEDIATE", None, None)
    ]


def test_weather_rainfall_is_boolean(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    assert {r["rainfall"] for r in build(jolpica, openf1, 1).weather} == {False}
    assert {r["rainfall"] for r in build(jolpica, openf1, 21).weather} == {False, True}


def test_race_control_is_numbered_and_mapped(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    messages = build(jolpica, openf1, 1).race_control
    assert [m["seq"] for m in messages] == list(range(1, len(messages) + 1))
    with_driver = [m for m in messages if m["driver_id"] is not None]
    assert with_driver
    assert all(isinstance(m["driver_id"], str) for m in with_driver)


def test_unknown_car_number_in_laps_is_an_error(
    jolpica: JolpicaClient, openf1: OpenF1Client
) -> None:
    race = by_round(jolpica, 1)
    session = match_session(race, openf1.race_sessions(2024))
    lap = {**openf1.laps(BAHRAIN)[0], "driver_number": 99}
    with pytest.raises(TransformError, match="car number 99"):
        build_race_rows(
            race,
            session,
            results=jolpica.results(2024, 1),
            pit_stops=[],
            laps=[lap],
            stints=[],
            weather=[],
            race_control=[],
        )


def test_race_without_results_is_an_error(jolpica: JolpicaClient, openf1: OpenF1Client) -> None:
    race = by_round(jolpica, 1)
    session = match_session(race, openf1.race_sessions(2024))
    with pytest.raises(TransformError, match="no results"):
        build_race_rows(
            race, session, results=[], pit_stops=[], laps=[], stints=[], weather=[], race_control=[]
        )

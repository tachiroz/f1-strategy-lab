"""Tests for the Jolpica and OpenF1 wrappers, on recorded real responses."""

import json
from typing import cast

import pytest
import requests

from f1lab.ingest.http import JsonValue, QueryParams
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.openf1 import OpenF1Client, is_openf1_empty

BAHRAIN = 9472
SAO_PAULO = 9636


class PagedPitStops:
    """In-memory Jolpica endpoint serving 5 pit stops in pages of ``limit``."""

    def __init__(self) -> None:
        self.requested_offsets: list[int] = []

    def get_json(self, path: str, params: QueryParams | None = None) -> JsonValue:
        assert params is not None
        limit, offset = int(params["limit"]), int(params["offset"])
        self.requested_offsets.append(offset)
        stops = [{"driverId": "x", "stop": str(n)} for n in range(1, 6)][offset : offset + limit]
        return {"MRData": {"total": "5", "RaceTable": {"Races": [{"PitStops": stops}]}}}


class FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> object:
        return json.loads(self.text)


def test_schedule_lists_all_2024_races(jolpica: JolpicaClient) -> None:
    races = jolpica.schedule(2024)
    assert len(races) == 24
    assert races[0]["raceName"] == "Bahrain Grand Prix"


def test_schedule_keeps_jolpica_las_vegas_date(jolpica: JolpicaClient) -> None:
    vegas = next(r for r in jolpica.schedule(2024) if r["Circuit"]["circuitId"] == "vegas")
    # OpenF1 dates the same race 2024-11-24 06:00 UTC; the matcher tolerates one day.
    assert (vegas["date"], vegas["time"]) == ("2024-11-23", "06:00:00Z")


def test_results_include_all_classified_and_dns(jolpica: JolpicaClient) -> None:
    results = jolpica.results(2024, 21)
    assert len(results) == 20
    statuses = {r["Driver"]["code"]: r["status"] for r in results}
    assert statuses["VER"] == "Finished"
    assert statuses["STR"] == "Did not start"
    assert statuses["HUL"] == "Disqualified"


def test_pit_stops_include_red_flag_entries(jolpica: JolpicaClient) -> None:
    assert len(jolpica.pit_stops(2024, 1)) == 43
    durations = [p["duration"] for p in jolpica.pit_stops(2024, 21)]
    assert any(d.count(":") == 1 and int(d.split(":")[0]) > 20 for d in durations)


def test_pagination_collects_all_pages() -> None:
    fetcher = PagedPitStops()
    stops = JolpicaClient(fetcher, page_limit=2).pit_stops(2024, 1)
    assert [s["stop"] for s in stops] == ["1", "2", "3", "4", "5"]
    assert fetcher.requested_offsets == [0, 2, 4]


def test_race_sessions_2024(openf1: OpenF1Client) -> None:
    sessions = openf1.race_sessions(2024)
    assert len(sessions) == 24
    assert {s["session_name"] for s in sessions} == {"Race"}
    assert BAHRAIN in {s["session_key"] for s in sessions}


def test_stints_have_compounds_and_lap_ranges(openf1: OpenF1Client) -> None:
    verstappen = sorted(
        (s for s in openf1.stints(BAHRAIN) if s["driver_number"] == 1),
        key=lambda s: s["stint_number"],
    )
    assert [(s["compound"], s["lap_start"], s["lap_end"]) for s in verstappen] == [
        ("SOFT", 1, 17),
        ("HARD", 18, 37),
        ("SOFT", 38, 57),
    ]


def test_laps_weather_and_race_control_are_lists(openf1: OpenF1Client) -> None:
    assert {lap["driver_number"] for lap in openf1.laps(BAHRAIN)} == {1, 27}
    assert len(openf1.weather(SAO_PAULO)) > 0
    categories = {m["category"] for m in openf1.race_control(SAO_PAULO)}
    assert "SafetyCar" in categories


@pytest.mark.parametrize(
    ("status", "text", "expected"),
    [
        (404, '{"detail": "No results found."}', True),
        (404, '{"detail": "Not Found"}', False),
        (404, "<html>not json</html>", False),
        (200, "[]", False),
    ],
)
def test_is_openf1_empty(status: int, text: str, expected: bool) -> None:
    response = cast(requests.Response, FakeResponse(status, text))
    assert is_openf1_empty(response) is expected


def test_openf1_rejects_non_list_payload() -> None:
    class DictFetcher:
        def get_json(self, path: str, params: QueryParams | None = None) -> JsonValue:
            return {"detail": "unexpected"}

    with pytest.raises(TypeError, match="expected a list"):
        OpenF1Client(DictFetcher()).laps(1)

"""Opt-in smoke tests against the real APIs: ``pytest -m network``.

Recorded fixtures cannot reveal API drift (renamed fields, changed formats), so
these tests check that the fields used by ``f1lab.ingest.transform`` still exist.
"""

from pathlib import Path

import pytest

from f1lab.ingest.jolpica import create_jolpica_client
from f1lab.ingest.openf1 import create_openf1_client

pytestmark = pytest.mark.network

SEASON, ROUND, SESSION_KEY = 2024, 1, 9472


def test_jolpica_fields(tmp_path: Path) -> None:
    client = create_jolpica_client(tmp_path)
    race = client.schedule(SEASON)[0]
    assert {"season", "round", "raceName", "Circuit", "date", "time"} <= race.keys()
    result = client.results(SEASON, ROUND)[0]
    assert {"number", "position", "positionText", "points", "grid", "laps", "status"} <= (
        result.keys()
    )
    assert {"driverId", "givenName", "familyName"} <= result["Driver"].keys()
    stop = client.pit_stops(SEASON, ROUND)[0]
    assert {"driverId", "stop", "lap", "time", "duration"} <= stop.keys()


def test_openf1_fields(tmp_path: Path) -> None:
    client = create_openf1_client(tmp_path)
    session = next(s for s in client.race_sessions(SEASON) if s["session_key"] == SESSION_KEY)
    assert {"date_start", "meeting_key"} <= session.keys()
    lap_fields = {"driver_number", "lap_number", "lap_duration", "date_start", "is_pit_out_lap"}
    assert lap_fields <= client.laps(SESSION_KEY)[0].keys()
    stint_fields = {"driver_number", "stint_number", "compound", "lap_start", "lap_end"}
    assert stint_fields <= client.stints(SESSION_KEY)[0].keys()
    assert {"date", "air_temperature", "track_temperature", "rainfall"} <= (
        client.weather(SESSION_KEY)[0].keys()
    )
    assert {"date", "category", "flag", "message"} <= client.race_control(SESSION_KEY)[0].keys()

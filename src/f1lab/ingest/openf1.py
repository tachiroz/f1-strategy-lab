"""OpenF1 API: race sessions, laps, tyre stints, weather and race control messages."""

from pathlib import Path

import requests

from f1lab.config import (
    OPENF1_BASE_URL,
    OPENF1_CACHE_DIR_NAME,
    OPENF1_EMPTY_DETAIL,
    OPENF1_EMPTY_STATUS,
    OPENF1_MIN_INTERVAL_S,
    OPENF1_RACE_SESSION_NAME,
)
from f1lab.ingest.http import CachedHttpClient, JsonFetcher, JsonObject


def is_openf1_empty(response: requests.Response) -> bool:
    """Return True for OpenF1's "no results" answer (HTTP 404 with a detail message)."""
    if response.status_code != OPENF1_EMPTY_STATUS:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("detail") == OPENF1_EMPTY_DETAIL


class OpenF1Client:
    """Typed access to the OpenF1 endpoints the loader needs."""

    def __init__(self, fetcher: JsonFetcher) -> None:
        """Wrap a JSON fetcher (cached HTTP client or test fixtures)."""
        self._fetcher = fetcher

    def race_sessions(self, year: int) -> list[JsonObject]:
        """Return all Grand Prix race sessions of a year, cancelled ones included."""
        return self._list("sessions", year=year, session_name=OPENF1_RACE_SESSION_NAME)

    def laps(self, session_key: int) -> list[JsonObject]:
        """Return every lap of every driver in a session."""
        return self._list("laps", session_key=session_key)

    def stints(self, session_key: int) -> list[JsonObject]:
        """Return tyre stints (compound, lap range, tyre age) of a session."""
        return self._list("stints", session_key=session_key)

    def weather(self, session_key: int) -> list[JsonObject]:
        """Return per-minute weather samples of a session."""
        return self._list("weather", session_key=session_key)

    def race_control(self, session_key: int) -> list[JsonObject]:
        """Return race control messages (flags, Safety Car, penalties) of a session."""
        return self._list("race_control", session_key=session_key)

    def _list(self, path: str, **params: str | int) -> list[JsonObject]:
        """Fetch an endpoint that returns a JSON array."""
        body = self._fetcher.get_json(path, params)
        if not isinstance(body, list):
            raise TypeError(f"OpenF1 /{path} returned {type(body).__name__}, expected a list")
        return body


def create_openf1_client(cache_root: Path) -> OpenF1Client:
    """Create an OpenF1 client backed by the HTTP cache under ``cache_root``."""
    http = CachedHttpClient(
        OPENF1_BASE_URL,
        cache_root / OPENF1_CACHE_DIR_NAME,
        OPENF1_MIN_INTERVAL_S,
        is_empty=is_openf1_empty,
    )
    return OpenF1Client(http)

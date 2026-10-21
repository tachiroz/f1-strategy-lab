"""Tests for the cached, rate-limited HTTP client (no network)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import requests

from f1lab.ingest.http import CachedHttpClient, HttpError, cache_file_name

BASE_URL = "https://api.example.test/v1"


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(
        self, status_code: int, body: object, headers: dict[str, str] | None = None
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.url = BASE_URL
        self.text = json.dumps(body)

    def json(self) -> object:
        return self._body


class FakeSession:
    """Returns queued responses (or raises queued exceptions) and records calls."""

    def __init__(self, *outcomes: FakeResponse | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClock:
    """Manual monotonic clock; sleeping advances it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(
    tmp_path: Path,
    session: FakeSession,
    clock: FakeClock,
    is_empty: Callable[[requests.Response], bool] | None = None,
    min_interval_s: float = 0.0,
) -> CachedHttpClient:
    return CachedHttpClient(
        BASE_URL,
        tmp_path / "cache",
        min_interval_s,
        session=cast(requests.Session, session),
        is_empty=is_empty,
        max_retries=2,
        backoff_s=1.0,
        sleep=clock.sleep,
        clock=clock,
    )


@pytest.mark.parametrize(
    ("path", "params", "expected"),
    [
        (
            "2024/1/results.json",
            {"offset": 0, "limit": 100},
            "2024_1_results__limit=100_offset=0.json",
        ),
        ("laps", {"session_key": 9472}, "laps__session_key=9472.json"),
        ("/2024.json", None, "2024.json"),
        (
            "sessions",
            {"session_name": "Race", "year": 2024},
            "sessions__session_name=Race_year=2024.json",
        ),
    ],
)
def test_cache_file_name(path: str, params: dict[str, int] | None, expected: str) -> None:
    assert cache_file_name(path, params) == expected


def test_second_call_is_served_from_cache(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(200, [{"lap": 1}]))
    client = make_client(tmp_path, session, FakeClock())
    assert client.get_json("laps", {"session_key": 1}) == [{"lap": 1}]
    assert client.get_json("laps", {"session_key": 1}) == [{"lap": 1}]
    assert len(session.calls) == 1
    assert client.network_requests == 1
    assert (tmp_path / "cache" / "laps__session_key=1.json").is_file()


def test_cache_survives_a_new_client(tmp_path: Path) -> None:
    make_client(tmp_path, FakeSession(FakeResponse(200, {"a": 1})), FakeClock()).get_json("x")
    offline = FakeSession()
    assert make_client(tmp_path, offline, FakeClock()).get_json("x") == {"a": 1}
    assert offline.calls == []


def test_sends_user_agent_and_params(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(200, []))
    make_client(tmp_path, session, FakeClock()).get_json("/laps", {"session_key": 7})
    call = session.calls[0]
    assert call["url"] == f"{BASE_URL}/laps"
    assert call["params"] == {"session_key": 7}
    assert str(cast(dict[str, str], call["headers"])["User-Agent"]).startswith("f1-strategy-lab/")


def test_requests_are_spaced_by_min_interval(tmp_path: Path) -> None:
    clock = FakeClock()
    session = FakeSession(FakeResponse(200, 1), FakeResponse(200, 2))
    client = make_client(tmp_path, session, clock, min_interval_s=2.0)
    client.get_json("a")
    client.get_json("b")
    assert clock.sleeps == [2.0]


def test_retry_after_header_is_honoured(tmp_path: Path) -> None:
    clock = FakeClock()
    session = FakeSession(FakeResponse(429, {}, {"Retry-After": "7"}), FakeResponse(200, "ok"))
    assert make_client(tmp_path, session, clock).get_json("a") == "ok"
    assert clock.sleeps == [7.0]


def test_server_errors_back_off_exponentially_then_fail(tmp_path: Path) -> None:
    clock = FakeClock()
    session = FakeSession(*(FakeResponse(503, {}) for _ in range(3)))
    with pytest.raises(HttpError, match="503"):
        make_client(tmp_path, session, clock).get_json("a")
    assert clock.sleeps == [1.0, 2.0]
    assert not (tmp_path / "cache" / "a.json").exists()


def test_connection_errors_are_retried(tmp_path: Path) -> None:
    session = FakeSession(requests.ConnectionError("reset"), FakeResponse(200, [1]))
    assert make_client(tmp_path, session, FakeClock()).get_json("a") == [1]


def test_connection_errors_give_up_after_max_retries(tmp_path: Path) -> None:
    session = FakeSession(*(requests.Timeout("slow") for _ in range(3)))
    with pytest.raises(HttpError, match="slow"):
        make_client(tmp_path, session, FakeClock()).get_json("a")


def test_client_errors_are_not_retried(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(400, {"detail": "bad filter"}))
    with pytest.raises(HttpError, match="400"):
        make_client(tmp_path, session, FakeClock()).get_json("a")
    assert len(session.calls) == 1


def test_empty_responses_become_cached_empty_lists(tmp_path: Path) -> None:
    session = FakeSession(FakeResponse(404, {"detail": "No results found."}))
    client = make_client(tmp_path, session, FakeClock(), is_empty=lambda r: r.status_code == 404)
    assert client.get_json("race_control", {"session_key": 1}) == []
    assert client.get_json("race_control", {"session_key": 1}) == []
    assert len(session.calls) == 1

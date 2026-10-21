"""Cached, rate-limited JSON-over-HTTP client shared by the API wrappers."""

import json
import re
import time
from collections.abc import Callable, Mapping
from http import HTTPStatus
from pathlib import Path
from typing import Protocol

import requests

from f1lab.config import (
    HTTP_BACKOFF_S,
    HTTP_MAX_RETRIES,
    HTTP_RETRY_STATUSES,
    HTTP_TIMEOUT_S,
    USER_AGENT,
)

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None
type JsonObject = dict[str, JsonValue]
type QueryParams = Mapping[str, str | int]

_UNSAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9._=-]+")


class JsonFetcher(Protocol):
    """Anything that returns parsed JSON for an API path and query parameters."""

    def get_json(self, path: str, params: QueryParams | None = None) -> JsonValue:
        """Return the parsed JSON body of ``GET path?params``."""
        ...


class HttpError(RuntimeError):
    """The API could not be reached or answered with an unexpected status."""


def cache_file_name(path: str, params: QueryParams | None = None) -> str:
    """Build a readable, filesystem-safe cache file name for a request.

    Args:
        path: API path relative to the base URL, e.g. ``"2024/1/results.json"``.
        params: Query parameters; their order does not matter.

    Returns:
        File name such as ``"2024_1_results__limit=100_offset=0.json"``.
    """
    stem = path.strip("/").removesuffix(".json").replace("/", "_")
    if params:
        query = "&".join(f"{key}={params[key]}" for key in sorted(params))
        stem = f"{stem}__{query}"
    return f"{_UNSAFE_FILE_CHARS.sub('_', stem)}.json"


class CachedHttpClient:
    """GET JSON from an API with a disk cache, request spacing and retries.

    Historical race data does not change, so cached responses never expire:
    delete the cache directory to download them again.
    """

    def __init__(
        self,
        base_url: str,
        cache_dir: Path,
        min_interval_s: float,
        *,
        session: requests.Session | None = None,
        is_empty: Callable[[requests.Response], bool] | None = None,
        timeout_s: float = HTTP_TIMEOUT_S,
        max_retries: int = HTTP_MAX_RETRIES,
        backoff_s: float = HTTP_BACKOFF_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configure the client.

        Args:
            base_url: API root, e.g. ``"https://api.openf1.org/v1"``.
            cache_dir: Directory for cached responses; created on first write.
            min_interval_s: Minimum time between two network requests.
            session: HTTP session; a new ``requests.Session`` by default.
            is_empty: Predicate for responses that mean "no data" (cached as ``[]``).
            timeout_s: Timeout of a single request.
            max_retries: Retries after a 429/5xx answer or a connection error.
            backoff_s: Base delay of the exponential backoff between retries.
            sleep: Sleep function, replaceable in tests.
            clock: Monotonic clock, replaceable in tests.
        """
        self._base_url = base_url.rstrip("/")
        self._cache_dir = cache_dir
        self._min_interval_s = min_interval_s
        self._session = session or requests.Session()
        self._is_empty = is_empty
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self.network_requests = 0

    def get_json(self, path: str, params: QueryParams | None = None) -> JsonValue:
        """Return the JSON for a request, from the cache if possible.

        Args:
            path: API path relative to the base URL.
            params: Query parameters.

        Returns:
            Parsed JSON body (``[]`` for responses matched by ``is_empty``).

        Raises:
            HttpError: If the request keeps failing or returns an unexpected status.
        """
        cache_file = self._cache_dir / cache_file_name(path, params)
        if cache_file.is_file():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        data = self._fetch(path, params)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp_file.replace(cache_file)
        return data

    def _fetch(self, path: str, params: QueryParams | None) -> JsonValue:
        """Download one response, retrying transient failures."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        attempt = 0
        while True:
            self._wait_for_slot()
            self.network_requests += 1
            try:
                response = self._session.get(
                    url, params=params, timeout=self._timeout_s, headers={"User-Agent": USER_AGENT}
                )
            except requests.RequestException as error:
                if attempt >= self._max_retries:
                    raise HttpError(f"GET {url} failed: {error}") from error
                self._sleep(self._retry_delay(attempt, retry_after=None))
                attempt += 1
                continue

            if self._is_empty is not None and self._is_empty(response):
                return []
            if response.status_code in HTTP_RETRY_STATUSES and attempt < self._max_retries:
                self._sleep(self._retry_delay(attempt, response.headers.get("Retry-After")))
                attempt += 1
                continue
            if response.status_code != HTTPStatus.OK:
                raise HttpError(
                    f"GET {response.url} -> HTTP {response.status_code}: {response.text[:200]}"
                )
            return response.json()

    def _wait_for_slot(self) -> None:
        """Sleep so that requests are at least ``min_interval_s`` apart."""
        if self._last_request_at is not None:
            wait_s = self._min_interval_s - (self._clock() - self._last_request_at)
            if wait_s > 0:
                self._sleep(wait_s)
        self._last_request_at = self._clock()

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        """Return the delay before the next retry, honouring ``Retry-After`` seconds."""
        if retry_after is not None and retry_after.isdigit():
            return float(retry_after)
        return self._backoff_s * 2**attempt

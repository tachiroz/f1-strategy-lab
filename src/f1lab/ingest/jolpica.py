"""Jolpica-F1 (Ergast-compatible) API: race schedule, results and pit stops."""

from collections.abc import Iterator
from pathlib import Path

from f1lab.config import (
    JOLPICA_BASE_URL,
    JOLPICA_CACHE_DIR_NAME,
    JOLPICA_MIN_INTERVAL_S,
    JOLPICA_PAGE_LIMIT,
)
from f1lab.ingest.http import CachedHttpClient, JsonFetcher, JsonObject


class JolpicaClient:
    """Typed access to the Jolpica endpoints the loader needs.

    All values in Jolpica payloads are strings; conversion happens in
    ``f1lab.ingest.transform``.
    """

    def __init__(self, fetcher: JsonFetcher, page_limit: int = JOLPICA_PAGE_LIMIT) -> None:
        """Wrap a JSON fetcher.

        Args:
            fetcher: Source of JSON responses (cached HTTP client or test fixtures).
            page_limit: Page size for paginated endpoints.
        """
        self._fetcher = fetcher
        self._page_limit = page_limit

    def schedule(self, season: int) -> list[JsonObject]:
        """Return the races of a season (``Races`` objects without results)."""
        return [
            race for page in self._pages(f"{season}.json") for race in page["RaceTable"]["Races"]
        ]

    def results(self, season: int, round_number: int) -> list[JsonObject]:
        """Return the classification of a race; empty if the race has not run yet."""
        return self._race_rows(f"{season}/{round_number}/results.json", "Results")

    def pit_stops(self, season: int, round_number: int) -> list[JsonObject]:
        """Return all pit stops of a race in API order."""
        return self._race_rows(f"{season}/{round_number}/pitstops.json", "PitStops")

    def _race_rows(self, path: str, key: str) -> list[JsonObject]:
        """Collect the per-race list ``key`` across all pages of ``path``."""
        return [
            row
            for page in self._pages(path)
            for race in page["RaceTable"]["Races"]
            for row in race[key]
        ]

    def _pages(self, path: str) -> Iterator[JsonObject]:
        """Yield the ``MRData`` object of every page of a paginated endpoint."""
        offset = 0
        while True:
            body = self._fetcher.get_json(path, {"limit": self._page_limit, "offset": offset})
            page = body["MRData"]
            yield page
            offset += self._page_limit
            if offset >= int(page["total"]):
                return


def create_jolpica_client(cache_root: Path) -> JolpicaClient:
    """Create a Jolpica client backed by the HTTP cache under ``cache_root``."""
    http = CachedHttpClient(
        JOLPICA_BASE_URL, cache_root / JOLPICA_CACHE_DIR_NAME, JOLPICA_MIN_INTERVAL_S
    )
    return JolpicaClient(http)

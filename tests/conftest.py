"""Shared pytest fixtures."""

from pathlib import Path
from typing import cast

import pandas as pd
import pytest
import requests
from sqlalchemy import Engine

from f1lab.config import JOLPICA_CACHE_DIR_NAME, OPENF1_CACHE_DIR_NAME
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.ingest.http import CachedHttpClient
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.loader import RaceLoader
from f1lab.ingest.openf1 import OpenF1Client
from synthetic import complete_stints, make_synthetic_laps

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class OfflineSession:
    """HTTP session that fails loudly: tests must be served from fixtures only."""

    def get(self, url: str, **kwargs: object) -> None:
        raise AssertionError(f"Network access in tests, missing fixture for {url} {kwargs}")


def offline_fetcher(source_dir_name: str) -> CachedHttpClient:
    """Return a client that reads recorded responses from ``tests/fixtures``."""
    return CachedHttpClient(
        "https://offline.invalid",
        FIXTURES_DIR / source_dir_name,
        0.0,
        session=cast(requests.Session, OfflineSession()),
        max_retries=0,
    )


@pytest.fixture
def synthetic_laps() -> pd.DataFrame:
    """Synthetic clean laps (2023-2025, one circuit) with known model parameters."""
    return make_synthetic_laps()


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory with recorded API responses (HTTP cache layout)."""
    return FIXTURES_DIR


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """Return an engine for an empty, initialised SQLite database in a temp dir."""
    db_engine = create_sqlite_engine(tmp_path / "test.sqlite")
    init_db(db_engine)
    return db_engine


@pytest.fixture
def loaded(engine: Engine, jolpica: JolpicaClient, openf1: OpenF1Client) -> Engine:
    """Database with the recorded races loaded (2024 rounds 1 and 21)."""
    RaceLoader(engine, jolpica, openf1).load_season(2024, rounds=[1, 21])
    return engine


@pytest.fixture
def jolpica() -> JolpicaClient:
    """Jolpica client backed by recorded responses (2024 rounds 1 and 21)."""
    return JolpicaClient(offline_fetcher(JOLPICA_CACHE_DIR_NAME))


@pytest.fixture
def openf1() -> OpenF1Client:
    """OpenF1 client backed by recorded responses (sessions 9472 and 9636)."""
    return OpenF1Client(offline_fetcher(OPENF1_CACHE_DIR_NAME))


@pytest.fixture(scope="module")
def race_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Database file shared by a test module (read-only): the recorded races, every 2024
    Bahrain starter with a dry strategy so that the race can be simulated."""
    path = tmp_path_factory.mktemp("races") / "test.sqlite"
    db_engine = create_sqlite_engine(path)
    init_db(db_engine)
    RaceLoader(
        db_engine,
        JolpicaClient(offline_fetcher(JOLPICA_CACHE_DIR_NAME)),
        OpenF1Client(offline_fetcher(OPENF1_CACHE_DIR_NAME)),
    ).load_season(2024, rounds=[1, 21])
    complete_stints(db_engine, 202401, laps=57)
    db_engine.dispose()
    return path

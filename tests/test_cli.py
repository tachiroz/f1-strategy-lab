"""Tests for ``python -m f1lab.ingest`` (no network: every request gets HTTP 403)."""

import shutil
from pathlib import Path

import pytest
import requests
from sqlalchemy import func, select

from f1lab.db import schema
from f1lab.db.engine import create_sqlite_engine
from f1lab.ingest.__main__ import EXIT_OK, EXIT_RACE_FAILED, EXIT_USAGE, main


class Forbidden:
    status_code = 403
    url = "blocked"
    text = "network disabled in tests"
    headers: dict[str, str] = {}  # noqa: RUF012


@pytest.fixture
def cache_dir(tmp_path: Path, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy of the recorded responses; any request that misses it fails with 403."""
    monkeypatch.setattr(requests.Session, "get", lambda self, url, **kwargs: Forbidden())
    target = tmp_path / "cache"
    for source in ("jolpica", "openf1"):
        shutil.copytree(fixtures_dir / source, target / source)
    return target


def run(tmp_path: Path, cache_dir: Path, *args: str) -> int:
    return main([*args, "--db", str(tmp_path / "f1.sqlite"), "--cache-dir", str(cache_dir)])


def test_loads_selected_round(
    tmp_path: Path, cache_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, cache_dir, "--season", "2024", "--round", "1") == EXIT_OK
    assert "loaded: 1" in capsys.readouterr().out
    with create_sqlite_engine(tmp_path / "f1.sqlite").connect() as conn:
        assert conn.execute(select(func.count()).select_from(schema.races)).scalar_one() == 1


def test_missing_data_fails_the_race(tmp_path: Path, cache_dir: Path) -> None:
    (cache_dir / "openf1" / "laps__session_key=9472.json").unlink()
    assert run(tmp_path, cache_dir, "--season", "2024", "--round", "1") == EXIT_RACE_FAILED


def test_old_season_is_a_usage_error(tmp_path: Path, cache_dir: Path) -> None:
    assert run(tmp_path, cache_dir, "--season", "2018") == EXIT_USAGE


def test_unknown_round_is_a_usage_error(tmp_path: Path, cache_dir: Path) -> None:
    assert run(tmp_path, cache_dir, "--season", "2024", "--round", "99") == EXIT_USAGE

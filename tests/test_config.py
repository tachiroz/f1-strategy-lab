"""Tests for project paths in f1lab.config."""

from pathlib import Path

import pytest

from f1lab import config


def test_project_root_contains_pyproject() -> None:
    assert (config.PROJECT_ROOT / "pyproject.toml").is_file()


def test_default_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.DATA_DIR_ENV_VAR, raising=False)
    assert config.get_data_dir() == config.PROJECT_ROOT / "data"


def test_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(tmp_path))
    assert config.get_data_dir() == tmp_path.resolve()


def test_cache_and_db_follow_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(tmp_path))
    assert config.get_cache_dir() == tmp_path.resolve() / config.CACHE_DIR_NAME
    assert config.get_db_path() == tmp_path.resolve() / config.DB_FILE_NAME


def test_data_dir_is_not_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(missing))
    config.get_data_dir()
    assert not missing.exists()

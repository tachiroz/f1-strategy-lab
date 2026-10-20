"""Smoke tests: the package and all its subpackages import."""

import importlib

import pytest

import f1lab

SUBPACKAGES = ("ingest", "db", "models", "sim", "report", "api")


def test_version_is_set() -> None:
    assert f1lab.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"f1lab.{name}")
    assert module.__doc__

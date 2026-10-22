"""The dashboard's test fixtures must match the API contract.

The files in ``web/src/test/fixtures`` are real responses recorded by
``tests/fixtures/export_web_fixtures.py``; if a response model changes, this
test fails until they are recorded again.
"""

import json

import pytest
from pydantic import TypeAdapter

from f1lab.api.schemas import (
    CircuitSummary,
    RaceDetail,
    RaceSimulation,
    RaceSummary,
    ScSensitivity,
    StrategyComparison,
    TyreModel,
)
from fixtures.export_web_fixtures import FIXTURES, WEB_FIXTURES_DIR

MODELS: dict[str, object] = {
    "races.json": list[RaceSummary],
    "race-202504.json": RaceDetail,
    "race-202501.json": RaceDetail,
    "simulation-202504.json": RaceSimulation,
    "strategies-202504.json": StrategyComparison,
    "sc-sensitivity-202504.json": ScSensitivity,
    "circuits.json": list[CircuitSummary],
    "tyres-bahrain.json": TyreModel,
}


def keys(value: object, prefix: str = "") -> set[str]:
    """Dotted paths of every object key in a JSON value (list items merged)."""
    if isinstance(value, dict):
        return {
            path
            for key, item in value.items()
            for path in {f"{prefix}{key}", *keys(item, f"{prefix}{key}.")}
        }
    if isinstance(value, list):
        return {path for item in value for path in keys(item, prefix)}
    return set()


def test_every_fixture_has_a_model() -> None:
    assert set(MODELS) == set(FIXTURES)
    assert {path.name for path in WEB_FIXTURES_DIR.glob("*.json")} == set(FIXTURES)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_fixture_matches_the_response_model(name: str) -> None:
    raw = (WEB_FIXTURES_DIR / name).read_text(encoding="utf-8")
    adapter = TypeAdapter(MODELS[name])
    parsed = adapter.validate_json(raw, strict=True)
    # No extra and no missing keys: the web tests see exactly what the API returns.
    assert keys(json.loads(raw)) == keys(adapter.dump_python(parsed))


def test_keys_walks_nested_values() -> None:
    assert keys({"a": [{"b": 1}, {"c": {"d": 2}}]}) == {"a", "a.b", "a.c", "a.c.d"}

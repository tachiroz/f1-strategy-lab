"""Tests for the FastAPI application (recorded races: Bahrain 2024 dry, São Paulo 2024 wet)."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from f1lab import __version__
from f1lab.api.main import create_app
from f1lab.api.service import Lab, observed_deltas
from f1lab.config import MAX_COMPARED_STRATEGIES, MIN_OBSERVED_LAPS, SC_SENSITIVITY_SCALES
from f1lab.models.degradation import fit_circuit

BAHRAIN, SAO_PAULO = 202401, 202421
RUNS, SENSITIVITY_RUNS = 200, 50


@pytest.fixture(scope="module")
def client(race_db: Path) -> Iterator[TestClient]:
    with TestClient(create_app(race_db, runs=RUNS, sensitivity_runs=SENSITIVITY_RUNS)) as api:
        yield api


def compare(
    client: TestClient, endpoint: str, *strategies: str, driver: str = "max_verstappen"
) -> Response:
    params = [("driver", driver), *(("strategy", s) for s in strategies)]
    return client.get(f"/api/races/{BAHRAIN}/{endpoint}", params=params)


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "version": __version__}


def test_app_does_not_touch_the_disk_before_a_request(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "f1lab.sqlite"
    with TestClient(create_app(db_path)) as api:
        assert not db_path.parent.exists()
        assert api.get("/api/races").json() == []  # an empty database is created on demand
    assert db_path.exists()


def test_races(client: TestClient) -> None:
    races = {race["race_id"]: race for race in client.get("/api/races").json()}
    assert list(races) == [BAHRAIN, SAO_PAULO]
    bahrain, sao_paulo = races[BAHRAIN], races[SAO_PAULO]
    assert bahrain["race_name"] == "Bahrain Grand Prix"
    assert bahrain["date"] == "2024-03-02"
    assert (bahrain["simulatable"], bahrain["reason"], bahrain["in_sample"]) == (True, None, True)
    assert not sao_paulo["simulatable"]
    assert sao_paulo["reason"] == "No tyre model for interlagos"  # only wet laps recorded there


def test_race_detail(client: TestClient) -> None:
    race = client.get(f"/api/races/{BAHRAIN}").json()
    assert race["race_laps"] == 57
    drivers = {driver["driver_id"]: driver for driver in race["drivers"]}
    assert len(drivers) == 20
    winner = race["drivers"][0]
    assert (winner["driver_id"], winner["finish_position"], winner["code"]) == (
        "max_verstappen",
        1,
        "VER",
    )
    assert winner["name"] == "Max Verstappen"
    assert winner["team"] == "Red Bull"
    stints = winner["strategy"]["stints"]
    assert stints[0]["first_lap"] == 1
    assert stints[-1]["last_lap"] == 57
    counts = [entry["drivers"] for entry in race["field_strategies"]]
    assert counts == sorted(counts, reverse=True)


def test_wet_race_detail_has_no_strategies(client: TestClient) -> None:
    race = client.get(f"/api/races/{SAO_PAULO}").json()
    assert not race["simulatable"]
    assert all(driver["strategy"] is None for driver in race["drivers"])
    assert race["field_strategies"] == []


def test_unknown_race_is_404(client: TestClient) -> None:
    response = client.get("/api/races/190001")
    assert response.status_code == 404
    assert "190001" in response.json()["detail"]


def test_simulation(client: TestClient) -> None:
    simulation = client.get(f"/api/races/{BAHRAIN}/simulation").json()
    assert (simulation["race_id"], simulation["runs"]) == (BAHRAIN, RUNS)
    drivers = simulation["drivers"]
    assert len(drivers) == 20
    means = [driver["mean_position"]["value"] for driver in drivers]
    assert means == sorted(means)
    for driver in drivers:
        assert len(driver["histogram"]) == 21  # 20 positions and retirements
        assert sum(driver["histogram"]) == pytest.approx(1.0)
        assert driver["histogram"][-1] == pytest.approx(driver["p_retire"])
        p_win = driver["p_win"]
        assert p_win["low"] - 1e-9 <= p_win["value"] <= p_win["high"] + 1e-9
    assert 0 <= simulation["p_safety_car"] <= 1
    score = simulation["score"]
    assert score["finishers"] == sum(d["actual_position"] is not None for d in drivers)
    assert score["mae"] >= 0


def test_wet_race_cannot_be_simulated(client: TestClient) -> None:
    response = client.get(f"/api/races/{SAO_PAULO}/simulation")
    assert response.status_code == 422
    assert response.json()["detail"] == "No tyre model for interlagos"


def test_strategy_comparison(client: TestClient) -> None:
    comparison = compare(client, "strategies", "S-20-H", "h-30-s").json()
    actual, first, second = comparison["strategies"]
    assert actual["is_actual"]
    assert actual["delta"] == {"value": 0.0, "low": 0.0, "high": 0.0}
    assert (first["notation"], first["is_actual"]) == ("S-20-H", False)
    assert second["notation"] == "H-30-S"
    assert first["stints"] == [
        {"compound": "SOFT", "first_lap": 1, "last_lap": 20},
        {"compound": "HARD", "first_lap": 21, "last_lap": 57},
    ]
    assert sum(first["histogram"]) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("strategies", "driver", "status", "message"),
    [
        (["X-20-H"], "max_verstappen", 422, "Unknown compound"),
        (["S-20-S"], "max_verstappen", 422, "at least 2 compounds"),
        (["S-60-H"], "max_verstappen", 422, "between 1 and 56"),
        (["M-30-H"], "max_verstappen", 422, "No tyre model for ['MEDIUM']"),
        (["S-20-H"] * MAX_COMPARED_STRATEGIES, "max_verstappen", 422, "at most"),
        (["S-20-H"], "nobody", 404, "did not start"),
    ],
)
def test_strategy_errors(
    client: TestClient, strategies: list[str], driver: str, status: int, message: str
) -> None:
    response = compare(client, "strategies", *strategies, driver=driver)
    assert response.status_code == status
    assert message in response.json()["detail"]


def test_sc_sensitivity(client: TestClient) -> None:
    sensitivity = compare(client, "sc-sensitivity", "S-20-H").json()
    assert sensitivity["scales"] == list(SC_SENSITIVITY_SCALES)
    assert sensitivity["runs"] == SENSITIVITY_RUNS
    actual, alternative = sensitivity["series"]
    assert actual["is_actual"]
    assert alternative["label"] == "S-20-H"
    calm = actual["points"][0]
    assert (calm["scale"], calm["p_safety_car"]) == (0.0, 0.0)
    shares = [point["p_safety_car"] for point in actual["points"]]
    assert shares == sorted(shares)
    assert shares == [point["p_safety_car"] for point in alternative["points"]]


def test_circuits_and_tyres(client: TestClient) -> None:
    circuits = client.get("/api/circuits").json()
    assert [circuit["circuit_id"] for circuit in circuits] == ["bahrain"]
    slopes = circuits[0]["degradation_s_per_lap"]
    assert set(slopes) == set(circuits[0]["compounds"])
    tyres = client.get("/api/circuits/bahrain/tyres").json()
    assert tyres["circuit_name"] == "Bahrain International Circuit"
    assert tyres["fuel_s_per_lap"]["value"] < 0  # cars get faster as fuel burns off
    for compound in tyres["compounds"]:
        assert compound["degradation_s_per_lap"] == slopes[compound["compound"]]
        curve = compound["curve"]
        assert curve[0]["delta_s"] == pytest.approx(compound["offset_s"]["value"])
        assert len(curve) == compound["max_tyre_age"] + 1
        assert all(point["laps"] >= 5 for point in compound["observed"])
    assert client.get("/api/circuits/monaco/tyres").status_code == 404


def test_simulations_are_cached(race_db: Path) -> None:
    lab = Lab(race_db, runs=20)
    assert lab.simulation(BAHRAIN) is lab.simulation(BAHRAIN)
    assert lab.compare(BAHRAIN, "max_verstappen", ()) is lab.compare(BAHRAIN, "max_verstappen", ())


def test_observed_deltas_follow_the_model(synthetic_laps: pd.DataFrame) -> None:
    model = fit_circuit(synthetic_laps)
    observed = observed_deltas(model, synthetic_laps)
    assert set(observed["compound"]) == {"SOFT", "MEDIUM", "HARD"}
    assert (observed["laps"] >= MIN_OBSERVED_LAPS).all()
    for compound, points in observed.groupby("compound"):
        curve = (
            model.compound_offset_s[compound].value
            + model.degradation_s_per_lap[compound].value * points["tyre_age"]
        )
        assert (points["delta_s"] - curve).abs().max() < 0.2

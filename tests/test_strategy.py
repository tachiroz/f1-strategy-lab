"""Tests for race strategies (notation, rules, lap plans, real stints)."""

import pandas as pd
import pytest
from sqlalchemy import Engine, text

from f1lab.sim.strategy import (
    Stop,
    Strategy,
    StrategyError,
    lap_plan,
    parse_strategy,
    strategy_from_stints,
    validate_strategy,
)


def driver_frames(engine: Engine, race_id: int, driver: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    params = {"race": race_id, "driver": driver}
    with engine.connect() as conn:
        stints = pd.read_sql(
            text("SELECT * FROM stints WHERE race_id = :race AND driver_id = :driver"),
            conn,
            params=params,
        )
        stops = pd.read_sql(
            text("SELECT * FROM pit_stops WHERE race_id = :race AND driver_id = :driver"),
            conn,
            params=params,
        )
    return stints, stops


def test_parse_simple_strategy() -> None:
    strategy = parse_strategy("M-18-H")
    assert strategy == Strategy("MEDIUM", (Stop(18, "HARD"),))
    assert strategy.notation() == "M-18-H"


def test_parse_used_tyres_and_two_stops() -> None:
    strategy = parse_strategy(" s3-15-h-38-m ")
    assert strategy.start_age == 3
    assert strategy.compounds == ["SOFT", "HARD", "MEDIUM"]
    assert strategy.notation() == "S3-15-H-38-M"


@pytest.mark.parametrize("text", ["", "X-10-H", "M-18", "M-H", "M--H"])
def test_parse_rejects_bad_notation(text: str) -> None:
    with pytest.raises(StrategyError):
        parse_strategy(text)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("M-0-H", "between"),
        ("M-57-H", "between"),
        ("M-30-H-20-S", "increasing"),
        ("M-20-M", "compounds"),
    ],
)
def test_validate_rejects_rule_breaks(text: str, message: str) -> None:
    with pytest.raises(StrategyError, match=message):
        validate_strategy(parse_strategy(text), race_laps=57)


def test_validate_accepts_legal_strategy() -> None:
    validate_strategy(parse_strategy("S3-15-H-38-M"), race_laps=57)


def test_lap_plan() -> None:
    plan = lap_plan(parse_strategy("S3-15-H"), race_laps=20).set_index("lap")
    assert (plan.loc[1, "compound"], plan.loc[1, "tyre_age"]) == ("SOFT", 3)
    assert (plan.loc[15, "compound"], plan.loc[15, "tyre_age"], plan.loc[15, "pit"]) == (
        "SOFT",
        17,
        True,
    )
    assert (plan.loc[16, "compound"], plan.loc[16, "tyre_age"]) == ("HARD", 0)
    assert plan.loc[20, "tyre_age"] == 4
    assert plan["pit"].sum() == 1


def test_strategy_from_real_stints(loaded: Engine) -> None:
    stints, stops = driver_frames(loaded, 202401, "max_verstappen")
    assert strategy_from_stints(stints, stops).notation() == "S3-17-H-37-S"


def test_shared_boundary_lap_gives_the_same_stop(loaded: Engine) -> None:
    stints, _ = driver_frames(loaded, 202401, "max_verstappen")
    shared = stints.assign(lap_start=stints["lap_start"].where(stints["stint"] != 2, 17))
    assert strategy_from_stints(shared).notation() == "S3-17-H-37-S"


def test_red_flag_tyre_change_is_free(loaded: Engine) -> None:
    # São Paulo 2024: the field changed tyres in the pit lane during the red flag on lap 32.
    stints, stops = driver_frames(loaded, 202421, "max_verstappen")
    strategy = strategy_from_stints(stints, stops)
    assert [(s.lap, s.free) for s in strategy.stops] == [(32, True)]


def test_zero_lap_stints_are_skipped() -> None:
    stints = pd.DataFrame(
        {
            "stint": [1, 2, 3],
            "compound": ["MEDIUM", "SOFT", "HARD"],
            "lap_start": [1, 1, 1],
            "lap_end": [0, 30, 57],
            "tyre_age_at_start": [0, 0, 0],
        }
    )
    stints.loc[2, "lap_start"] = 31
    assert strategy_from_stints(stints).notation() == "S-30-H"


def test_no_usable_stints() -> None:
    stints = pd.DataFrame(
        {"stint": [1], "compound": ["INTERMEDIATE"], "lap_start": [None], "lap_end": [None]}
    ).assign(tyre_age_at_start=0)
    with pytest.raises(StrategyError):
        strategy_from_stints(stints)

"""Tests for pit lane passes behind the Safety Car.

Real data: Australian Grand Prix 2025, where the Safety Car led the field through
the pit lane on laps 2-4. ``tests/fixtures/pitlane/australia_2025.json`` was
extracted from the database with::

    SELECT seq, time_utc, lap, category, flag, scope, message FROM race_control
    WHERE race_id = 202501 AND (category IN ('SafetyCar', 'Flag')
                                OR message LIKE '%PIT LANE%') ORDER BY seq;
    SELECT driver_id, stint, compound, lap_start, lap_end, tyre_age_at_start
    FROM stints WHERE race_id = 202501 ORDER BY driver_id, stint;
    SELECT driver_id, stop, lap, duration_s FROM pit_stops
    WHERE race_id = 202501 ORDER BY driver_id, stop;
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from f1lab.config import PIT_LANE_PASS_MARGIN_S
from f1lab.models.pitlane import (
    PassWindow,
    merge_pit_lane_passes,
    pass_windows,
    pit_lane_passes,
)
from f1lab.sim.strategy import strategy_from_stints

FIXTURE = Path(__file__).parent / "fixtures" / "pitlane" / "australia_2025.json"
WINDOW = PassWindow(1, 7)
PASS_S = 14.0


@pytest.fixture(scope="module")
def australia() -> dict[str, pd.DataFrame]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    frames = {name: pd.DataFrame(raw[name]) for name in ("race_control", "stints", "pit_stops")}
    messages = frames["race_control"]
    messages["time_utc"] = pd.to_datetime(messages["time_utc"], utc=True)
    return frames


def stints(*rows: tuple[str, int, str, int, int]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"driver_id": d, "stint": n, "compound": c, "lap_start": a, "lap_end": b}
            for d, n, c, a, b in rows
        ]
    ).assign(tyre_age_at_start=0)


def visits(*rows: tuple[str, int, float]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["driver_id", "lap", "duration_s"])


def test_window_from_the_message_to_the_end_of_the_safety_car(
    australia: dict[str, pd.DataFrame],
) -> None:
    assert pass_windows(australia["race_control"]) == [WINDOW]
    plain = australia["race_control"]
    plain = plain[~plain["message"].str.contains("PIT LANE")]
    assert pass_windows(plain) == []
    assert 1 in WINDOW
    assert 7 in WINDOW
    assert 8 not in WINDOW


def test_passes_in_the_real_race(australia: dict[str, pd.DataFrame]) -> None:
    stops = australia["pit_stops"]
    passes = pit_lane_passes(stops, australia["stints"], [WINDOW])
    norris = stops["driver_id"] == "norris"
    assert dict(zip(stops.loc[norris, "lap"], passes[norris], strict=True)) == {
        2: True,
        3: True,
        4: True,
        34: False,
        44: False,
    }
    lawson = (stops["driver_id"] == "lawson") & (stops["lap"] == 4)
    assert not passes[lawson].any()  # 18.9 s against a median of about 15: a real stop
    assert int(passes.sum()) == 47
    assert not passes[~stops["lap"].map(lambda lap: lap in WINDOW)].any()


def test_merged_strategy_has_only_the_real_stops(australia: dict[str, pd.DataFrame]) -> None:
    merged = merge_pit_lane_passes(australia["stints"], australia["pit_stops"], [WINDOW])
    norris = merged[merged["driver_id"] == "norris"].sort_values("stint")
    assert list(zip(norris["compound"], norris["lap_start"], norris["lap_end"], strict=True)) == [
        ("INTERMEDIATE", 1, 34),
        ("HARD", 34, 44),
        ("INTERMEDIATE", 44, 57),
    ]
    stops = australia["pit_stops"]
    strategy = strategy_from_stints(norris, stops[stops["driver_id"] == "norris"])
    assert [(stop.lap, stop.compound) for stop in strategy.stops] == [
        (34, "HARD"),
        (44, "INTERMEDIATE"),
    ]


def test_a_compound_change_is_always_a_stop() -> None:
    laps = stints(("a", 1, "MEDIUM", 1, 3), ("a", 2, "HARD", 3, 50))
    stops = visits(("a", 3, PASS_S), ("b", 3, PASS_S), ("c", 3, PASS_S))
    assert pit_lane_passes(stops, laps, [WINDOW]).tolist() == [False, True, True]


def test_a_long_visit_with_the_same_compound_is_a_stop() -> None:
    laps = stints(("a", 1, "MEDIUM", 1, 3), ("a", 2, "MEDIUM", 3, 50))
    slow = PASS_S + PIT_LANE_PASS_MARGIN_S + 1
    stops = visits(("a", 3, slow), ("b", 3, PASS_S), ("c", 3, PASS_S))
    assert pit_lane_passes(stops, laps, [WINDOW]).tolist() == [False, True, True]
    merged = merge_pit_lane_passes(laps, stops, [WINDOW])
    assert len(merged) == len(laps)


def test_splits_merge_only_inside_a_window() -> None:
    laps = stints(
        ("a", 1, "MEDIUM", 1, 2),
        ("a", 2, "MEDIUM", 3, 20),  # split by a pass on lap 2 (stint ends a lap early)
        ("a", 3, "MEDIUM", 21, 50),  # same compound, but outside the window: a real stop
    )
    stops = visits(("a", 3, PASS_S), ("a", 21, PASS_S))
    merged = merge_pit_lane_passes(laps, stops, [WINDOW])
    assert list(zip(merged["lap_start"], merged["lap_end"], strict=True)) == [(1, 20), (21, 50)]


def test_no_window_changes_nothing() -> None:
    laps = stints(("a", 1, "MEDIUM", 1, 3), ("a", 2, "MEDIUM", 3, 50))
    stops = visits(("a", 3, PASS_S))
    assert merge_pit_lane_passes(laps, stops, []) is laps
    assert not pit_lane_passes(stops, laps, []).any()


def test_stints_without_laps_are_kept() -> None:
    laps = pd.concat(
        [
            stints(("a", 1, "MEDIUM", 1, 3), ("a", 2, "MEDIUM", 3, 50)),
            stints(("b", 1, "HARD", 1, 1)).assign(lap_start=None, lap_end=None),
        ],
        ignore_index=True,
    )
    merged = merge_pit_lane_passes(laps, visits(("a", 3, PASS_S)), [WINDOW])
    assert merged["driver_id"].tolist() == ["a", "b"]

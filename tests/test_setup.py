"""Tests for rebuilding the strategies of a race's starters."""

import pandas as pd
import pytest

from f1lab.sim.setup import SetupError, actual_strategies


def stint(driver: str, number: int, compound: str, start: int, end: int) -> dict[str, object]:
    return {
        "driver_id": driver,
        "stint": number,
        "compound": compound,
        "lap_start": start,
        "lap_end": end,
        "tyre_age_at_start": 0,
    }


NO_STOPS = pd.DataFrame(columns=["driver_id", "lap", "duration_s"])


def test_early_retiree_gets_the_most_common_strategy() -> None:
    starters = pd.DataFrame(
        {"driver_id": ["a", "b", "c", "d"], "status": ["Finished", "Finished", "Lapped", "Retired"]}
    )
    stints = pd.DataFrame(
        [
            stint("a", 1, "MEDIUM", 1, 20), stint("a", 2, "HARD", 21, 50),
            stint("b", 1, "MEDIUM", 1, 20), stint("b", 2, "HARD", 21, 50),
            stint("c", 1, "SOFT", 1, 15), stint("c", 2, "HARD", 16, 50),
            stint("d", 1, "SOFT", 1, 8),
        ]
    )  # fmt: skip
    strategies = actual_strategies(starters, stints, NO_STOPS, race_laps=50)
    assert strategies["a"].notation() == "M-20-H"
    assert strategies["d"].notation() == "M-20-H"
    assert strategies["d"].label == "most common (retired early)"


def test_finisher_with_an_incomplete_strategy_is_an_error() -> None:
    starters = pd.DataFrame({"driver_id": ["a"], "status": ["Finished"]})
    stints = pd.DataFrame([stint("a", 1, "MEDIUM", 1, 50)])
    with pytest.raises(SetupError, match="a:"):
        actual_strategies(starters, stints, NO_STOPS, race_laps=50)


def test_stints_after_the_flag_are_ignored() -> None:
    # Alonso, Belgium 2024: OpenF1 lists a one-lap stint after the 44-lap race.
    starters = pd.DataFrame({"driver_id": ["alonso"], "status": ["Finished"]})
    stints = pd.DataFrame(
        [
            stint("alonso", 1, "MEDIUM", 1, 13),
            stint("alonso", 2, "HARD", 14, 44),
            stint("alonso", 3, "MEDIUM", 45, 45),
        ]
    )
    assert actual_strategies(starters, stints, NO_STOPS, race_laps=44)["alonso"].notation() == (
        "M-13-H"
    )

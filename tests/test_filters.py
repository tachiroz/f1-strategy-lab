"""Tests for the clean-lap rules."""

import pandas as pd
import pytest
from sqlalchemy import Engine

from f1lab.config import MIN_CLEAN_LAPS_PER_DRIVER
from f1lab.models.filters import Exclusion, annotate_laps, clean_laps, exclusion_summary
from f1lab.models.laps import load_model_laps, load_race_control, load_rainfall

START = pd.Timestamp("2025-01-01 12:00:00", tz="UTC")
LAP_S = 90.0


def at_lap(lap: int, seconds: float = 0.0) -> pd.Timestamp:
    """Start time of a synthetic lap plus an offset."""
    return START + pd.Timedelta(seconds=(lap - 1) * LAP_S + seconds)


def make_laps(n: int = 10, driver: str = "driver") -> pd.DataFrame:
    """One race, one driver, n dry laps of 90 s on softs."""
    laps = pd.DataFrame(
        {
            "race_id": 1,
            "driver_id": driver,
            "lap": range(1, n + 1),
            "start_time_utc": [at_lap(lap) for lap in range(1, n + 1)],
            "lap_time_s": LAP_S,
            "is_pit_in_lap": False,
            "is_pit_out_lap": False,
            "compound": "SOFT",
            "tyre_age": pd.array(range(1, n + 1), dtype="Int64"),
        }
    )
    laps["compound"] = laps["compound"].astype("object")
    return laps


def no_messages() -> pd.DataFrame:
    return pd.DataFrame(
        {"race_id": pd.Series(dtype=int), "time_utc": pd.Series(dtype="datetime64[ns, UTC]")}
    ).assign(flag=None, scope=None, message=None)


def no_rain() -> pd.DataFrame:
    return pd.DataFrame({"race_id": [1], "time_utc": [START], "rainfall": [False]})


def reasons(
    laps: pd.DataFrame, messages: pd.DataFrame | None = None, rain: pd.DataFrame | None = None
) -> dict[int, str]:
    annotated = annotate_laps(
        laps, no_messages() if messages is None else messages, no_rain() if rain is None else rain
    )
    return {
        int(lap): reason
        for lap, reason in zip(annotated["lap"], annotated["exclusion"], strict=True)
        if not pd.isna(reason)
    }


def test_only_the_first_lap_is_excluded_on_clean_data() -> None:
    assert reasons(make_laps()) == {1: Exclusion.FIRST_LAP}


def test_first_matching_rule_wins() -> None:
    laps = make_laps()
    laps.loc[0, "lap_time_s"] = None
    assert reasons(laps)[1] == Exclusion.UNTIMED


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("is_pit_in_lap", True, Exclusion.PIT_IN),
        ("is_pit_out_lap", True, Exclusion.PIT_OUT),
        ("compound", None, Exclusion.NO_TYRE),
        ("compound", "INTERMEDIATE", Exclusion.NOT_DRY),
        ("compound", "UNKNOWN", Exclusion.NOT_DRY),
    ],
)
def test_single_lap_rules(column: str, value: object, reason: Exclusion) -> None:
    laps = make_laps()
    laps.loc[4, column] = value
    assert reasons(laps)[5] == reason


def test_neutralised_lap_and_restart_lap() -> None:
    messages = pd.DataFrame(
        {
            "race_id": 1,
            "time_utc": [at_lap(4, 10), at_lap(4, 20), at_lap(4, 30)],
            "flag": [None, None, "CLEAR"],
            "scope": [None, None, "Track"],
            "message": ["VIRTUAL SAFETY CAR DEPLOYED", "VIRTUAL SAFETY CAR ENDING", "TRACK CLEAR"],
        }
    )
    found = reasons(make_laps(), messages)
    assert found[4] == Exclusion.NEUTRALISED
    assert found[5] == Exclusion.AFTER_NEUTRALISATION
    assert 6 not in found


def test_rain_at_lap_start_or_end() -> None:
    rain = pd.DataFrame(
        {
            "race_id": 1,
            "time_utc": [START, at_lap(6, 45), at_lap(7, 10)],
            "rainfall": [False, True, False],
        }
    )
    found = reasons(make_laps(), rain=rain)
    assert {lap for lap, reason in found.items() if reason == Exclusion.RAIN} == {6, 7}


def test_slow_outlier() -> None:
    laps = make_laps()
    laps.loc[5, "lap_time_s"] = 100.0  # > 5% slower than the 90 s median
    laps.loc[6, "lap_time_s"] = 93.0  # within 5%
    found = reasons(laps)
    assert found[6] == Exclusion.OUTLIER
    assert 7 not in found


def test_driver_with_too_few_clean_laps() -> None:
    laps = make_laps(n=MIN_CLEAN_LAPS_PER_DRIVER)  # lap 1 excluded, so one lap short
    found = reasons(laps)
    assert set(found.values()) == {Exclusion.FIRST_LAP, Exclusion.FEW_LAPS}


def test_summary_and_clean_laps() -> None:
    annotated = annotate_laps(make_laps(), no_messages(), no_rain())
    summary = exclusion_summary(annotated)
    assert summary.sum() == len(annotated)
    assert summary["clean"] == len(clean_laps(annotated)) == 9
    assert list(summary.index)[-1] == "clean"


def test_recorded_races(loaded: Engine) -> None:
    laps = load_model_laps(loaded, [2024])
    race_ids = laps["race_id"].unique().tolist()
    annotated = annotate_laps(
        laps, load_race_control(loaded, race_ids), load_rainfall(loaded, race_ids)
    )
    clean = clean_laps(annotated)
    assert clean[clean["race_id"] == 202421].empty  # São Paulo: wet race
    bahrain = clean[clean["race_id"] == 202401]
    assert set(bahrain["driver_id"]) == {"max_verstappen", "hulkenberg"}
    assert 45 <= (bahrain["driver_id"] == "max_verstappen").sum() <= 54
    assert set(bahrain["compound"]) <= {"SOFT", "MEDIUM", "HARD"}

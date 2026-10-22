"""Tests for SC/VSC/red flag periods (real São Paulo 2024 messages + edge cases)."""

import pandas as pd
from sqlalchemy import Engine

from f1lab.models.laps import load_race_control
from f1lab.models.neutralisation import (
    Neutralisation,
    Period,
    flag_neutralised_laps,
    lap_states,
    neutralisation_periods,
)

SC, VSC, RED = Neutralisation.SAFETY_CAR, Neutralisation.VIRTUAL_SAFETY_CAR, Neutralisation.RED_FLAG


def ts(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz="UTC")


def messages(*rows: tuple[str, str | None, str | None, str]) -> pd.DataFrame:
    """Build race control messages from (time, flag, scope, message) tuples."""
    frame = pd.DataFrame(rows, columns=["time_utc", "flag", "scope", "message"])
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    return frame


def test_sao_paulo_2024_periods(loaded: Engine) -> None:
    periods = neutralisation_periods(load_race_control(loaded, [202421]))
    assert periods == [
        Period(VSC, ts("2024-11-03 16:28:21"), ts("2024-11-03 16:30:04")),
        Period(SC, ts("2024-11-03 16:32:53"), ts("2024-11-03 16:37:22")),  # ended by red flag
        Period(RED, ts("2024-11-03 16:37:22"), ts("2024-11-03 17:02:00.390")),
        Period(SC, ts("2024-11-03 17:13:14"), ts("2024-11-03 17:19:29")),
    ]


def test_bahrain_2024_has_no_neutralisation(loaded: Engine) -> None:
    assert neutralisation_periods(load_race_control(loaded, [202401])) == []


def test_sc_waits_for_track_clear_after_in_this_lap() -> None:
    periods = neutralisation_periods(
        messages(
            ("2025-01-01 12:00:00", None, None, "SAFETY CAR DEPLOYED"),
            ("2025-01-01 12:01:00", "CLEAR", "Track", "TRACK CLEAR"),  # before IN THIS LAP
            ("2025-01-01 12:04:00", None, None, "SAFETY CAR IN THIS LAP"),
            ("2025-01-01 12:05:10", "CLEAR", "Track", "TRACK CLEAR"),
        )
    )
    assert periods == [Period(SC, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:05:10"))]


def test_sc_ended_by_chequered_flag() -> None:
    periods = neutralisation_periods(
        messages(
            ("2025-01-01 12:00:00", None, None, "SAFETY CAR DEPLOYED"),
            ("2025-01-01 12:03:00", "CHEQUERED", "Track", "CHEQUERED FLAG"),
        )
    )
    assert periods == [Period(SC, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:03:00"))]


def test_red_flag_without_restart_ends_at_last_message() -> None:
    periods = neutralisation_periods(
        messages(
            ("2025-01-01 12:00:00", "RED", "Track", "RED FLAG"),
            ("2025-01-01 12:30:00", None, None, "SESSION FINISHED"),
        )
    )
    assert periods == [Period(RED, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:30:00"))]


def test_repeated_deployment_does_not_split_the_period() -> None:
    periods = neutralisation_periods(
        messages(
            ("2025-01-01 12:00:00", None, None, "VIRTUAL SAFETY CAR DEPLOYED"),
            ("2025-01-01 12:00:30", None, None, "VIRTUAL SAFETY CAR DEPLOYED"),
            ("2025-01-01 12:01:00", None, None, "VIRTUAL SAFETY CAR ENDING"),
            ("2025-01-01 12:01:12", "GREEN", "Track", "GREEN LIGHT - PIT EXIT OPEN"),
        )
    )
    assert periods == [Period(VSC, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:01:12"))]


def test_session_start_without_red_flag_is_ignored() -> None:
    periods = neutralisation_periods(
        messages(("2025-01-01 12:00:00", None, None, "SESSION STARTED"))
    )
    assert periods == []


def test_flag_neutralised_laps_by_overlap() -> None:
    laps = pd.DataFrame(
        {
            "race_id": [1, 1, 1, 1, 2],
            "start_time_utc": pd.to_datetime(
                [
                    "2025-01-01 11:58:00",  # ends 11:59:30, before the period
                    "2025-01-01 11:59:30",  # ends 12:01:00, overlaps the start
                    "2025-01-01 12:05:00",  # starts after the period
                    "2025-01-01 12:00:30",  # untimed: cannot be placed
                    "2025-01-01 12:00:30",  # other race
                ],
                utc=True,
            ),
            "lap_time_s": [90.0, 90.0, 90.0, None, 90.0],
        }
    )
    periods = {1: [Period(SC, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:04:00"))]}
    assert flag_neutralised_laps(laps, periods).tolist() == [False, True, False, False, False]


def test_lap_states_prefer_the_strongest_period() -> None:
    laps = pd.DataFrame(
        {
            "race_id": [1, 1, 1, 1],
            "start_time_utc": pd.to_datetime(
                [
                    "2025-01-01 11:50:00",  # green
                    "2025-01-01 11:59:30",  # overlaps the VSC
                    "2025-01-01 12:09:30",  # overlaps the VSC and the red flag
                    "2025-01-01 12:30:00",  # after everything
                ],
                utc=True,
            ),
            "lap_time_s": [90.0, 90.0, 90.0, 90.0],
        }
    )
    periods = {
        1: [
            Period(VSC, ts("2025-01-01 12:00:00"), ts("2025-01-01 12:10:00")),
            Period(RED, ts("2025-01-01 12:10:00"), ts("2025-01-01 12:20:00")),
        ]
    }
    assert lap_states(laps, periods).tolist() == ["GREEN", "VSC", "RED", "GREEN"]

"""Safety Car, Virtual Safety Car and red flag periods from race control messages.

OpenF1 has no per-lap Safety Car flag, so periods are rebuilt from the messages.
Rules, checked on every 2023-2025 race:

* SC: from "SAFETY CAR DEPLOYED" until the first track-wide CLEAR/GREEN flag after
  "SAFETY CAR IN THIS LAP" (the restart, 26-137 s later). A red flag or the
  chequered flag ends it earlier (6 of 46 deployments).
* VSC: the same with "VIRTUAL SAFETY CAR DEPLOYED" / "... ENDING" (11-15 s).
* Red flag: from the RED flag until the next "SESSION STARTED".

A period still open at the last message ends there.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from f1lab.config import (
    FIRST_RACE_LAP,
    RC_FLAG_CHEQUERED,
    RC_FLAG_RED,
    RC_GREEN_FLAGS,
    RC_SC_DEPLOYED,
    RC_SC_ENDING,
    RC_SESSION_STARTED,
    RC_TRACK_SCOPE,
    RC_VSC_DEPLOYED,
    RC_VSC_ENDING,
)


class Neutralisation(StrEnum):
    """Kind of neutralisation period."""

    SAFETY_CAR = "SC"
    VIRTUAL_SAFETY_CAR = "VSC"
    RED_FLAG = "RED"


@dataclass(frozen=True)
class Period:
    """A time interval during which the race was neutralised."""

    kind: Neutralisation
    start: pd.Timestamp
    end: pd.Timestamp


_DEPLOYED = {
    RC_SC_DEPLOYED: Neutralisation.SAFETY_CAR,
    RC_VSC_DEPLOYED: Neutralisation.VIRTUAL_SAFETY_CAR,
}
_ENDING = {
    RC_SC_ENDING: Neutralisation.SAFETY_CAR,
    RC_VSC_ENDING: Neutralisation.VIRTUAL_SAFETY_CAR,
}
_CAUTIONS = (Neutralisation.SAFETY_CAR, Neutralisation.VIRTUAL_SAFETY_CAR)


def neutralisation_periods(messages: pd.DataFrame) -> list[Period]:
    """Rebuild the SC/VSC/red flag periods of one race.

    Args:
        messages: Race control messages of a single race with columns
            ``time_utc``, ``flag``, ``scope`` and ``message``, in chronological order.

    Returns:
        Periods in the order they end.
    """
    periods: list[Period] = []
    opened: dict[Neutralisation, pd.Timestamp] = {}
    ending: set[Neutralisation] = set()

    def close(kind: Neutralisation, at: pd.Timestamp) -> None:
        if kind in opened:
            periods.append(Period(kind, opened.pop(kind), at))
        ending.discard(kind)

    for message in messages.itertuples(index=False):
        at = message.time_utc
        if message.message in _DEPLOYED:
            opened.setdefault(_DEPLOYED[message.message], at)
        elif message.message in _ENDING and _ENDING[message.message] in opened:
            ending.add(_ENDING[message.message])
        elif message.message == RC_SESSION_STARTED:
            close(Neutralisation.RED_FLAG, at)

        if message.flag == RC_FLAG_RED:
            for kind in _CAUTIONS:
                close(kind, at)
            opened.setdefault(Neutralisation.RED_FLAG, at)
        elif message.flag == RC_FLAG_CHEQUERED:
            for kind in _CAUTIONS:
                close(kind, at)
        elif message.scope == RC_TRACK_SCOPE and message.flag in RC_GREEN_FLAGS:
            for kind in list(ending):
                close(kind, at)

    if not messages.empty:
        last = messages["time_utc"].iloc[-1]
        for kind in list(opened):
            close(kind, last)
    return periods


def leader_lap(laps: pd.DataFrame, at: pd.Timestamp, first_lap: int = FIRST_RACE_LAP) -> int:
    """Lap the leader was on at a moment: the highest lap number already started.

    Args:
        laps: Laps of one race with ``lap`` and ``start_time_utc``.
        at: The moment, e.g. the start of a neutralisation period.
        first_lap: Returned when no lap has started yet (before the race start).
    """
    started = laps[laps["start_time_utc"] <= at]
    return int(started["lap"].max()) if not started.empty else first_lap


GREEN = "GREEN"
"""State of a lap that overlaps no neutralisation period."""
_PRECEDENCE = (
    Neutralisation.RED_FLAG,
    Neutralisation.SAFETY_CAR,
    Neutralisation.VIRTUAL_SAFETY_CAR,
)


def lap_states(laps: pd.DataFrame, periods_by_race: Mapping[int, list[Period]]) -> pd.Series:
    """Label every lap GREEN, SC, VSC or RED (the strongest period it overlaps).

    Laps without a start time or a lap time are labelled GREEN (they cannot be
    placed in time; other rules exclude them where it matters).
    """
    start = laps["start_time_utc"]
    end = start + pd.to_timedelta(laps["lap_time_s"], unit="s")
    states = pd.Series(GREEN, index=laps.index, dtype=object)
    for kind in reversed(_PRECEDENCE):  # weakest first, so stronger kinds overwrite
        for race_id, periods in periods_by_race.items():
            in_race = laps["race_id"] == race_id
            for period in (p for p in periods if p.kind == kind):
                overlaps = ((start < period.end) & (end > period.start)).fillna(False)
                states[in_race & overlaps] = kind.value
    return states


def flag_neutralised_laps(
    laps: pd.DataFrame, periods_by_race: Mapping[int, list[Period]]
) -> pd.Series:
    """Mark laps that overlap a neutralisation period of their race.

    A lap spans ``[start_time_utc, start_time_utc + lap_time_s]``. Laps without a
    start time or a lap time cannot be placed in time and are not flagged here
    (they are excluded by other clean-lap rules).

    Args:
        laps: Laps with ``race_id``, ``start_time_utc`` and ``lap_time_s``.
        periods_by_race: Periods of each race, keyed by ``race_id``.

    Returns:
        Boolean series aligned with ``laps``.
    """
    start = laps["start_time_utc"]
    end = start + pd.to_timedelta(laps["lap_time_s"], unit="s")
    flagged = pd.Series(False, index=laps.index)
    for race_id, periods in periods_by_race.items():
        in_race = laps["race_id"] == race_id
        for period in periods:
            overlaps = (start < period.end) & (end > period.start)
            flagged |= in_race & overlaps.fillna(False)
    return flagged

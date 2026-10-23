"""Pit lane passes behind the Safety Car.

Sometimes the Safety Car leads the field through the pit lane instead of along
the pit straight (race control: "SAFETY CAR THROUGH THE PIT LANE"; Austria and
São Paulo 2023, Qatar 2024, Australia and Canada 2025). Jolpica then records a
pit stop for every car on each such lap and OpenF1 opens a new stint, although
nobody changed tyres. Left alone, the passes become phantom pit stops in the
simulator's strategies and in the race report.

Rule: inside a pass window (from one lap before the message, for lapped cars,
to the end of the Safety Car period around it) a pit lane visit is a pass,
unless the compound changed or the visit took more than
``PIT_LANE_PASS_MARGIN_S`` longer than the window's median visit (a real stop).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from f1lab.config import (
    FIRST_RACE_LAP,
    PIT_LANE_PASS_LAP_SLACK,
    PIT_LANE_PASS_MARGIN_S,
    RC_PIT_LANE_PASS,
)
from f1lab.models.neutralisation import Neutralisation, neutralisation_periods


@dataclass(frozen=True)
class PassWindow:
    """Laps (inclusive, drivers' own lap numbers) in which pit lane visits may be passes."""

    first_lap: int
    last_lap: int

    def __contains__(self, lap: object) -> bool:
        """Whether a lap number falls inside the window."""
        return isinstance(lap, int | float) and self.first_lap <= lap <= self.last_lap


def pass_windows(messages: pd.DataFrame) -> list[PassWindow]:
    """Pass windows of one race.

    Args:
        messages: Race control messages of the race in chronological order
            (``time_utc``, ``lap``, ``flag``, ``scope``, ``message``).
    """
    calls = messages[messages["message"].fillna("").str.contains(RC_PIT_LANE_PASS, regex=False)]
    calls = calls.dropna(subset=["lap"])
    if calls.empty:
        return []
    periods = [
        period
        for period in neutralisation_periods(messages)
        if period.kind == Neutralisation.SAFETY_CAR
    ]
    windows = []
    for call in calls.itertuples(index=False):
        period = next((p for p in periods if p.start <= call.time_utc <= p.end), None)
        end = period.end if period else call.time_utc
        last_lap = messages.loc[messages["time_utc"] <= end, "lap"].max()
        first_lap = max(FIRST_RACE_LAP, int(call.lap) - PIT_LANE_PASS_LAP_SLACK)
        windows.append(PassWindow(first_lap, max(int(last_lap), int(call.lap))))
    return windows


def _usable(stints: pd.DataFrame) -> pd.DataFrame:
    """Stints with a lap range, in order (as ``strategy_from_stints`` reads them)."""
    ordered = stints.dropna(subset=["lap_start", "lap_end"]).sort_values(["driver_id", "stint"])
    return ordered[ordered["lap_end"] >= ordered["lap_start"]]


def _boundary_visits(stints: pd.DataFrame, visits: pd.DataFrame) -> list[object | None]:
    """Index of the recorded visit behind each boundary between one driver's stints.

    OpenF1 places the boundary differently from race to race (a stint ends on the
    in-lap or a lap before it, the next starts on it or a lap after), but the
    visit always lies between the end of one stint and the start of the next.
    Boundaries take the earliest visit in that range not taken yet, in order:
    first those where the compound changes (certainly a stop), then the rest, so
    that a duplicated one-lap stint cannot take the visit of a real tyre change.

    Args:
        stints: One driver's stints with a lap range, in order.
        visits: The same driver's recorded pit stops.

    Returns:
        One entry per boundary: the index of the visit in ``visits``, or None.
    """
    ends = stints["lap_end"].to_numpy()[:-1]
    starts = stints["lap_start"].to_numpy()[1:]
    compounds = stints["compound"].to_numpy()
    changes = compounds[:-1] != compounds[1:]
    order = [*np.flatnonzero(changes), *np.flatnonzero(~changes)]
    free = visits.sort_values("lap")
    found: list[object | None] = [None] * len(ends)
    for boundary in order:
        low, high = sorted((ends[boundary], starts[boundary]))
        candidates = free[free["lap"].between(low, high)]
        if not candidates.empty:
            found[boundary] = candidates.index[0]
            free = free.drop(index=candidates.index[0])
    return found


def _in_any(lap: int, windows: list[PassWindow]) -> bool:
    return any(lap in window for window in windows)


def pit_lane_passes(
    pit_stops: pd.DataFrame, stints: pd.DataFrame, windows: list[PassWindow]
) -> pd.Series:
    """Which recorded pit stops of one race were passes behind the Safety Car.

    Args:
        pit_stops: Jolpica pit stops (``driver_id``, ``lap``, ``duration_s``).
        stints: OpenF1 stints of the same race.
        windows: Pass windows of the race.

    Returns:
        Boolean series aligned with ``pit_stops``.
    """
    passes = pd.Series(False, index=pit_stops.index)
    if not windows or pit_stops.empty:
        return passes
    window_of = pit_stops["lap"].map(
        lambda lap: next((i for i, window in enumerate(windows) if lap in window), None)
    )
    inside = window_of.notna()
    durations = pit_stops["duration_s"]
    reference = durations[inside].groupby(window_of[inside]).median()
    short = durations <= window_of.map(reference) + PIT_LANE_PASS_MARGIN_S

    changed = pd.Series(False, index=pit_stops.index)
    for driver_id, group in _usable(stints).groupby("driver_id"):
        visits = pit_stops[pit_stops["driver_id"] == driver_id]
        compounds = group["compound"].tolist()
        for before, after, visit in zip(
            compounds[:-1], compounds[1:], _boundary_visits(group, visits), strict=True
        ):
            if before != after and visit is not None:
                changed[visit] = True
    return inside & short.fillna(False).astype(bool) & ~changed


def merge_pit_lane_passes(
    stints: pd.DataFrame, pit_stops: pd.DataFrame, windows: list[PassWindow]
) -> pd.DataFrame:
    """Stints of one race with the splits at pit lane passes merged into the stint before.

    A split is merged when the compound stays the same and the visit behind it
    was a pass (with no visit recorded: when the split lies in a pass window).
    Stints without a lap range are kept as they are.
    """
    if not windows:
        return stints
    passes = pit_lane_passes(pit_stops, stints, windows)
    usable = _usable(stints)
    merged: list[dict[str, object]] = []
    for driver_id, group in usable.groupby("driver_id", sort=False):
        visits = pit_stops[pit_stops["driver_id"] == driver_id]
        records = group.to_dict("records")
        rows = records[:1]
        for row, visit in zip(records[1:], _boundary_visits(group, visits), strict=True):
            is_pass = (
                bool(passes[visit]) if visit is not None else _in_any(row["lap_start"], windows)
            )
            if row["compound"] == rows[-1]["compound"] and is_pass:
                rows[-1]["lap_end"] = row["lap_end"]
                continue
            rows.append(row)
        merged.extend(rows)
    result = pd.DataFrame(merged, columns=stints.columns)
    rest = stints.drop(index=usable.index)
    return result if rest.empty else pd.concat([result, rest], ignore_index=True)

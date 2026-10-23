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


def _visit_lap(visit_laps: set[int], boundary: int) -> int | None:
    """Visit behind a stint boundary: OpenF1 ends a stint on the in-lap or a lap before it."""
    for lap in (boundary, boundary + 1):
        if lap in visit_laps:
            return lap
    return None


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
        visit_laps = {int(lap) for lap in visits["lap"]}
        compounds = group["compound"].tolist()
        for before, after, boundary in zip(
            compounds, compounds[1:], group["lap_end"].iloc[:-1], strict=False
        ):
            lap = _visit_lap(visit_laps, int(boundary))
            if before != after and lap is not None:
                changed[visits.index[visits["lap"] == lap]] = True
    return inside & short.fillna(False).astype(bool) & ~changed


def merge_pit_lane_passes(
    stints: pd.DataFrame, pit_stops: pd.DataFrame, windows: list[PassWindow]
) -> pd.DataFrame:
    """Stints of one race with the splits at pit lane passes merged into the stint before.

    A split is merged when the compound stays the same, the boundary lies in a
    pass window and the visit behind it (if Jolpica recorded one) was a pass.
    Stints without a lap range are kept as they are.
    """
    if not windows:
        return stints
    passes = pit_lane_passes(pit_stops, stints, windows)
    usable = _usable(stints)
    merged: list[dict[str, object]] = []
    for driver_id, group in usable.groupby("driver_id", sort=False):
        visits = pit_stops[pit_stops["driver_id"] == driver_id]
        visit_laps = {int(lap) for lap in visits["lap"]}
        real_laps = {int(lap) for lap in visits.loc[~passes[visits.index], "lap"]}
        rows: list[dict[str, object]] = []
        for row in group.to_dict("records"):
            if rows and row["compound"] == rows[-1]["compound"]:
                boundary = int(rows[-1]["lap_end"])
                lap = _visit_lap(visit_laps, boundary)
                if _in_any(boundary, windows) and (lap is None or lap not in real_laps):
                    rows[-1]["lap_end"] = row["lap_end"]
                    continue
            rows.append(row)
        merged.extend(rows)
    result = pd.DataFrame(merged, columns=stints.columns)
    rest = stints.drop(index=usable.index)
    return result if rest.empty else pd.concat([result, rest], ignore_index=True)

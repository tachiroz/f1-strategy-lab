"""Race strategies: a starting tyre plus a list of pit stops (lap, new compound).

Text notation, used by the CLI and in reports::

    M-18-H          start on new mediums, pit at the end of lap 18 for hards
    S3-15-H-38-M    start on softs 3 laps old, stop on laps 15 and 38

A stop "on lap L" means the car pits at the end of lap L (L is the in-lap),
the same convention as the Jolpica pit stop data.
"""

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from f1lab.config import COMPOUND_CODES, MIN_DRY_COMPOUNDS, RED_FLAG_STOP_S

_NOTATION = re.compile(r"^([A-Z])(\d*)((?:-\d+-[A-Z])*)$")
_LETTER_BY_COMPOUND = {compound: letter for letter, compound in COMPOUND_CODES.items()}


class StrategyError(ValueError):
    """A strategy is malformed or breaks the sporting rules."""


@dataclass(frozen=True)
class Stop:
    """A pit stop at the end of ``lap`` onto ``compound``.

    ``free`` marks a tyre change that costs no time (fitted during a red flag).
    """

    lap: int
    compound: str
    free: bool = False


@dataclass(frozen=True)
class Strategy:
    """Starting tyre and the planned pit stops."""

    start_compound: str
    stops: tuple[Stop, ...] = ()
    start_age: int = 0
    label: str = field(default="", compare=False)

    @property
    def compounds(self) -> list[str]:
        """Compounds in the order they are used."""
        return [self.start_compound, *(stop.compound for stop in self.stops)]

    def notation(self) -> str:
        """Return the text notation of the strategy."""
        age = str(self.start_age) if self.start_age else ""
        parts = [f"{_LETTER_BY_COMPOUND.get(self.start_compound, '?')}{age}"]
        parts += [
            f"{stop.lap}-{_LETTER_BY_COMPOUND.get(stop.compound, '?')}" for stop in self.stops
        ]
        return "-".join(parts)


def parse_strategy(text: str) -> Strategy:
    """Parse the text notation (see the module docstring).

    Raises:
        StrategyError: If the text does not follow the notation or uses an unknown compound.
    """
    match = _NOTATION.match(text.strip().upper())
    if not match:
        raise StrategyError(f"Cannot parse strategy {text!r}; expected e.g. 'M-18-H' or 'S3-15-H'")
    start_letter, start_age, rest = match.groups()
    tokens = [token for token in rest.split("-") if token]
    letters = [start_letter, *tokens[1::2]]
    unknown = [letter for letter in letters if letter not in COMPOUND_CODES]
    if unknown:
        raise StrategyError(f"Unknown compound letter(s) {unknown} in {text!r}")
    stops = tuple(
        Stop(int(lap), COMPOUND_CODES[letter])
        for lap, letter in zip(tokens[0::2], tokens[1::2], strict=True)
    )
    return Strategy(COMPOUND_CODES[start_letter], stops, int(start_age or 0), label=text.strip())


def validate_strategy(strategy: Strategy, race_laps: int) -> None:
    """Check pit laps and the two-compound rule.

    Raises:
        StrategyError: If stops are not strictly increasing inside the race, or
            fewer than ``MIN_DRY_COMPOUNDS`` different compounds are used.
    """
    laps = [stop.lap for stop in strategy.stops]
    if any(lap < 1 or lap >= race_laps for lap in laps):
        raise StrategyError(f"Pit laps must be between 1 and {race_laps - 1}: {laps}")
    if laps != sorted(set(laps)):
        raise StrategyError(f"Pit laps must be strictly increasing: {laps}")
    if len(set(strategy.compounds)) < MIN_DRY_COMPOUNDS:
        raise StrategyError(
            f"A dry race needs at least {MIN_DRY_COMPOUNDS} compounds: {strategy.notation()}"
        )


def lap_plan(strategy: Strategy, race_laps: int) -> pd.DataFrame:
    """Expand a strategy into one row per lap.

    Returns:
        Columns ``lap`` (1..race_laps), ``compound``, ``tyre_age`` (laps already
        driven on the tyre at the start of the lap), ``pit`` (the car pits at
        the end of the lap) and ``free_pit`` (that stop costs no time).
    """
    laps = np.arange(1, race_laps + 1)
    compound = np.full(race_laps, strategy.start_compound, dtype=object)
    age = strategy.start_age + laps - 1
    pit = np.zeros(race_laps, dtype=bool)
    free = np.zeros(race_laps, dtype=bool)
    for stop in strategy.stops:
        after = laps > stop.lap
        compound[after] = stop.compound
        age[after] = laps[after] - stop.lap - 1
        pit[stop.lap - 1] = True
        free[stop.lap - 1] = stop.free
    return pd.DataFrame(
        {"lap": laps, "compound": compound, "tyre_age": age, "pit": pit, "free_pit": free}
    )


def strategy_stints(strategy: Strategy, race_laps: int) -> list[tuple[str, int, int]]:
    """Stints of a strategy as ``(compound, first lap, last lap)``, in race order."""
    bounds = [0, *(stop.lap for stop in strategy.stops), race_laps]
    return [
        (compound, first + 1, last)
        for compound, first, last in zip(strategy.compounds, bounds, bounds[1:], strict=False)
    ]


def strategy_from_stints(
    stints: pd.DataFrame, pit_stops: pd.DataFrame | None = None, label: str = ""
) -> Strategy:
    """Rebuild the strategy a driver actually ran from their stints.

    A stop is placed on the last lap of the previous stint (the in-lap). Zero-lap
    stints are skipped. If ``pit_stops`` shows a stop on that lap longer than
    ``RED_FLAG_STOP_S``, the change happened under red flag and is free.

    Args:
        stints: One driver's stints (``stint``, ``compound``, ``lap_start``,
            ``lap_end``, ``tyre_age_at_start``).
        pit_stops: The same driver's pit stops (``lap``, ``duration_s``), optional.
        label: Label of the resulting strategy.

    Raises:
        StrategyError: If the driver has no stint with a lap range.
    """
    ordered = stints.dropna(subset=["lap_start", "lap_end"]).sort_values("stint")
    ordered = ordered[ordered["lap_end"] >= ordered["lap_start"]]
    if ordered.empty:
        raise StrategyError("No stint with a lap range")
    red_flag_laps: set[int] = set()
    if pit_stops is not None and not pit_stops.empty:
        long = pit_stops["duration_s"].fillna(0) > RED_FLAG_STOP_S
        red_flag_laps = {int(lap) for lap in pit_stops.loc[long, "lap"]}
    first = ordered.iloc[0]
    stops = []
    previous_end = int(first["lap_end"])
    for row in ordered.iloc[1:].itertuples(index=False):
        # Whether OpenF1 starts the next stint after the in-lap or on it, the
        # in-lap is the last lap of the previous stint.
        stops.append(Stop(previous_end, str(row.compound), free=previous_end in red_flag_laps))
        previous_end = int(row.lap_end)
    start_age = 0 if pd.isna(first["tyre_age_at_start"]) else int(first["tyre_age_at_start"])
    return Strategy(str(first["compound"]), tuple(stops), start_age, label=label)

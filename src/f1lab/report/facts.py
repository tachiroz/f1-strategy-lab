"""Facts of one race for the automatic report.

The report never computes or invents anything: every number it prints is a field
of ``RaceFacts`` (``tests/test_report.py`` checks this). Facts come from the
database; the simulator's view is a separate, clearly labelled part
(``SimulationView``) that exists only for races the simulator can run.
"""

from collections import Counter
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Engine, text

from f1lab.config import (
    CALIBRATION_SEASONS,
    CONFIDENCE_LEVEL,
    DISQUALIFIED_STATUS,
    NON_STARTER_STATUSES,
    PIT_LANE_START_GRID,
    PODIUM_POSITIONS,
    POSITION_BAND,
    RED_FLAG_STOP_S,
    REPORT_MOVERS,
    REPORT_STRATEGY_CANDIDATES,
    REPORT_STRATEGY_DRIVERS,
    REPORT_STRATEGY_RUNS,
    REPORT_SURPRISES,
    WET_COMPOUNDS,
)
from f1lab.models.laps import load_race_control
from f1lab.models.neutralisation import Neutralisation, leader_lap, neutralisation_periods
from f1lab.sim.backtest import actual_results, score_summary
from f1lab.sim.engine import SimulationParams, simulate
from f1lab.sim.montecarlo import compare_strategies, neutralisation_shares, summarise
from f1lab.sim.setup import ACTUAL_LABEL, RaceSetup
from f1lab.sim.strategy import parse_strategy

MS_PER_S = 1000
S_PER_MIN = 60


class RaceNotFoundError(LookupError):
    """The race is not in the database."""


@dataclass(frozen=True)
class StintLine:
    """Laps on one set of tyres."""

    compound: str
    first_lap: int
    last_lap: int


@dataclass(frozen=True)
class DriverLine:
    """A starter's race in numbers."""

    driver_id: str
    code: str
    name: str
    team: str
    grid: int
    """Official grid position, 0 for a pit-lane start."""
    start_slot: int
    """Grid position with pit-lane starters counted behind the whole field."""
    position: int | None
    """Classified position; None if not classified."""
    status: str
    laps: int
    points: float
    stops: int
    """Pit stops, tyre changes under red flag not counted."""
    red_flag_changes: int
    """Tyre changes while the race was stopped (free, not pit stops)."""
    stints: tuple[StintLine, ...]
    gained: int | None
    """Places gained from the start slot (negative: lost); None if not classified."""

    @property
    def is_disqualified(self) -> bool:
        """Excluded from the result after finishing."""
        return self.status == DISQUALIFIED_STATUS

    @property
    def compounds(self) -> tuple[str, ...]:
        """Compounds in the order they were used."""
        return tuple(stint.compound for stint in self.stints)


@dataclass(frozen=True)
class NeutralisationLine:
    """A Safety Car, VSC or red flag period."""

    kind: str
    start_lap: int
    end_lap: int
    minutes: float


@dataclass(frozen=True)
class FastestLap:
    """The race's fastest lap."""

    driver_id: str
    name: str
    lap: int
    time_s: float


@dataclass(frozen=True)
class Weather:
    """Conditions averaged over the race."""

    air_c: float
    track_c: float
    rain: bool


@dataclass(frozen=True)
class StopCount:
    """How many classified finishers made this many pit stops."""

    stops: int
    drivers: int


@dataclass(frozen=True)
class Surprise:
    """A driver whose real finish fell outside the simulated band."""

    driver_id: str
    name: str
    position: int
    expected: float
    band_low: float
    band_high: float


@dataclass(frozen=True)
class StrategyIdea:
    """A field strategy that, by the model, would have served a driver better."""

    driver_id: str
    name: str
    actual: str
    better: str
    delta: float
    """Paired mean position difference (negative = better)."""
    delta_low: float
    delta_high: float


@dataclass(frozen=True)
class SimulationView:
    """What the simulator expected before the start, next to what happened."""

    runs: int
    in_sample: bool
    confidence: float
    band_share: float
    """Share of runs inside the band of ``Surprise`` (the 10-90% spread is 0.8)."""
    favourite_id: str
    favourite_name: str
    favourite_p_win: float
    winner_p_win: float
    winner_rank: int
    """The winner's place when drivers are ordered by simulated chance to win."""
    p_safety_car: float
    finishers: int
    mae: float
    grid_mae: float
    spearman: float | None
    grid_spearman: float | None
    over: tuple[Surprise, ...]
    under: tuple[Surprise, ...]
    strategy_runs: int
    strategy_drivers: int
    strategy_ideas: tuple[StrategyIdea, ...]


@dataclass(frozen=True)
class RaceFacts:
    """Everything the report may say about a race."""

    race_id: int
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str
    country: str | None
    date: str
    race_laps: int
    starters: int
    classified: int
    drivers: tuple[DriverLine, ...]
    """Starters in the official order of the result."""
    pole: DriverLine | None
    """The driver who started from grid position 1."""
    winner_margin_s: float | None
    fastest_lap: FastestLap | None
    neutralisations: tuple[NeutralisationLine, ...]
    weather: Weather | None
    wet: bool
    gainers: tuple[DriverLine, ...]
    losers: tuple[DriverLine, ...]
    retirements: tuple[DriverLine, ...]
    disqualified: tuple[DriverLine, ...]
    stop_counts: tuple[StopCount, ...]
    simulation: SimulationView | None
    simulation_reason: str | None
    """Why there is no simulator view (e.g. a wet race)."""
    podium_size: int = PODIUM_POSITIONS

    @property
    def finishers(self) -> tuple[DriverLine, ...]:
        """Classified drivers in finishing order."""
        return tuple(driver for driver in self.drivers if driver.position is not None)

    @property
    def podium(self) -> tuple[DriverLine, ...]:
        """The first classified finishers."""
        return self.finishers[: self.podium_size]

    @property
    def has_red_flag_changes(self) -> bool:
        """Some driver changed tyres while the race was stopped."""
        return any(line.red_flag_changes for line in self.drivers)

    @property
    def has_safety_car(self) -> bool:
        """A Safety Car (not only a VSC) came out during the race."""
        return any(line.kind == Neutralisation.SAFETY_CAR for line in self.neutralisations)

    def driver(self, driver_id: str) -> DriverLine:
        """Look up a starter by id."""
        return next(line for line in self.drivers if line.driver_id == driver_id)


def _read(engine: Engine, sql: str, race_id: int) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params={"race": race_id})


def _stints(frame: pd.DataFrame, race_laps: int) -> tuple[StintLine, ...]:
    """Stints with a lap range, in order; zero-lap and post-flag stints dropped."""
    usable = frame.dropna(subset=["lap_start", "lap_end"]).sort_values("stint")
    usable = usable[(usable["lap_end"] >= usable["lap_start"]) & (usable["lap_start"] <= race_laps)]
    return tuple(
        StintLine(str(row.compound), int(row.lap_start), min(int(row.lap_end), race_laps))
        for row in usable.itertuples(index=False)
    )


def driver_lines(
    results: pd.DataFrame, stints: pd.DataFrame, pit_stops: pd.DataFrame, race_laps: int
) -> tuple[DriverLine, ...]:
    """One line per starter, in the official order of the result."""
    starters = results[~results["status"].isin(NON_STARTER_STATUSES)].sort_values("position")
    back = len(starters)
    under_red = pit_stops["duration_s"].fillna(0) > RED_FLAG_STOP_S
    stop_counts = pit_stops[~under_red].groupby("driver_id").size()
    red_flag_counts = pit_stops[under_red].groupby("driver_id").size()
    lines = []
    for row in starters.itertuples(index=False):
        position = int(row.position) if str(row.position_text).isdigit() else None
        start = back if row.grid == PIT_LANE_START_GRID else int(row.grid)
        lines.append(
            DriverLine(
                driver_id=row.driver_id,
                code=row.code if isinstance(row.code, str) else row.driver_id[:3].upper(),
                name=f"{row.given_name} {row.family_name}",
                team=row.constructor_name,
                grid=int(row.grid),
                start_slot=start,
                position=position,
                status=row.status,
                laps=int(row.laps),
                points=float(row.points),
                stops=int(stop_counts.get(row.driver_id, 0)),
                red_flag_changes=int(red_flag_counts.get(row.driver_id, 0)),
                stints=_stints(stints[stints["driver_id"] == row.driver_id], race_laps),
                gained=None if position is None else start - position,
            )
        )
    return tuple(lines)


def neutralisation_lines(engine: Engine, race_id: int) -> tuple[NeutralisationLine, ...]:
    """SC, VSC and red flag periods with the leader's laps at their start and end."""
    periods = neutralisation_periods(load_race_control(engine, [race_id]))
    if not periods:
        return ()
    laps = _read(engine, "SELECT lap, start_time_utc FROM laps WHERE race_id = :race", race_id)
    laps["start_time_utc"] = pd.to_datetime(laps["start_time_utc"], utc=True, format="ISO8601")
    ordered = sorted(periods, key=lambda period: period.start)
    return tuple(
        NeutralisationLine(
            kind=period.kind.value,
            start_lap=leader_lap(laps, period.start),
            end_lap=leader_lap(laps, period.end),
            minutes=(period.end - period.start).total_seconds() / S_PER_MIN,
        )
        for period in ordered
    )


def _weather(engine: Engine, race_id: int) -> Weather | None:
    frame = _read(
        engine,
        "SELECT AVG(air_temp_c) AS air, AVG(track_temp_c) AS track, MAX(rainfall) AS rain "
        "FROM weather WHERE race_id = :race",
        race_id,
    )
    row = frame.iloc[0]
    if pd.isna(row["air"]):
        return None
    return Weather(air_c=float(row["air"]), track_c=float(row["track"]), rain=bool(row["rain"]))


def _margin(results: pd.DataFrame) -> float | None:
    """Gap from the winner to second place, in seconds (None when either time is missing)."""
    times = results.sort_values("position").head(2)["race_time_ms"]
    if len(times) < 2 or times.isna().any():
        return None
    return float(times.iloc[1] - times.iloc[0]) / MS_PER_S


def _fastest_lap(results: pd.DataFrame, lines: tuple[DriverLine, ...]) -> FastestLap | None:
    best = results[results["fastest_lap_rank"] == 1]
    if best.empty or pd.isna(best["fastest_lap"].iloc[0]):
        return None
    row = best.iloc[0]
    name = next(line.name for line in lines if line.driver_id == row["driver_id"])
    return FastestLap(
        driver_id=str(row["driver_id"]),
        name=name,
        lap=int(row["fastest_lap"]),
        time_s=float(row["fastest_lap_time_s"]),
    )


def _movers(lines: tuple[DriverLine, ...]) -> tuple[tuple[DriverLine, ...], tuple[DriverLine, ...]]:
    classified = [line for line in lines if line.gained is not None]
    gainers = sorted((line for line in classified if line.gained > 0), key=lambda x: -x.gained)
    losers = sorted((line for line in classified if line.gained < 0), key=lambda x: x.gained)
    return tuple(gainers[:REPORT_MOVERS]), tuple(losers[:REPORT_MOVERS])


def _stop_counts(lines: tuple[DriverLine, ...]) -> tuple[StopCount, ...]:
    counts = Counter(line.stops for line in lines if line.position is not None)
    return tuple(
        StopCount(stops, drivers)
        for stops, drivers in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )


def _surprises(
    summary: pd.DataFrame, lines: tuple[DriverLine, ...]
) -> tuple[tuple[Surprise, ...], tuple[Surprise, ...]]:
    over, under = [], []
    for line in lines:
        if line.position is None or line.driver_id not in summary.index:
            continue
        stats = summary.loc[line.driver_id]
        low, high = float(stats["finish_low"]), float(stats["finish_high"])
        surprise = Surprise(
            line.driver_id, line.name, line.position, float(stats["finish_mean"]), low, high
        )
        if line.position < low:
            over.append((low - line.position, surprise))
        elif line.position > high:
            under.append((line.position - high, surprise))
    return _largest(over), _largest(under)


def _largest(items: list[tuple[float, Surprise]]) -> tuple[Surprise, ...]:
    """The ``REPORT_SURPRISES`` surprises with the largest gap to the band."""
    ranked = sorted(items, key=lambda item: -item[0])[:REPORT_SURPRISES]
    return tuple(surprise for _, surprise in ranked)


def strategy_ideas(
    setup: RaceSetup, lines: tuple[DriverLine, ...], params: SimulationParams
) -> tuple[StrategyIdea, ...]:
    """For each podium finisher, the best of the field's most common strategies, if clearly better.

    "Clearly" means the whole confidence interval of the paired position
    difference is below zero.
    """
    field_plans = Counter(
        plan.notation() for plan in setup.strategies.values() if plan.label == ACTUAL_LABEL
    )
    ideas = []
    podium = [line for line in lines if line.position is not None][:REPORT_STRATEGY_DRIVERS]
    for line in podium:
        if line.driver_id not in setup.drivers:
            continue
        own = setup.strategies[line.driver_id]
        candidates = [
            notation for notation, _ in field_plans.most_common() if notation != own.notation()
        ][:REPORT_STRATEGY_CANDIDATES]
        if not candidates:
            continue
        plans = [own, *(parse_strategy(notation) for notation in candidates)]
        table = compare_strategies(setup, line.driver_id, plans, params).iloc[1:]
        best = table.sort_values("delta_vs_first").iloc[0]
        if best["delta_high"] < 0:
            ideas.append(
                StrategyIdea(
                    driver_id=line.driver_id,
                    name=line.name,
                    actual=own.notation(),
                    better=str(best["notation"]),
                    delta=float(best["delta_vs_first"]),
                    delta_low=float(best["delta_low"]),
                    delta_high=float(best["delta_high"]),
                )
            )
    return tuple(ideas)


def simulation_view(
    engine: Engine,
    setup: RaceSetup,
    lines: tuple[DriverLine, ...],
    params: SimulationParams,
    strategy_params: SimulationParams,
    in_sample: bool,
) -> SimulationView:
    """Simulate the race as it was set up and compare with what happened."""
    result = simulate(setup, params)
    summary = summarise(result)
    actual = actual_results(engine, setup.race_id)
    score = score_summary(setup, summary, actual)
    finishers = [line for line in lines if line.position is not None]
    winner = finishers[0].driver_id
    by_chance = summary["p_win"].sort_values(ascending=False)
    over, under = _surprises(summary, lines)
    band_low, band_high = POSITION_BAND
    return SimulationView(
        runs=params.runs,
        in_sample=in_sample,
        confidence=CONFIDENCE_LEVEL,
        band_share=band_high - band_low,
        favourite_id=str(by_chance.index[0]),
        favourite_name=next(line.name for line in lines if line.driver_id == by_chance.index[0]),
        favourite_p_win=float(by_chance.iloc[0]),
        winner_p_win=float(summary.loc[winner, "p_win"]),
        winner_rank=int(list(by_chance.index).index(winner)) + 1,
        p_safety_car=neutralisation_shares(result.track_state)[0],
        finishers=len([line for line in finishers if line.driver_id in summary.index]),
        mae=score.mae,
        grid_mae=score.grid_mae,
        spearman=None if pd.isna(score.spearman) else score.spearman,
        grid_spearman=None if pd.isna(score.grid_spearman) else score.grid_spearman,
        over=over,
        under=under,
        strategy_runs=strategy_params.runs,
        strategy_drivers=REPORT_STRATEGY_DRIVERS,
        strategy_ideas=strategy_ideas(setup, lines, strategy_params),
    )


def race_facts(
    engine: Engine,
    race_id: int,
    setup: RaceSetup | str | None = None,
    params: SimulationParams | None = None,
    strategy_params: SimulationParams | None = None,
) -> RaceFacts:
    """Collect the facts of a race.

    Args:
        engine: Database engine.
        race_id: The race.
        setup: The simulator's setup of the race, or the reason it cannot be
            simulated, or None to leave the simulator out.
        params: Simulation parameters for the race (default: ``SimulationParams()``).
        strategy_params: Parameters of the strategy check (default runs:
            ``REPORT_STRATEGY_RUNS``).

    Raises:
        RaceNotFoundError: If the race is not in the database.
    """
    race = _read(engine, "SELECT * FROM races WHERE race_id = :race", race_id)
    if race.empty:
        raise RaceNotFoundError(f"Race {race_id} is not in the database")
    info = race.iloc[0]
    results = _read(
        engine,
        "SELECT res.*, d.code, d.given_name, d.family_name FROM results AS res "
        "JOIN drivers AS d ON d.driver_id = res.driver_id WHERE res.race_id = :race",
        race_id,
    )
    stints = _read(engine, "SELECT * FROM stints WHERE race_id = :race", race_id)
    pit_stops = _read(engine, "SELECT * FROM pit_stops WHERE race_id = :race", race_id)
    race_laps = int(results["laps"].max())
    lines = driver_lines(results, stints, pit_stops, race_laps)
    pole = next((line for line in lines if line.grid == 1), None)
    gainers, losers = _movers(lines)
    used = {compound for line in lines for compound in line.compounds}
    season = int(info["season"])
    simulation = (
        simulation_view(
            engine,
            setup,
            lines,
            params or SimulationParams(),
            strategy_params or SimulationParams(runs=REPORT_STRATEGY_RUNS),
            in_sample=season in CALIBRATION_SEASONS,
        )
        if isinstance(setup, RaceSetup)
        else None
    )
    return RaceFacts(
        race_id=race_id,
        season=season,
        round=int(info["round"]),
        race_name=str(info["race_name"]),
        circuit_id=str(info["circuit_id"]),
        circuit_name=str(info["circuit_name"]),
        country=None if pd.isna(info["country"]) else str(info["country"]),
        date=str(info["start_time_utc"])[:10],
        race_laps=race_laps,
        starters=len(lines),
        classified=sum(line.position is not None for line in lines),
        drivers=lines,
        pole=pole,
        winner_margin_s=_margin(results[results["position_text"].astype(str).str.isdigit()]),
        fastest_lap=_fastest_lap(results, lines),
        neutralisations=neutralisation_lines(engine, race_id),
        weather=_weather(engine, race_id),
        wet=bool(used & set(WET_COMPOUNDS)),
        gainers=gainers,
        losers=losers,
        retirements=tuple(
            line for line in lines if line.position is None and not line.is_disqualified
        ),
        disqualified=tuple(line for line in lines if line.is_disqualified),
        stop_counts=_stop_counts(lines),
        simulation=simulation,
        simulation_reason=setup if isinstance(setup, str) else None,
    )

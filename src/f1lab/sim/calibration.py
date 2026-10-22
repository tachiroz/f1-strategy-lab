"""Simulator parameters estimated from past races.

Everything the simulator draws at random comes from the data of the calibration
seasons (never from the race being simulated):

* race pace from qualifying: seconds per qualifying position and the leftover
  "form of the day" spread;
* time lost per grid slot on lap 1;
* pit stop time loss, per circuit, relative to the cars that did not pit, plus
  how much cheaper a stop is under SC and VSC;
* SC and VSC: chance on lap 1, hazard per lap afterwards (per circuit, shrunk to
  the all-circuit rate), and how many laps a period lasts;
* retirements: probability per car and when in the race they happen.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Engine, bindparam, text

from f1lab.config import (
    DISQUALIFIED_STATUS,
    DRY_COMPOUNDS,
    FINISHED_STATUSES,
    FIRST_RACE_LAP,
    MIN_CIRCUIT_PIT_STOPS,
    NON_STARTER_STATUSES,
    PIT_LOSS_PERCENTILES,
    SC_PRIOR_RACES,
)
from f1lab.models.degradation import CircuitModel, driver_levels, fit_circuits
from f1lab.models.filters import annotate_laps, clean_laps, rain_during_lap
from f1lab.models.laps import load_model_laps, load_race_control, load_rainfall
from f1lab.models.neutralisation import (
    GREEN,
    Neutralisation,
    Period,
    lap_states,
    neutralisation_periods,
)

SC = Neutralisation.SAFETY_CAR.value
VSC = Neutralisation.VIRTUAL_SAFETY_CAR.value


@dataclass(frozen=True)
class History:
    """Everything the calibration needs about the calibration seasons."""

    seasons: tuple[int, ...]
    laps: pd.DataFrame
    periods: dict[int, list[Period]]
    rainfall: pd.DataFrame
    results: pd.DataFrame
    qualifying: pd.DataFrame


@dataclass(frozen=True)
class NeutralisationStats:
    """How often and how long one kind of neutralisation happens."""

    lap1_probability: float
    hazard: dict[str, float]
    hazard_all: float
    lengths_laps: np.ndarray


@dataclass(frozen=True)
class Calibration:
    """Simulator parameters estimated from the calibration seasons."""

    seasons: tuple[int, ...]
    quali_s_per_position: float
    form_sd_s: float
    grid_slot_s: float
    pit_loss_s: dict[str, np.ndarray]
    pit_loss_all_s: np.ndarray
    sc_pit_ratio: float
    vsc_pit_ratio: float
    sc_lap1_probability: float
    vsc_lap1_probability: float
    sc_hazard: dict[str, float]
    vsc_hazard: dict[str, float]
    sc_hazard_all: float
    vsc_hazard_all: float
    sc_length_laps: np.ndarray
    vsc_length_laps: np.ndarray
    dnf_probability: float
    dnf_race_fraction: np.ndarray

    def pit_losses(self, circuit_id: str) -> np.ndarray:
        """Green-flag pit loss samples of a circuit (all circuits if it has too few)."""
        return self.pit_loss_s.get(circuit_id, self.pit_loss_all_s)

    def hazards(self, circuit_id: str) -> tuple[float, float]:
        """SC and VSC hazard per lap after lap 1 at a circuit."""
        return (
            self.sc_hazard.get(circuit_id, self.sc_hazard_all),
            self.vsc_hazard.get(circuit_id, self.vsc_hazard_all),
        )


def load_history(engine: Engine, seasons: Sequence[int]) -> History:
    """Load laps, neutralisation periods, rainfall, results and qualifying of the seasons."""
    laps = load_model_laps(engine, seasons)
    race_ids = laps["race_id"].unique().tolist()
    messages = load_race_control(engine, race_ids)
    periods = {
        int(race_id): neutralisation_periods(group)
        for race_id, group in messages.groupby("race_id")
    }
    params = {"seasons": list(seasons)}
    with engine.connect() as conn:
        results = pd.read_sql(
            text(
                "SELECT res.*, r.circuit_id, r.season FROM results AS res "
                "JOIN races AS r ON r.race_id = res.race_id WHERE r.season IN :seasons"
            ).bindparams(bindparam("seasons", expanding=True)),
            conn,
            params=params,
        )
        qualifying = pd.read_sql(
            text(
                "SELECT q.* FROM qualifying AS q JOIN races AS r ON r.race_id = q.race_id "
                "WHERE r.season IN :seasons"
            ).bindparams(bindparam("seasons", expanding=True)),
            conn,
            params=params,
        )
    rainfall = load_rainfall(engine, race_ids)
    return History(
        seasons=tuple(seasons),
        laps=annotate_laps(laps, messages, rainfall),
        periods=periods,
        rainfall=rainfall,
        results=results,
        qualifying=qualifying,
    )


def race_distance(results: pd.DataFrame) -> pd.Series:
    """Race distance in laps (the winner's lap count) per race."""
    return results.groupby("race_id")["laps"].max()


def estimate_quali_pace(
    clean: pd.DataFrame, models: dict[str, CircuitModel], qualifying: pd.DataFrame
) -> tuple[float, float]:
    """Relate qualifying position to race pace.

    For every race, drivers' race levels (from the tyre model) and qualifying
    positions are centred on the race median; a pooled linear fit gives seconds
    per position, and the residual spread is the "form of the day".

    Returns:
        ``(seconds per qualifying position, residual standard deviation)``.
    """
    pairs = []
    for (race_id, circuit_id), laps in clean.groupby(["race_id", "circuit_id"]):
        if circuit_id not in models:
            continue
        levels = driver_levels(models[str(circuit_id)], laps).droplevel(0)
        positions = qualifying[qualifying["race_id"] == race_id].set_index("driver_id")["position"]
        joined = pd.DataFrame({"level": levels, "position": positions}).dropna()
        if len(joined) < 2:
            continue
        pairs.append(joined - joined.median())
    data = pd.concat(pairs)
    slope, intercept = np.polyfit(data["position"], data["level"], 1)
    residual = data["level"] - (slope * data["position"] + intercept)
    return float(slope), float(residual.std())


def estimate_grid_slot(laps: pd.DataFrame, results: pd.DataFrame) -> float:
    """Seconds lost on lap 1 per grid position (green first laps, pit-lane starters excluded)."""
    first = laps[(laps["lap"] == FIRST_RACE_LAP) & laps["lap_time_s"].notna()]
    first = first[~first["neutralised"]].merge(
        results[["race_id", "driver_id", "grid"]], on=["race_id", "driver_id"]
    )
    first = first[first["grid"] > 0]
    relative = first["lap_time_s"] - first.groupby("race_id")["lap_time_s"].transform("min")
    slope, _ = np.polyfit(first["grid"], relative, 1)
    return float(slope)


def estimate_pit_losses(
    laps: pd.DataFrame, states: pd.Series, rain: pd.Series
) -> tuple[dict[str, np.ndarray], np.ndarray, float, float]:
    """Pit stop time loss relative to the cars that did not pit on the same laps.

    loss = (in-lap + out-lap of the pitting car) - median (same two laps) of the
    cars that did not pit. Only dry-compound stops count; green-flag losses
    (both laps green, no rain) form the samples, SC and VSC stops give the
    discount ratios.

    Returns:
        ``(samples per circuit, all samples, SC ratio, VSC ratio)``.
    """
    frame = laps.assign(state=states, rain=rain).set_index(["race_id", "driver_id", "lap"])
    following = frame[["lap_time_s", "is_pit_out_lap", "state", "rain"]].add_suffix("_next")
    following.index = following.index.set_levels(following.index.levels[2] - 1, level=2)
    pairs = frame.join(following, how="inner").reset_index()
    pairs["two_laps"] = pairs["lap_time_s"] + pairs["lap_time_s_next"]
    pairs = pairs[pairs["two_laps"].notna()]
    calm = ~pairs["is_pit_in_lap"] & ~pairs["is_pit_out_lap"] & ~pairs["is_pit_out_lap_next"]
    field = pairs[calm].groupby(["race_id", "lap"])["two_laps"].median().rename("field")
    stops = pairs[pairs["is_pit_in_lap"] & pairs["compound"].isin(DRY_COMPOUNDS)]
    stops = stops.join(field, on=["race_id", "lap"]).dropna(subset=["field"])
    stops = stops.assign(loss=stops["two_laps"] - stops["field"])

    green = stops[
        (stops["state"] == GREEN)
        & (stops["state_next"] == GREEN)
        & ~stops["rain"]
        & ~stops["rain_next"]
    ]
    low, high = np.percentile(green["loss"], PIT_LOSS_PERCENTILES)
    green = green[green["loss"].between(low, high)]
    per_circuit = {
        str(circuit): group["loss"].to_numpy()
        for circuit, group in green.groupby("circuit_id")
        if len(group) >= MIN_CIRCUIT_PIT_STOPS
    }
    green_median = green["loss"].median()

    def ratio(kind: str) -> float:
        under = stops[(stops["state"] == kind) | (stops["state_next"] == kind)]
        return float(under["loss"].median() / green_median) if len(under) else 1.0

    return per_circuit, green["loss"].to_numpy(), ratio(SC), ratio(VSC)


def _deployment_lap(laps: pd.DataFrame, race_id: int, start: pd.Timestamp) -> int:
    """Leader's lap when a period starts: the highest lap number already started."""
    started = laps[(laps["race_id"] == race_id) & (laps["start_time_utc"] <= start)]
    return int(started["lap"].max()) if not started.empty else FIRST_RACE_LAP


def estimate_neutralisations(
    laps: pd.DataFrame, periods: dict[int, list[Period]], results: pd.DataFrame
) -> dict[str, NeutralisationStats]:
    """SC/VSC frequencies and lengths.

    Lap-1 deployments get their own probability (start crashes); later ones a
    hazard per lap. Per-circuit hazards are shrunk towards the all-circuit rate
    with the weight of ``SC_PRIOR_RACES`` average races. Lengths are measured in
    laps of the race's median green lap time.
    """
    distance = race_distance(results)
    circuit_of = results.groupby("race_id")["circuit_id"].first()
    green_lap = laps[~laps["neutralised"]].groupby("race_id")["lap_time_s"].median()
    rows = []
    for race_id, race_periods in periods.items():
        if race_id not in distance.index:
            continue
        for period in race_periods:
            if period.kind == Neutralisation.RED_FLAG:
                continue
            seconds = (period.end - period.start).total_seconds()
            rows.append(
                {
                    "race_id": race_id,
                    "kind": period.kind.value,
                    "lap": _deployment_lap(laps, race_id, period.start),
                    "length": max(1, round(seconds / green_lap.get(race_id, np.nan)))
                    if race_id in green_lap.index
                    else 1,
                }
            )
    events = pd.DataFrame(rows, columns=["race_id", "kind", "lap", "length"])
    races = len(distance)
    later_laps = (distance - FIRST_RACE_LAP).clip(lower=0)
    out: dict[str, NeutralisationStats] = {}
    for kind in (SC, VSC):
        of_kind = events[events["kind"] == kind]
        on_first = of_kind["lap"] <= FIRST_RACE_LAP
        later = of_kind[~on_first]
        rate_all = len(later) / later_laps.sum()
        prior_laps = SC_PRIOR_RACES * later_laps.mean()
        per_circuit = {}
        for circuit_id, race_ids in circuit_of.groupby(circuit_of).groups.items():
            count = later["race_id"].isin(race_ids).sum()
            exposure = later_laps.loc[list(race_ids)].sum()
            per_circuit[str(circuit_id)] = float(
                (count + rate_all * prior_laps) / (exposure + prior_laps)
            )
        out[kind] = NeutralisationStats(
            lap1_probability=float(on_first.sum() / races),
            hazard=per_circuit,
            hazard_all=float(rate_all),
            lengths_laps=of_kind["length"].to_numpy(dtype=int),
        )
    return out


def estimate_retirements(results: pd.DataFrame) -> tuple[float, np.ndarray]:
    """Retirement probability per starting car and the race fraction completed when retiring."""
    distance = race_distance(results)
    starters = results[~results["status"].isin(NON_STARTER_STATUSES)]
    # A disqualified car finished on track: it counts as a starter that did not retire.
    finished = starters["status"].isin(FINISHED_STATUSES) | (
        starters["status"] == DISQUALIFIED_STATUS
    )
    retired = starters[~finished]
    fraction = (retired["laps"] / retired["race_id"].map(distance)).clip(0, 1)
    return float(len(retired) / len(starters)), fraction.to_numpy()


def calibrate(history: History) -> tuple[Calibration, dict[str, CircuitModel]]:
    """Estimate all simulator parameters from the calibration seasons.

    Returns:
        The calibration and the pooled tyre models of the same seasons.
    """
    clean = clean_laps(history.laps)
    models = fit_circuits(clean, pooled=True)
    slope, form_sd = estimate_quali_pace(clean, models, history.qualifying)
    states = lap_states(history.laps, history.periods)
    rain = rain_during_lap(history.laps, history.rainfall)
    per_circuit, all_losses, sc_ratio, vsc_ratio = estimate_pit_losses(history.laps, states, rain)
    neutral = estimate_neutralisations(history.laps, history.periods, history.results)
    dnf_probability, dnf_fraction = estimate_retirements(history.results)
    calibration = Calibration(
        seasons=history.seasons,
        quali_s_per_position=slope,
        form_sd_s=form_sd,
        grid_slot_s=estimate_grid_slot(history.laps, history.results),
        pit_loss_s=per_circuit,
        pit_loss_all_s=all_losses,
        sc_pit_ratio=sc_ratio,
        vsc_pit_ratio=vsc_ratio,
        sc_lap1_probability=neutral[SC].lap1_probability,
        vsc_lap1_probability=neutral[VSC].lap1_probability,
        sc_hazard=neutral[SC].hazard,
        vsc_hazard=neutral[VSC].hazard,
        sc_hazard_all=neutral[SC].hazard_all,
        vsc_hazard_all=neutral[VSC].hazard_all,
        sc_length_laps=neutral[SC].lengths_laps,
        vsc_length_laps=neutral[VSC].lengths_laps,
        dnf_probability=dnf_probability,
        dnf_race_fraction=dnf_fraction,
    )
    return calibration, models

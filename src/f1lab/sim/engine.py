"""Vectorised Monte Carlo race engine: N races at once, lap by lap, whole field.

Per lap and run, a car's lap time is

    tyre-model pace (fuel, compound, capped tyre age)
    + qualifying-based level + form of the day + lap noise
    + dirty-air loss (within DIRTY_AIR_GAP_S of the car ahead)
    + pit loss on its in-lap (cheaper under SC/VSC, free under red flag)

Cars cannot pass unless they are at least ``overtake_delta_s`` faster than the
car ahead on that lap; otherwise they cross the line ``follow_gap_s`` behind it.
On SC/VSC laps every car laps at the same pace (order kept, pits still happen);
when a Safety Car period ends the field is bunched to ``restart_gap_s``.
Retirements happen on laps drawn in advance.

Every random draw is made in the same order for any strategy (common random
numbers), so two strategies of one driver face the same Safety Cars,
retirements and noise and their difference is not lost in randomness.
"""

from dataclasses import dataclass

import numpy as np

from f1lab.config import (
    DIRTY_AIR_GAP_S,
    DIRTY_AIR_PENALTY_S,
    MIN_FOLLOW_GAP_S,
    OVERTAKE_DELTA_S,
    SC_RESTART_GAP_S,
    SIM_RUNS,
    SIM_SEED,
)
from f1lab.sim.setup import RaceSetup
from f1lab.sim.strategy import lap_plan, validate_strategy

GREEN, SAFETY_CAR, VIRTUAL_SAFETY_CAR = 0, 1, 2
RETIRED_TIME = np.inf


@dataclass(frozen=True)
class SimulationParams:
    """Run count, seed and the race-craft assumptions."""

    runs: int = SIM_RUNS
    seed: int = SIM_SEED
    overtake_delta_s: float = OVERTAKE_DELTA_S
    dirty_air_penalty_s: float = DIRTY_AIR_PENALTY_S
    dirty_air_gap_s: float = DIRTY_AIR_GAP_S
    follow_gap_s: float = MIN_FOLLOW_GAP_S
    restart_gap_s: float = SC_RESTART_GAP_S


@dataclass(frozen=True)
class SimulationResult:
    """Outcome of every run."""

    drivers: tuple[str, ...]
    positions: np.ndarray
    retired: np.ndarray
    total_time_s: np.ndarray
    track_state: np.ndarray

    @property
    def runs(self) -> int:
        """Number of simulated races."""
        return self.positions.shape[0]


def _pace_and_pits(setup: RaceSetup) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per driver and lap: tyre-model pace, pit flag and free-stop flag, shape (D, L)."""
    pace, pit, free = [], [], []
    for driver in setup.drivers:
        strategy = setup.strategies[driver]
        validate_strategy(strategy, setup.race_laps)
        plan = lap_plan(strategy, setup.race_laps)
        relative = setup.model.relative_pace(plan)
        if relative.isna().any():
            unknown = sorted(set(plan.loc[relative.isna(), "compound"]))
            raise ValueError(f"{driver}: no tyre model for {unknown} at {setup.circuit_id}")
        pace.append(relative.to_numpy(dtype=float))
        pit.append(plan["pit"].to_numpy())
        free.append(plan["free_pit"].to_numpy())
    return np.array(pace), np.array(pit), np.array(free)


def _track_states(setup: RaceSetup, runs: int, rng: np.random.Generator) -> np.ndarray:
    """Draw the SC/VSC state of every lap of every run, shape (N, L)."""
    states = np.zeros((runs, setup.race_laps), dtype=np.int8)
    remaining = np.zeros(runs, dtype=int)
    kind = np.zeros(runs, dtype=np.int8)
    for lap in range(setup.race_laps):
        first = lap == 0
        p_sc = setup.sc_lap1_probability if first else setup.sc_hazard
        p_vsc = setup.vsc_lap1_probability if first else setup.vsc_hazard
        draw = rng.random(runs)
        sc_length = rng.choice(setup.sc_lengths_laps, runs)
        vsc_length = rng.choice(setup.vsc_lengths_laps, runs)
        free = remaining <= 0
        start_sc = free & (draw < p_sc)
        start_vsc = free & ~start_sc & (draw < p_sc + p_vsc)
        kind = np.where(start_sc, SAFETY_CAR, np.where(start_vsc, VIRTUAL_SAFETY_CAR, kind))
        remaining = np.where(start_sc, sc_length, np.where(start_vsc, vsc_length, remaining))
        active = remaining > 0
        states[:, lap] = np.where(active, kind, GREEN)
        remaining = remaining - active
    return states


def _retirement_laps(setup: RaceSetup, runs: int, rng: np.random.Generator) -> np.ndarray:
    """Lap on which each car retires (0 = it does not), shape (N, D)."""
    shape = (runs, len(setup.drivers))
    retires = rng.random(shape) < setup.dnf_probability
    fraction = rng.choice(setup.dnf_race_fraction, shape)
    lap = np.clip(np.ceil(fraction * setup.race_laps), 1, setup.race_laps).astype(int)
    return np.where(retires, lap, 0)


def _hold_behind(
    proposed: np.ndarray, lap_time: np.ndarray, order: np.ndarray, params: SimulationParams
) -> np.ndarray:
    """Apply the overtaking rule front to back in the order of the previous lap."""
    times = np.take_along_axis(proposed, order, axis=1)
    laps = np.take_along_axis(lap_time, order, axis=1)
    for position in range(1, times.shape[1]):
        ahead, mine = times[:, position - 1], times[:, position]
        racing = np.isfinite(ahead) & np.isfinite(mine)
        too_close = mine < ahead + params.follow_gap_s
        too_slow = (laps[:, position - 1] - laps[:, position]) < params.overtake_delta_s
        times[:, position] = np.where(
            racing & too_close & too_slow, ahead + params.follow_gap_s, mine
        )
    result = np.empty_like(proposed)
    np.put_along_axis(result, order, times, axis=1)
    return result


def _bunch_up(times: np.ndarray, gap: float) -> np.ndarray:
    """Close every gap to ``gap`` seconds behind the car ahead, keeping the order."""
    order = np.argsort(times, axis=1)
    ordered = np.take_along_axis(times, order, axis=1)
    finite = np.isfinite(ordered)
    bunched = ordered[:, :1] + gap * np.arange(times.shape[1])
    result = np.empty_like(times)
    np.put_along_axis(result, order, np.where(finite, bunched, ordered), axis=1)
    return result


def simulate(setup: RaceSetup, params: SimulationParams | None = None) -> SimulationResult:
    """Simulate ``params.runs`` races of the setup.

    Returns:
        Finishing positions (1 = winner; retired cars behind every finisher,
        ordered by laps completed), retirements, total times and track states.
    """
    params = params or SimulationParams()
    rng = np.random.default_rng(params.seed)
    runs, drivers, laps = params.runs, len(setup.drivers), setup.race_laps
    pace, pit, free_pit = _pace_and_pits(setup)

    states = _track_states(setup, runs, rng)
    retire_lap = _retirement_laps(setup, runs, rng)
    form = rng.normal(0.0, setup.form_sd_s, (runs, drivers))
    level = setup.level_s[None, :] + form
    times = np.broadcast_to((setup.grid - 1) * setup.grid_slot_s, (runs, drivers)).astype(float)

    for lap in range(laps):
        noise = rng.normal(0.0, setup.lap_noise_sd_s, (runs, drivers))
        pit_loss = rng.choice(setup.pit_loss_samples_s, (runs, drivers))
        state = states[:, lap]
        green = state == GREEN

        order = np.argsort(times, axis=1)
        ordered = np.take_along_axis(times, order, axis=1)
        gap_ahead = np.empty_like(times)
        with np.errstate(invalid="ignore"):  # inf - inf behind retired cars: NaN, no penalty
            gaps = np.diff(ordered, axis=1, prepend=-np.inf)
        np.put_along_axis(gap_ahead, order, gaps, axis=1)
        dirty_air = (gap_ahead < params.dirty_air_gap_s) * params.dirty_air_penalty_s

        racing_lap = pace[None, :, lap] + level + noise + dirty_air
        common_lap = np.broadcast_to(pace[:, lap].mean() + setup.level_s.mean(), (runs, drivers))
        lap_time = np.where(green[:, None], racing_lap, common_lap)

        ratio = np.select(
            [state == SAFETY_CAR, state == VIRTUAL_SAFETY_CAR],
            [setup.sc_pit_ratio, setup.vsc_pit_ratio],
            1.0,
        )
        stopping = pit[None, :, lap] & ~free_pit[None, :, lap]
        lap_time = lap_time + stopping * pit_loss * ratio[:, None]

        proposed = times + lap_time
        held = _hold_behind(proposed, lap_time, order, params)
        proposed = np.where(green[:, None], held, proposed)

        sc_ends = (state == SAFETY_CAR) & (
            states[:, lap + 1] != SAFETY_CAR if lap + 1 < laps else True
        )
        proposed = np.where(sc_ends[:, None], _bunch_up(proposed, params.restart_gap_s), proposed)

        proposed[retire_lap == lap + 1] = RETIRED_TIME
        times = proposed

    retired = retire_lap > 0
    completed = np.where(retired, retire_lap - 1, laps)
    # Finishers by time; retired cars behind them, more laps completed first.
    key = np.where(retired, np.inf, times)
    order = np.lexsort((key, -completed, retired), axis=1)
    positions = np.empty_like(order)
    np.put_along_axis(positions, order, np.arange(1, drivers + 1)[None, :], axis=1)
    return SimulationResult(
        drivers=setup.drivers,
        positions=positions,
        retired=retired,
        total_time_s=np.where(retired, np.inf, times),
        track_state=states,
    )

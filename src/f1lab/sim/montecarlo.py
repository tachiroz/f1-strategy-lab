"""Turn simulated races into answers: positions, probabilities and confidence intervals.

Proportions (win, podium, points) get Wilson intervals; mean positions a
normal-approximation interval. Strategy comparisons also report the paired
difference to the first strategy: thanks to common random numbers every run of
one strategy has a twin run of the other with the same Safety Cars,
retirements and noise, so the difference is far more precise than the
difference of two independent means.

For the dashboard: position histograms, the share of runs with a Safety Car
and the sensitivity of a strategy to how often Safety Cars come out.
"""

import warnings
from collections.abc import Sequence

import numpy as np
import pandas as pd

from f1lab.config import PODIUM_POSITIONS, POINTS_POSITIONS, POSITION_BAND
from f1lab.models.degradation import Z_SCORE
from f1lab.sim.engine import (
    SAFETY_CAR,
    VIRTUAL_SAFETY_CAR,
    SimulationParams,
    SimulationResult,
    simulate,
)
from f1lab.sim.setup import RaceSetup
from f1lab.sim.strategy import Strategy


def wilson_interval(successes: np.ndarray, trials: int) -> tuple[np.ndarray, np.ndarray]:
    """Wilson score interval of a proportion (works at 0 and 1, unlike p +- z*se)."""
    share = np.asarray(successes, dtype=float) / trials
    z2 = Z_SCORE**2
    centre = (share + z2 / (2 * trials)) / (1 + z2 / trials)
    half = (
        Z_SCORE * np.sqrt(share * (1 - share) / trials + z2 / (4 * trials**2)) / (1 + z2 / trials)
    )
    return centre - half, centre + half


def mean_interval(values: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean and its normal-approximation confidence interval along an axis."""
    mean = values.mean(axis=axis)
    half = Z_SCORE * values.std(axis=axis, ddof=1) / np.sqrt(values.shape[axis])
    return mean, mean - half, mean + half


def position_stats(positions: np.ndarray, retired: np.ndarray) -> dict[str, np.ndarray]:
    """Statistics of finishing positions; arrays have one value per column (driver)."""
    runs = positions.shape[0]
    mean, low, high = mean_interval(positions.astype(float))
    stats = {"mean_position": mean, "mean_low": low, "mean_high": high}
    stats["median_position"] = np.median(positions, axis=0)
    low_q, high_q = POSITION_BAND
    stats["position_low"] = np.quantile(positions, low_q, axis=0)
    stats["position_high"] = np.quantile(positions, high_q, axis=0)
    for name, limit in (("win", 1), ("podium", PODIUM_POSITIONS), ("points", POINTS_POSITIONS)):
        hits = (positions <= limit).sum(axis=0)
        stats[f"p_{name}"] = hits / runs
        stats[f"p_{name}_low"], stats[f"p_{name}_high"] = wilson_interval(hits, runs)
    stats["p_retire"] = retired.mean(axis=0)
    # Conditional on finishing: the fair prediction for a driver who is classified.
    finished = np.where(retired, np.nan, positions.astype(float))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a driver retiring in every run
        stats["finish_mean"] = np.nanmean(finished, axis=0)
        stats["finish_low"] = np.nanquantile(finished, low_q, axis=0)
        stats["finish_high"] = np.nanquantile(finished, high_q, axis=0)
    return stats


def position_histogram(positions: np.ndarray, retired: np.ndarray, field_size: int) -> np.ndarray:
    """Share of runs ending in each position, with retirements in an extra last column.

    Args:
        positions: Finishing positions, shape (runs, drivers).
        retired: Retirement flags, same shape.
        field_size: Cars in the race, i.e. positions 1..field_size.

    Returns:
        Shape (drivers, field_size + 1): column ``k - 1`` is the share of runs in
        which the driver is classified k-th, the last column the share of
        retirements. Every row sums to 1.
    """
    runs, drivers = positions.shape
    shares = np.zeros((drivers, field_size + 1))
    for column in range(drivers):
        finished = positions[~retired[:, column], column]
        counts = np.bincount(finished - 1, minlength=field_size)[:field_size]
        shares[column, :field_size] = counts / runs
        shares[column, field_size] = retired[:, column].mean()
    return shares


def neutralisation_shares(track_state: np.ndarray) -> tuple[float, float]:
    """Share of runs with at least one Safety Car lap, and with at least one VSC lap."""
    return (
        float((track_state == SAFETY_CAR).any(axis=1).mean()),
        float((track_state == VIRTUAL_SAFETY_CAR).any(axis=1).mean()),
    )


def summarise(result: SimulationResult) -> pd.DataFrame:
    """One row per driver, best expected finish first."""
    table = pd.DataFrame(
        position_stats(result.positions, result.retired), index=list(result.drivers)
    )
    return table.rename_axis("driver_id").sort_values("mean_position")


def compare_strategies(
    setup: RaceSetup,
    driver_id: str,
    strategies: Sequence[Strategy],
    params: SimulationParams | None = None,
) -> pd.DataFrame:
    """Simulate a driver's alternative strategies against the same field.

    Args:
        setup: The race (other drivers keep their strategies).
        driver_id: The driver whose strategy changes.
        strategies: Strategies to compare; the first one is the reference.
        params: Simulation parameters (same seed for every strategy).

    Returns:
        One row per strategy with position statistics, ``histogram`` (see
        ``position_histogram``) and ``delta_vs_first`` (mean paired position
        difference, negative = better) with its interval.
    """
    params = params or SimulationParams()
    index = setup.drivers.index(driver_id)
    rows, reference = [], None
    for strategy in strategies:
        result = simulate(setup.with_strategy(driver_id, strategy), params)
        positions, retired = result.positions[:, index], result.retired[:, [index]]
        stats = position_stats(positions[:, None], retired)
        row = {"strategy": strategy.label or strategy.notation(), "notation": strategy.notation()}
        row |= {name: float(values[0]) for name, values in stats.items()}
        row["histogram"] = position_histogram(positions[:, None], retired, len(setup.drivers))[0]
        if reference is None:
            reference = positions
        difference = (positions - reference).astype(float)
        if np.allclose(difference, difference[0]):
            row |= {
                "delta_vs_first": difference[0],
                "delta_low": difference[0],
                "delta_high": difference[0],
            }
        else:
            delta, low, high = mean_interval(difference)
            row |= {"delta_vs_first": delta, "delta_low": low, "delta_high": high}
        rows.append(row)
    return pd.DataFrame(rows)


def sc_sensitivity(
    setup: RaceSetup,
    driver_id: str,
    strategies: Sequence[Strategy],
    scales: Sequence[float],
    params: SimulationParams | None = None,
) -> pd.DataFrame:
    """How a driver's strategies fare as Safety Cars become rarer or more frequent.

    Every SC and VSC probability of the race is multiplied by each scale
    (1 = the circuit's history). At one scale all strategies share the random
    numbers, so they face the same neutralisations.

    Returns:
        One row per scale and strategy: ``scale``, ``strategy``, ``notation``,
        ``p_safety_car`` (share of runs with a Safety Car), ``mean_position``
        with ``mean_low`` / ``mean_high``, ``p_podium`` and ``p_points``.
    """
    params = params or SimulationParams()
    index = setup.drivers.index(driver_id)
    rows = []
    for scale in scales:
        scaled = setup.with_neutralisation_scale(scale)
        for strategy in strategies:
            result = simulate(scaled.with_strategy(driver_id, strategy), params)
            stats = position_stats(result.positions[:, [index]], result.retired[:, [index]])
            row = {
                "scale": scale,
                "strategy": strategy.label or strategy.notation(),
                "notation": strategy.notation(),
                "p_safety_car": neutralisation_shares(result.track_state)[0],
            }
            for name in ("mean_position", "mean_low", "mean_high", "p_podium", "p_points"):
                row[name] = float(stats[name][0])
            rows.append(row)
    return pd.DataFrame(rows)

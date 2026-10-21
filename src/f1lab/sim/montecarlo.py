"""Turn simulated races into answers: positions, probabilities and confidence intervals.

Proportions (win, podium, points) get Wilson intervals; mean positions a
normal-approximation interval. Strategy comparisons also report the paired
difference to the first strategy: thanks to common random numbers every run of
one strategy has a twin run of the other with the same Safety Cars,
retirements and noise, so the difference is far more precise than the
difference of two independent means.
"""

from collections.abc import Sequence

import numpy as np
import pandas as pd

from f1lab.config import PODIUM_POSITIONS, POINTS_POSITIONS
from f1lab.models.degradation import Z_SCORE
from f1lab.sim.engine import SimulationParams, SimulationResult, simulate
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
    for name, limit in (("win", 1), ("podium", PODIUM_POSITIONS), ("points", POINTS_POSITIONS)):
        hits = (positions <= limit).sum(axis=0)
        stats[f"p_{name}"] = hits / runs
        stats[f"p_{name}_low"], stats[f"p_{name}_high"] = wilson_interval(hits, runs)
    stats["p_retire"] = retired.mean(axis=0)
    return stats


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
        One row per strategy with position statistics and ``delta_vs_first``
        (mean paired position difference, negative = better) with its interval.
    """
    params = params or SimulationParams()
    index = setup.drivers.index(driver_id)
    rows, reference = [], None
    for strategy in strategies:
        result = simulate(setup.with_strategy(driver_id, strategy), params)
        positions = result.positions[:, index]
        stats = position_stats(positions[:, None], result.retired[:, index][:, None])
        row = {"strategy": strategy.label or strategy.notation(), "notation": strategy.notation()}
        row |= {name: float(values[0]) for name, values in stats.items()}
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

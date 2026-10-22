"""Static charts of the tyre model (style shared with ``f1lab.plotting``)."""

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from f1lab.config import SHOWCASE_MIN_DRIVER_LAPS
from f1lab.models.degradation import CircuitModel
from f1lab.models.evaluate import FINAL_VARIANT, Evaluation, Variant
from f1lab.plotting import (
    AXIS,
    BAR_HEIGHT,
    COMPOUND_STYLE,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    LINE_WIDTH,
    MARKER_RING,
    MARKER_SIZE,
    SERIES_BLUE,
    SERIES_ORANGE,
    SURFACE,
    THIN_SPACE,
    VALUE_FORMAT,
    legend,
    new_figure,
    save,
)


def _compound_handle(compound: str) -> Line2D:
    colour, marker = COMPOUND_STYLE[compound]
    return Line2D(
        [], [], color=colour, marker=marker, linestyle="", markersize=MARKER_SIZE, label=compound
    )


def _with_gaps(laps: pd.Series, values: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Insert NaN where laps are not consecutive so a line does not bridge excluded laps."""
    x, y = laps.to_numpy(dtype=float), values.to_numpy(dtype=float)
    breaks = np.where(np.diff(x) > 1)[0] + 1
    return np.insert(x, breaks, np.nan), np.insert(y, breaks, np.nan)


def pick_showcase(evaluation: Evaluation, count: int = 3) -> list[tuple[int, str]]:
    """Pick test races spanning best, median and worst fit, with their busiest driver.

    Only races whose busiest driver has at least ``SHOWCASE_MIN_DRIVER_LAPS``
    predicted laps qualify (if any do): a race with half its laps missing in the
    source, like Miami 2025, would otherwise look "best" for the wrong reason.

    Returns:
        ``(race_id, driver_id)`` pairs: races ordered by the full model's MAE, and
        for each the driver with the most predicted laps.
    """
    predictions = evaluation.predictions
    if predictions.empty:
        return []
    per_driver = predictions.groupby(["race_id", "driver_id"]).size()
    busiest = per_driver.groupby(level="race_id").max()
    eligible = busiest[busiest >= SHOWCASE_MIN_DRIVER_LAPS].index
    if eligible.empty:
        eligible = busiest.index
    errors = evaluation.errors()[FINAL_VARIANT.value]
    by_race = errors.groupby(predictions["race_id"]).mean().loc[eligible]
    ordered = by_race.sort_values().index.tolist()
    positions = np.linspace(0, len(ordered) - 1, num=min(count, len(ordered))).round().astype(int)
    picks = []
    for race_id in [ordered[i] for i in dict.fromkeys(positions)]:
        counts = per_driver.loc[race_id]
        driver = sorted(counts[counts == counts.max()].index)[0]
        picks.append((int(race_id), str(driver)))
    return picks


def plot_actual_vs_model(
    evaluation: Evaluation, showcase: Iterable[tuple[int, str]], path: Path
) -> Path:
    """Small multiples: actual clean laps (by compound) and the full model's prediction."""
    showcase = list(showcase)
    figure, axes = new_figure(3.6, ncols=max(len(showcase), 1))
    predictions = evaluation.predictions
    for ax, (race_id, driver_id) in zip(axes, showcase, strict=False):
        laps = predictions[
            (predictions["race_id"] == race_id) & (predictions["driver_id"] == driver_id)
        ].sort_values("lap")
        mae = (laps[FINAL_VARIANT.value] - laps["lap_time_s"]).abs().mean()
        x, y = _with_gaps(laps["lap"], laps[FINAL_VARIANT.value])
        ax.plot(x, y, color=SERIES_BLUE, linewidth=LINE_WIDTH, solid_capstyle="round", zorder=3)
        for compound, group in laps.groupby("compound"):
            colour, marker = COMPOUND_STYLE.get(str(compound), (INK_MUTED, "o"))
            ax.plot(
                group["lap"],
                group["lap_time_s"],
                linestyle="",
                marker=marker,
                markersize=MARKER_SIZE,
                color=colour,
                markeredgecolor=SURFACE,
                markeredgewidth=MARKER_RING,
                zorder=2,
            )
        race = laps.iloc[0]
        ax.set_title(
            f"{race['race_name']} {race['season']}\n{driver_id} · MAE {mae:.2f} с",
            fontsize=9.5,
            loc="left",
            color=INK,
        )
        ax.set_xlabel("Круг")
    axes[0].set_ylabel("Время круга, с")
    compounds = [c for c in COMPOUND_STYLE if c in set(predictions["compound"])]
    handles = [_compound_handle(c) for c in compounds]
    handles.append(Line2D([], [], color=SERIES_BLUE, linewidth=LINE_WIDTH, label="модель"))
    legend(axes[-1], handles, loc="upper right")
    figure.suptitle(
        "Факт против модели на отложенных гонках 2025: лучшая, средняя и худшая трасса",
        color=INK,
        fontsize=11,
        x=0.01,
        ha="left",
    )
    figure.tight_layout()
    return save(figure, path)


def plot_mae_overall(evaluation: Evaluation, path: Path) -> Path:
    """Horizontal bars of overall MAE; the full model highlighted, baselines grey."""
    mae = evaluation.mae()["mae_s"]
    labels = [variant.value for variant in reversed(Variant)]
    values = [mae[label] for label in labels]
    colours = [SERIES_BLUE if label == FINAL_VARIANT.value else INK_MUTED for label in labels]
    figure, (ax,) = new_figure(2.4)
    ax.barh(labels, values, color=colours, height=BAR_HEIGHT)
    for y, value in enumerate(values):
        ax.text(value, y, "  " + VALUE_FORMAT.format(value), va="center", color=INK, fontsize=9)
    ax.set_xlim(0, max(values) * 1.25)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", colors=INK_SECONDARY)
    ax.set_xlabel("MAE времени круга, с (меньше — лучше)")
    test_laps = f"{len(evaluation.predictions):,}".replace(",", THIN_SPACE)
    ax.set_title(
        f"Ошибка на {', '.join(map(str, evaluation.test_seasons))} "
        f"(обучение {'–'.join(map(str, evaluation.train_seasons))}), "
        f"кругов в тесте: {test_laps}",
        fontsize=10.5,
        loc="left",
        color=INK,
    )
    figure.tight_layout()
    return save(figure, path)


def plot_mae_by_circuit(evaluation: Evaluation, path: Path) -> Path:
    """Dumbbell per circuit: model without degradation vs the full model."""
    mae = evaluation.mae(by="circuit_id")
    mae = mae.sort_values(FINAL_VARIANT.value, ascending=False)
    y = np.arange(len(mae))
    figure, (ax,) = new_figure(0.28 * len(mae) + 1.2)
    without = mae[Variant.NO_DEGRADATION.value].to_numpy()
    full = mae[FINAL_VARIANT.value].to_numpy()
    ax.hlines(y, np.minimum(without, full), np.maximum(without, full), color=AXIS, linewidth=2)
    for values, colour, label in (
        (without, SERIES_ORANGE, Variant.NO_DEGRADATION.value),
        (full, SERIES_BLUE, FINAL_VARIANT.value),
    ):
        ax.plot(
            values,
            y,
            linestyle="",
            marker="o",
            markersize=MARKER_SIZE + 1,
            color=colour,
            markeredgecolor=SURFACE,
            markeredgewidth=MARKER_RING,
            label=label,
            zorder=3,
        )
    ax.set_yticks(y, mae.index)
    ax.tick_params(axis="y", colors=INK_SECONDARY)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("MAE времени круга, с")
    ax.set_title(
        "Где деградация помогает, а где нет: MAE по трассам 2025",
        fontsize=10.5,
        loc="left",
        color=INK,
    )
    handles = [
        Line2D(
            [], [], color=colour, marker="o", linestyle="", markersize=MARKER_SIZE + 1, label=name
        )
        for colour, name in (
            (SERIES_ORANGE, Variant.NO_DEGRADATION.value),
            (SERIES_BLUE, FINAL_VARIANT.value),
        )
    ]
    legend(ax, handles, loc="upper right")
    figure.tight_layout()
    return save(figure, path)


def plot_degradation(models: Iterable[CircuitModel], path: Path) -> Path:
    """Small multiples per compound: degradation (s/lap) per circuit with confidence intervals."""
    rows = [
        (model.circuit_id, compound, estimate)
        for model in models
        for compound, estimate in model.degradation_s_per_lap.items()
    ]
    compounds = [c for c in COMPOUND_STYLE if any(r[1] == c for r in rows)]
    figure, axes = new_figure(
        0.24 * max(len(rows) // max(len(compounds), 1), 4) + 1.6, ncols=max(len(compounds), 1)
    )
    for ax, compound in zip(axes, compounds, strict=False):
        colour, marker = COMPOUND_STYLE[compound]
        items = sorted((r for r in rows if r[1] == compound), key=lambda r: r[2].value)
        y = np.arange(len(items))
        ax.hlines(
            y, [r[2].low for r in items], [r[2].high for r in items], color=INK_MUTED, linewidth=1
        )
        ax.plot(
            [r[2].value for r in items],
            y,
            linestyle="",
            marker=marker,
            markersize=MARKER_SIZE,
            color=colour,
            markeredgecolor=SURFACE,
            markeredgewidth=MARKER_RING,
        )
        ax.axvline(0, color=AXIS, linewidth=1)
        ax.set_yticks(y, [r[0] for r in items], fontsize=7.5)
        ax.tick_params(axis="y", colors=INK_SECONDARY)
        ax.grid(axis="y", visible=False)
        ax.set_title(compound, fontsize=10, loc="left", color=INK)
        ax.set_xlabel("Деградация, с/круг")
    figure.suptitle(
        "Деградация шин по трассам (2023–2025), точка — оценка, отрезок — 95% интервал",
        color=INK,
        fontsize=11,
        x=0.01,
        ha="left",
    )
    figure.tight_layout()
    return save(figure, path)

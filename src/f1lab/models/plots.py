"""Static charts of the tyre model (matplotlib, dark theme matching the web app).

Colours mirror the design tokens in ``web/src/index.css``. Compounds keep the
Pirelli convention (red / yellow / white): the palette passes the colour-vision
and contrast checks, but yellow and white sit above the usual lightness band and
white has no chroma, so every compound also gets its own marker shape.
Series that are not compounds use validated categorical slots (blue, orange).
"""

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from f1lab.config import SHOWCASE_MIN_DRIVER_LAPS
from f1lab.models.degradation import CircuitModel
from f1lab.models.evaluate import Evaluation, Variant

SURFACE = "#101319"
GRID = "#1f232b"
AXIS = "#2c3038"
INK = "#f4f5f8"
INK_SECONDARY = "#adb1b9"
INK_MUTED = "#82868f"
SERIES_BLUE = "#3987e5"
SERIES_ORANGE = "#d95926"
COMPOUND_STYLE = {
    "SOFT": ("#f72c2e", "o"),
    "MEDIUM": ("#fccf28", "s"),
    "HARD": ("#f0eeeb", "^"),
}
DPI = 160
FIGURE_WIDTH_IN = 11.0
LINE_WIDTH = 1.6
MARKER_SIZE = 5.0
MARKER_RING = 0.8
BAR_HEIGHT = 0.28
"""Share of the band a bar fills: keeps bars thin (about 24 px) with air between them."""
VALUE_FORMAT = "{:.3f} с"
THIN_SPACE = " "
"""Thousands separator in Russian typography (19 484)."""


def _style_axes(ax: Axes) -> None:
    """Recessive chrome: hairline solid grid, muted ticks, no top/right spines."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=8.5)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK)


def _new_figure(
    height_in: float, ncols: int = 1, sharey: bool = False
) -> tuple[Figure, list[Axes]]:
    """Create a dark figure with ``ncols`` styled axes."""
    figure = Figure(figsize=(FIGURE_WIDTH_IN, height_in), dpi=DPI, facecolor=SURFACE)
    axes = list(np.atleast_1d(figure.subplots(1, ncols, sharey=sharey)))
    for ax in axes:
        _style_axes(ax)
    return figure, axes


def _legend(ax: Axes, handles: list[Line2D], **kwargs: object) -> None:
    """Legend with text in ink colours (never the series colour)."""
    legend = ax.legend(handles=handles, frameon=False, fontsize=8.5, **kwargs)
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)


def _compound_handle(compound: str) -> Line2D:
    colour, marker = COMPOUND_STYLE[compound]
    return Line2D(
        [], [], color=colour, marker=marker, linestyle="", markersize=MARKER_SIZE, label=compound
    )


def _save(figure: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    return path


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
    errors = evaluation.errors()[Variant.FULL.value]
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
    figure, axes = _new_figure(3.6, ncols=max(len(showcase), 1))
    predictions = evaluation.predictions
    for ax, (race_id, driver_id) in zip(axes, showcase, strict=False):
        laps = predictions[
            (predictions["race_id"] == race_id) & (predictions["driver_id"] == driver_id)
        ].sort_values("lap")
        mae = (laps[Variant.FULL.value] - laps["lap_time_s"]).abs().mean()
        x, y = _with_gaps(laps["lap"], laps[Variant.FULL.value])
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
    _legend(axes[-1], handles, loc="upper right")
    figure.suptitle(
        "Факт против модели на отложенных гонках 2025: лучшая, средняя и худшая трасса",
        color=INK,
        fontsize=11,
        x=0.01,
        ha="left",
    )
    figure.tight_layout()
    return _save(figure, path)


def plot_mae_overall(evaluation: Evaluation, path: Path) -> Path:
    """Horizontal bars of overall MAE; the full model highlighted, baselines grey."""
    mae = evaluation.mae()["mae_s"]
    labels = [variant.value for variant in reversed(Variant)]
    values = [mae[label] for label in labels]
    colours = [SERIES_BLUE if label == Variant.FULL.value else INK_MUTED for label in labels]
    figure, (ax,) = _new_figure(2.4)
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
    return _save(figure, path)


def plot_mae_by_circuit(evaluation: Evaluation, path: Path) -> Path:
    """Dumbbell per circuit: model without degradation vs the full model."""
    mae = evaluation.mae(by="circuit_id")
    mae = mae.sort_values(Variant.FULL.value, ascending=False)
    y = np.arange(len(mae))
    figure, (ax,) = _new_figure(0.28 * len(mae) + 1.2)
    without = mae[Variant.NO_DEGRADATION.value].to_numpy()
    full = mae[Variant.FULL.value].to_numpy()
    ax.hlines(y, np.minimum(without, full), np.maximum(without, full), color=AXIS, linewidth=2)
    for values, colour, label in (
        (without, SERIES_ORANGE, Variant.NO_DEGRADATION.value),
        (full, SERIES_BLUE, Variant.FULL.value),
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
            (SERIES_BLUE, Variant.FULL.value),
        )
    ]
    _legend(ax, handles, loc="upper right")
    figure.tight_layout()
    return _save(figure, path)


def plot_degradation(models: Iterable[CircuitModel], path: Path) -> Path:
    """Small multiples per compound: degradation (s/lap) per circuit with confidence intervals."""
    rows = [
        (model.circuit_id, compound, estimate)
        for model in models
        for compound, estimate in model.degradation_s_per_lap.items()
    ]
    compounds = [c for c in COMPOUND_STYLE if any(r[1] == c for r in rows)]
    figure, axes = _new_figure(
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
    return _save(figure, path)

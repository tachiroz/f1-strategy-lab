"""Charts of the race simulator (style shared with ``f1lab.plotting``)."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from f1lab.plotting import (
    AXIS,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    MARKER_RING,
    MARKER_SIZE,
    SERIES_BLUE,
    SERIES_ORANGE,
    SURFACE,
    legend,
    new_figure,
    save,
)
from f1lab.sim.backtest import Backtest, RaceBacktest

BAND_WIDTH = 4.0
ROW_HEIGHT_IN = 0.24
ACTUAL_MARKER = "D"
RETIRED_MARKER = "x"
LEGEND_BAND = 0.05
"""Share of the figure height kept free below the panels for the legend."""
SHOWCASE_TITLE = "Симуляция против реальности (вне обучения): лучшая, средняя и худшая гонка"


def pick_showcase(result: Backtest, count: int = 3) -> list[RaceBacktest]:
    """Best, median and worst race by Spearman correlation (as many as requested)."""
    ordered = sorted(result.races, key=lambda race: race.spearman, reverse=True)
    if not ordered:
        return []
    positions = np.linspace(0, len(ordered) - 1, num=min(count, len(ordered))).round().astype(int)
    return [ordered[i] for i in dict.fromkeys(positions)]


def plot_backtest_races(
    races: Sequence[RaceBacktest], path: Path, title: str = SHOWCASE_TITLE
) -> Path:
    """Small multiples: simulated position band and mean vs the real finish, per driver."""
    rows = max((len(race.table) for race in races), default=1)
    figure, axes = new_figure(ROW_HEIGHT_IN * rows + 1.6, ncols=max(len(races), 1))
    for ax, race in zip(axes, races, strict=False):
        table = race.table.sort_values("position")
        y = np.arange(len(table))[::-1]
        ax.hlines(
            y,
            table["finish_low"],
            table["finish_high"],
            color=AXIS,
            linewidth=BAND_WIDTH,
            capstyle="round",
        )
        ax.plot(
            table["finish_mean"], y, "o", color=SERIES_BLUE, markersize=MARKER_SIZE,
            markeredgecolor=SURFACE, markeredgewidth=MARKER_RING, zorder=3,
        )  # fmt: skip
        classified = table["position_text"].astype(str).str.isdigit().to_numpy()
        ax.plot(
            table["position"][classified], y[classified], ACTUAL_MARKER, color=INK,
            markersize=MARKER_SIZE - 1, markeredgecolor=SURFACE, markeredgewidth=MARKER_RING,
            zorder=4,
        )  # fmt: skip
        ax.plot(
            table["position"][~classified], y[~classified], RETIRED_MARKER, color=INK_MUTED,
            markersize=MARKER_SIZE, zorder=4,
        )  # fmt: skip
        ax.set_yticks(y, table.index, fontsize=7.5)
        ax.tick_params(axis="y", colors=INK_SECONDARY)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0.5, len(table) + 0.5)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("Позиция")
        ax.set_title(
            f"{race.race_name}\nSpearman {race.spearman:.2f} (решётка {race.grid_spearman:.2f})",
            fontsize=9.5,
            loc="left",
            color=INK,
        )
    handles = [
        Line2D([], [], color=AXIS, linewidth=BAND_WIDTH, label="80% финишей в симуляции"),
        Line2D(
            [], [], color=SERIES_BLUE, marker="o", linestyle="", label="средняя позиция при финише"
        ),
        Line2D([], [], color=INK, marker=ACTUAL_MARKER, linestyle="", label="факт"),
        Line2D([], [], color=INK_MUTED, marker=RETIRED_MARKER, linestyle="", label="факт: сход"),
    ]
    box = figure.legend(
        handles=handles, loc="lower center", ncol=len(handles), frameon=False, fontsize=8.5
    )
    for text in box.get_texts():
        text.set_color(INK_SECONDARY)
    figure.suptitle(
        title,
        color=INK,
        fontsize=11,
        x=0.01,
        ha="left",
    )
    figure.tight_layout(rect=(0, LEGEND_BAND, 1, 1))
    return save(figure, path)


def plot_backtest_scores(result: Backtest, path: Path) -> Path:
    """Dumbbell per race: position error of the grid baseline vs the simulator."""
    table = result.summary().sort_values("mae", ascending=False)
    y = np.arange(len(table))
    figure, (ax,) = new_figure(ROW_HEIGHT_IN * len(table) + 1.2)
    low = np.minimum(table["mae"], table["grid_mae"])
    high = np.maximum(table["mae"], table["grid_mae"])
    ax.hlines(y, low, high, color=AXIS, linewidth=2)
    for column, colour in (("grid_mae", SERIES_ORANGE), ("mae", SERIES_BLUE)):
        ax.plot(
            table[column], y, "o", color=colour, markersize=MARKER_SIZE + 1,
            markeredgecolor=SURFACE, markeredgewidth=MARKER_RING, zorder=3,
        )  # fmt: skip
    ax.set_yticks(y, table["race"], fontsize=7.5)
    ax.tick_params(axis="y", colors=INK_SECONDARY)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Средняя ошибка позиции (MAE), позиций")
    ax.set_title(
        "Ошибка по гонкам: симулятор против стартовой решётки", fontsize=10.5, loc="left", color=INK
    )
    handles = [
        Line2D([], [], color=SERIES_ORANGE, marker="o", linestyle="", label="финиш = решётка"),
        Line2D([], [], color=SERIES_BLUE, marker="o", linestyle="", label="симулятор"),
    ]
    legend(ax, handles, loc="upper right")
    figure.tight_layout()
    return save(figure, path)


def plot_strategy_comparison(table: pd.DataFrame, title: str, path: Path) -> Path:
    """Mean position and P(podium)/P(points) with confidence intervals per strategy."""
    y = np.arange(len(table))[::-1]
    figure, (left, right) = new_figure(0.5 * len(table) + 1.6, ncols=2)
    left.hlines(y, table["mean_low"], table["mean_high"], color=INK_MUTED, linewidth=1.2)
    left.plot(
        table["mean_position"], y, "o", color=SERIES_BLUE, markersize=MARKER_SIZE + 1,
        markeredgecolor=SURFACE, markeredgewidth=MARKER_RING, zorder=3,
    )  # fmt: skip
    left.set_yticks(y, table["notation"])
    left.invert_xaxis()
    left.set_xlabel("Средняя позиция (95% интервал), правее лучше")
    for column, colour, offset in (
        ("p_podium", SERIES_BLUE, 0.12),
        ("p_points", SERIES_ORANGE, -0.12),
    ):
        right.hlines(
            y + offset,
            table[f"{column}_low"],
            table[f"{column}_high"],
            color=INK_MUTED,
            linewidth=1.2,
        )
        right.plot(
            table[column], y + offset, "o", color=colour, markersize=MARKER_SIZE + 1,
            markeredgecolor=SURFACE, markeredgewidth=MARKER_RING, zorder=3,
        )  # fmt: skip
    right.set_yticks(y, [""] * len(y))
    right.set_xlim(0, 1)
    right.set_xlabel("Вероятность (95% интервал)")
    for ax in (left, right):
        ax.tick_params(axis="y", colors=INK_SECONDARY)
        ax.grid(axis="y", visible=False)
    handles = [
        Line2D([], [], color=SERIES_BLUE, marker="o", linestyle="", label="P(подиум)"),
        Line2D([], [], color=SERIES_ORANGE, marker="o", linestyle="", label="P(очки)"),
    ]
    legend(right, handles, loc="lower left")  # probabilities sit to the right
    figure.suptitle(title, color=INK, fontsize=11, x=0.01, ha="left")
    figure.tight_layout()
    return save(figure, path)

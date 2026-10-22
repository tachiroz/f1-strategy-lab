"""Shared chart style: dark theme matching the web app (``web/src/index.css``).

Compounds keep the Pirelli convention (red / yellow / white): the palette passes
the colour-vision and contrast checks, but yellow and white sit above the usual
lightness band and white has no chroma, so every compound also gets its own
marker shape. Series that are not compounds use validated categorical slots
(blue, orange); text always uses the ink colours, never a series colour.
"""

from pathlib import Path

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

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


def style_axes(ax: Axes) -> None:
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


def new_figure(height_in: float, ncols: int = 1, sharey: bool = False) -> tuple[Figure, list[Axes]]:
    """Create a dark figure with ``ncols`` styled axes."""
    figure = Figure(figsize=(FIGURE_WIDTH_IN, height_in), dpi=DPI, facecolor=SURFACE)
    axes = list(np.atleast_1d(figure.subplots(1, ncols, sharey=sharey)))
    for ax in axes:
        style_axes(ax)
    return figure, axes


def legend(ax: Axes, handles: list[Line2D], **kwargs: object) -> None:
    """Legend with text in ink colours (never the series colour)."""
    box = ax.legend(handles=handles, frameon=False, fontsize=8.5, **kwargs)
    for text in box.get_texts():
        text.set_color(INK_SECONDARY)


def save(figure: Figure, path: Path) -> Path:
    """Write the figure as PNG on the dark surface, creating the directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    return path

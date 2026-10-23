"""Charts of the race report (style shared with ``f1lab.plotting``)."""

from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

from f1lab.plotting import (
    COMPOUND_STYLE,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    SURFACE,
    legend,
    new_figure,
    save,
)
from f1lab.report.facts import RaceFacts
from f1lab.report.text import COMPOUND_NAMES, neutralisation

ROW_HEIGHT_IN = 0.26
FRAME_HEIGHT_IN = 1.4
STINT_HEIGHT = 0.62
"""Share of a driver's row the stint bars fill; the rest is air between drivers."""
SEGMENT_GAP_PT = 1.5
"""Surface-coloured edge that separates touching stints."""
UNKNOWN_COMPOUND_COLOUR = INK_MUTED
NEUTRALISATION_ALPHA = {"SC": 0.16, "VSC": 0.08, "RED": 0.24}
LABEL_OFFSET = 0.6


def plot_stints(facts: RaceFacts, path: Path) -> Path:
    """Stints of every starter by lap, winner on top; SC, VSC and red flag periods shaded."""
    rows = len(facts.drivers)
    figure, (ax,) = new_figure(ROW_HEIGHT_IN * rows + FRAME_HEIGHT_IN)
    y = np.arange(rows)[::-1]
    for row, driver in zip(y, facts.drivers, strict=True):
        for stint in driver.stints:
            colour = COMPOUND_STYLE.get(stint.compound, (UNKNOWN_COMPOUND_COLOUR, "o"))[0]
            ax.barh(
                row,
                stint.last_lap - stint.first_lap + 1,
                left=stint.first_lap - 1,
                height=STINT_HEIGHT,
                color=colour,
                edgecolor=SURFACE,
                linewidth=SEGMENT_GAP_PT,
            )
    for period in facts.neutralisations:
        ax.axvspan(
            period.start_lap - 1,
            period.end_lap,
            color=INK,
            alpha=NEUTRALISATION_ALPHA.get(period.kind, NEUTRALISATION_ALPHA["SC"]),
            linewidth=0,
            zorder=0,
        )
        ax.text(
            period.start_lap - 1 + LABEL_OFFSET,
            rows - 1 + LABEL_OFFSET,
            period.kind,
            color=INK_SECONDARY,
            fontsize=7.5,
            va="bottom",
        )
    labels = [f"{driver.position or '—':>2}  {driver.code}" for driver in facts.drivers]
    ax.set_yticks(y, labels, fontsize=7.5, family="monospace")
    ax.tick_params(axis="y", colors=INK_SECONDARY, length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, facts.race_laps)
    ax.set_ylim(-1, rows + 0.5)
    ax.set_xlabel("Круг")
    ax.set_title(
        f"{facts.race_name} {facts.season}: шины по стинтам",
        fontsize=10,
        loc="left",
        color=INK,
    )
    used = [c for c in COMPOUND_STYLE if any(c in d.compounds for d in facts.drivers)]
    handles = [Patch(color=COMPOUND_STYLE[c][0], label=COMPOUND_NAMES[c]) for c in used]
    kinds = list(dict.fromkeys(period.kind for period in facts.neutralisations))
    handles += [
        Patch(color=INK, alpha=NEUTRALISATION_ALPHA[kind], label=f"{kind}: {neutralisation(kind)}")
        for kind in kinds
    ]
    legend(ax, handles, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=len(handles))
    figure.tight_layout()
    return save(figure, path)

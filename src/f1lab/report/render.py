"""Render race facts into a Markdown report with the Jinja2 template."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from f1lab.config import REPO_URL
from f1lab.report import text
from f1lab.report.facts import RaceFacts

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE = "race.md.j2"
MAX_DIGITS = 3

FILTERS: dict[str, Callable[..., str]] = {
    "num": text.number,
    "signed": text.signed,
    "unsigned": text.unsigned,
    "pct": text.percent,
    "laptime": text.lap_time,
    "longdate": text.long_date,
    "plural": text.plural,
    "compounds": text.compounds,
    "kind": text.neutralisation,
    "status": text.status,
    "reason": text.setup_reason,
}

NUMBER_FORMATS: tuple[Callable[[float], str], ...] = (
    *(lambda value, d=digits: text.number(value, d) for digits in range(MAX_DIGITS + 1)),
    *(lambda value, d=digits: text.signed(value, d) for digits in range(MAX_DIGITS + 1)),
    *(lambda value, d=digits: text.unsigned(value, d) for digits in range(MAX_DIGITS + 1)),
    text.percent,
    text.lap_time,
)
"""Every way the template can print a number (the provenance test enumerates them)."""


@dataclass(frozen=True)
class ReportCharts:
    """Chart files next to the report, as paths relative to it."""

    stints: str
    outcome: str | None = None


def report_stem(season: int, round_number: int, circuit_id: str) -> str:
    """File name of a report without extension, e.g. ``2025-04-bahrain``."""
    return f"{season}-{round_number:02d}-{circuit_id}"


def environment() -> Environment:
    """Jinja environment with the report filters; undefined names fail loudly."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,  # Markdown, not HTML
    )
    env.filters.update(FILTERS)
    return env


def render_report(facts: RaceFacts, charts: ReportCharts | None = None) -> str:
    """Markdown report of a race; with ``charts`` it links the chart images."""
    template = environment().get_template(TEMPLATE)
    return template.render(f=facts, charts=charts, repo_url=REPO_URL)

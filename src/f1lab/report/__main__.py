"""Command line entry point: ``python -m f1lab.report``.

Writes the automatic report of a race as Markdown with its charts (PNG) next to it.

Examples:
    python -m f1lab.report --season 2025 --round 4
    python -m f1lab.report --season 2024 --round 21 --out reports
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from f1lab.config import (
    CALIBRATION_SEASONS,
    REPORT_DIR,
    REPORT_STRATEGY_RUNS,
    SIM_RUNS,
    get_db_path,
)
from f1lab.console import tolerate_console_encoding
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.ingest.transform import race_id_for
from f1lab.report.facts import RaceNotFoundError, race_facts
from f1lab.report.plots import plot_stints
from f1lab.report.render import ReportCharts, render_report, report_stem
from f1lab.sim.backtest import actual_results, score_race
from f1lab.sim.calibration import calibrate, load_history
from f1lab.sim.engine import SimulationParams
from f1lab.sim.plots import plot_backtest_races
from f1lab.sim.setup import RaceSetup, SetupError, race_setup

EXIT_OK = 0
EXIT_USAGE = 2
OUTCOME_TITLE = "Прогноз симулятора против реального финиша"


def write_report(
    out: Path,
    season: int,
    round_number: int,
    db_path: Path,
    runs: int = SIM_RUNS,
    strategy_runs: int = REPORT_STRATEGY_RUNS,
) -> Path:
    """Build the facts, charts and Markdown of a race; return the Markdown path.

    Raises:
        RaceNotFoundError: If the race is not in the database.
    """
    engine = create_sqlite_engine(db_path)
    init_db(engine)
    race_id = race_id_for(season, round_number)
    calibration, models = calibrate(load_history(engine, CALIBRATION_SEASONS))
    setup: RaceSetup | str
    try:
        setup = race_setup(engine, race_id, calibration, models)
    except SetupError as error:
        setup = str(error)
    params = SimulationParams(runs=runs)
    facts = race_facts(engine, race_id, setup, params, SimulationParams(runs=strategy_runs))
    stem = report_stem(season, round_number, facts.circuit_id)
    charts = ReportCharts(stints=f"{stem}-stints.png")
    plot_stints(facts, out / charts.stints)
    if isinstance(setup, RaceSetup):
        charts = ReportCharts(stints=charts.stints, outcome=f"{stem}-outcome.png")
        scored = score_race(setup, actual_results(engine, race_id), params)
        plot_backtest_races([scored], out / charts.outcome, OUTCOME_TITLE)
    path = out / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(facts, charts), encoding="utf-8", newline="\n")
    return path


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(prog="python -m f1lab.report")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--out", type=Path, default=REPORT_DIR, help="output directory")
    parser.add_argument("--runs", type=int, default=SIM_RUNS)
    parser.add_argument(
        "--strategy-runs",
        type=int,
        default=REPORT_STRATEGY_RUNS,
        help="runs per strategy in the podium strategy check",
    )
    parser.add_argument("--db", type=Path, help="SQLite file (default: <data dir>/f1lab.sqlite)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write one report and return the process exit code."""
    args = build_parser().parse_args(argv)
    tolerate_console_encoding()
    try:
        path = write_report(
            args.out,
            args.season,
            args.round,
            args.db or get_db_path(),
            args.runs,
            args.strategy_runs,
        )
    except RaceNotFoundError as error:
        print(f"error: {error}; load it with python -m f1lab.ingest", file=sys.stderr)
        return EXIT_USAGE
    print(f"Report: {path}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

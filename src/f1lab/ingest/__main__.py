"""Command line entry point: ``python -m f1lab.ingest``.

Examples:
    python -m f1lab.ingest                         # default seasons
    python -m f1lab.ingest --season 2024 --round 1
    python -m f1lab.ingest --season 2025 --force   # reload what is already there
"""

import argparse
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from f1lab.config import DEFAULT_SEASONS, get_cache_dir, get_db_path
from f1lab.console import tolerate_console_encoding
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.db.quality import format_report, run_checks
from f1lab.ingest.jolpica import create_jolpica_client
from f1lab.ingest.loader import (
    LoadStatus,
    RaceLoader,
    SeasonNotSupportedError,
    UnknownRoundError,
)
from f1lab.ingest.openf1 import create_openf1_client

EXIT_OK = 0
EXIT_RACE_FAILED = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser of the ingest CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m f1lab.ingest",
        description="Load F1 races from Jolpica-F1 and OpenF1 into SQLite.",
    )
    parser.add_argument(
        "--season",
        type=int,
        action="append",
        dest="seasons",
        help=f"season to load, repeatable (default: {' '.join(map(str, DEFAULT_SEASONS))})",
    )
    parser.add_argument(
        "--round", type=int, action="append", dest="rounds", help="only this round, repeatable"
    )
    parser.add_argument("--force", action="store_true", help="reload races already in the database")
    parser.add_argument("--db", type=Path, help="SQLite file (default: <data dir>/f1lab.sqlite)")
    parser.add_argument("--cache-dir", type=Path, help="HTTP cache (default: <data dir>/cache)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    args = build_parser().parse_args(argv)
    tolerate_console_encoding()
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)

    db_path = args.db or get_db_path()
    engine = create_sqlite_engine(db_path)
    init_db(engine)
    cache_dir = args.cache_dir or get_cache_dir()
    loader = RaceLoader(engine, create_jolpica_client(cache_dir), create_openf1_client(cache_dir))

    reports = []
    try:
        for season in args.seasons or DEFAULT_SEASONS:
            reports += loader.load_season(season, rounds=args.rounds, force=args.force)
    except (SeasonNotSupportedError, UnknownRoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE

    totals = Counter(report.status for report in reports)
    print(
        f"Database: {db_path}\n" + ", ".join(f"{status}: {totals[status]}" for status in LoadStatus)
    )
    print(format_report(run_checks(engine)))
    return EXIT_RACE_FAILED if totals[LoadStatus.FAILED] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

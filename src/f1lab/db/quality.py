"""Data quality checks defined as SQL in ``sql/data_quality.sql``.

Usage: ``python -m f1lab.db.quality [--db PATH]``.
"""

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text

from f1lab.config import DATA_QUALITY_SQL, get_db_path
from f1lab.db.engine import create_sqlite_engine, init_db

_CHECK_HEADER = re.compile(r"^-- name: *(?P<name>\w+) *$", re.MULTILINE)
_COMMENT_PREFIX = "--"

EXIT_OK = 0
EXIT_VIOLATIONS = 1


@dataclass(frozen=True)
class QualityCheck:
    """A named SQL query that returns the rows violating a data rule."""

    name: str
    description: str
    sql: str


def parse_checks(source: str) -> list[QualityCheck]:
    """Split a SQL file into checks.

    Each check starts with ``-- name: <id>``, continues with comment lines (the
    description) and ends with the query. Text before the first header is ignored.

    Args:
        source: Content of the SQL file.

    Returns:
        Checks in file order.
    """
    headers = list(_CHECK_HEADER.finditer(source))
    checks = []
    for header, following in zip(headers, [*headers[1:], None], strict=True):
        body = source[header.end() : following.start() if following else len(source)]
        lines = body.strip().splitlines()
        description = " ".join(
            line.removeprefix(_COMMENT_PREFIX).strip()
            for line in lines
            if line.startswith(_COMMENT_PREFIX)
        )
        sql = "\n".join(line for line in lines if not line.startswith(_COMMENT_PREFIX))
        checks.append(QualityCheck(header["name"], description, sql.strip().rstrip(";")))
    return checks


def load_checks(path: Path = DATA_QUALITY_SQL) -> list[QualityCheck]:
    """Read and parse the checks file."""
    return parse_checks(path.read_text(encoding="utf-8"))


def run_checks(engine: Engine, checks: Sequence[QualityCheck] | None = None) -> dict[str, int]:
    """Count the violating rows of every check.

    Args:
        engine: Database to check.
        checks: Checks to run; all checks from the SQL file by default.

    Returns:
        Number of offending rows per check name (0 means OK).
    """
    checks = load_checks() if checks is None else checks
    with engine.connect() as conn:
        return {
            check.name: conn.execute(text(f"SELECT COUNT(*) FROM ({check.sql})")).scalar_one()
            for check in checks
        }


def format_report(violations: dict[str, int]) -> str:
    """Return a human-readable summary of check results."""
    failed = {name: rows for name, rows in violations.items() if rows}
    if not failed:
        return f"Data quality: all {len(violations)} checks passed"
    lines = [f"Data quality: {len(failed)} of {len(violations)} checks found issues"]
    lines += [f"  {name}: {rows} row(s)" for name, rows in failed.items()]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run all checks against a database and print the report."""
    parser = argparse.ArgumentParser(prog="python -m f1lab.db.quality")
    parser.add_argument("--db", type=Path, help="SQLite file (default: <data dir>/f1lab.sqlite)")
    args = parser.parse_args(argv)
    engine = create_sqlite_engine(args.db or get_db_path())
    init_db(engine)
    violations = run_checks(engine)
    print(format_report(violations))
    return EXIT_VIOLATIONS if any(violations.values()) else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

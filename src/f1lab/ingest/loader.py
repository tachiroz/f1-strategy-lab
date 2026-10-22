"""Idempotent loading of races into the database.

A race is fetched and transformed completely in memory first; only then are its
rows replaced inside one transaction: delete every race-scoped row, upsert the
race and its drivers, insert the fresh rows and an ``ingest_runs`` record. A
failure at any point leaves the previous state of the race untouched.
"""

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Connection, Engine, Table, delete, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from f1lab.config import OPENF1_FIRST_SEASON
from f1lab.db import schema
from f1lab.ingest.http import HttpError, JsonObject
from f1lab.ingest.jolpica import JolpicaClient
from f1lab.ingest.openf1 import OpenF1Client
from f1lab.ingest.transform import (
    RaceRows,
    Row,
    TransformError,
    build_race_rows,
    match_session,
    race_id_for,
)

logger = logging.getLogger(__name__)


class LoadStatus(StrEnum):
    """Outcome of loading one race."""

    LOADED = "loaded"
    SKIPPED = "skipped"
    NOT_AVAILABLE = "not available"
    FAILED = "failed"


class SeasonNotSupportedError(ValueError):
    """The season predates the lap and tyre data available in OpenF1."""


class UnknownRoundError(ValueError):
    """A requested round is not in the season schedule."""


@dataclass(frozen=True)
class LoadReport:
    """Result of loading one race."""

    season: int
    round: int
    race_name: str
    status: LoadStatus
    row_counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def describe(self) -> str:
        """Return a one-line human-readable summary."""
        line = f"{self.season} R{self.round:02d} {self.race_name}: {self.status}"
        if self.row_counts:
            line += " (" + ", ".join(f"{k}={v}" for k, v in self.row_counts.items()) + ")"
        if self.error:
            line += f": {self.error}"
        return line


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def _upsert(conn: Connection, table: Table, rows: list[Row]) -> None:
    """Insert rows or update every non-key column of rows that already exist."""
    if not rows:
        return
    statement = sqlite_insert(table)
    key_columns = [column.name for column in table.primary_key.columns]
    statement = statement.on_conflict_do_update(
        index_elements=key_columns,
        set_={
            column.name: statement.excluded[column.name]
            for column in table.columns
            if column.name not in key_columns
        },
    )
    conn.execute(statement, rows)


def write_race(engine: Engine, rows: RaceRows, loaded_at: datetime) -> None:
    """Replace all rows of a race in one transaction.

    Args:
        engine: Target database.
        rows: Complete, transformed rows of the race.
        loaded_at: Timestamp recorded in ``ingest_runs``.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If the database rejects the rows; the
            transaction is rolled back and the previous data stays in place.
    """
    race_id = rows.race["race_id"]
    unique_drivers = list({row["driver_id"]: row for row in rows.drivers}.values())
    with engine.begin() as conn:
        for table in schema.RACE_TABLES:
            conn.execute(delete(table).where(table.c.race_id == race_id))
        _upsert(conn, schema.races, [rows.race])
        _upsert(conn, schema.drivers, unique_drivers)
        for table, table_rows in (
            (schema.results, rows.results),
            (schema.qualifying, rows.qualifying),
            (schema.pit_stops, rows.pit_stops),
            (schema.laps, rows.laps),
            (schema.stints, rows.stints),
            (schema.weather, rows.weather),
            (schema.race_control, rows.race_control),
        ):
            if table_rows:
                conn.execute(insert(table), table_rows)
        conn.execute(
            insert(schema.ingest_runs).values(
                race_id=race_id,
                loaded_at_utc=loaded_at.isoformat(timespec="seconds"),
                row_counts=json.dumps(rows.row_counts(), sort_keys=True),
            )
        )


class RaceLoader:
    """Loads races from Jolpica-F1 and OpenF1 into the database."""

    def __init__(
        self,
        engine: Engine,
        jolpica: JolpicaClient,
        openf1: OpenF1Client,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Create a loader.

        Args:
            engine: Initialised database (see ``f1lab.db.engine.init_db``).
            jolpica: Source of the schedule, results and pit stops.
            openf1: Source of laps, stints, weather and race control.
            clock: Returns the load timestamp; replaceable in tests.
        """
        self._engine = engine
        self._jolpica = jolpica
        self._openf1 = openf1
        self._clock = clock

    def is_loaded(self, race_id: int) -> bool:
        """Return True if the race has a completed load in ``ingest_runs``."""
        with self._engine.connect() as conn:
            found = conn.execute(
                select(schema.ingest_runs.c.race_id).where(schema.ingest_runs.c.race_id == race_id)
            ).first()
        return found is not None

    def load_season(
        self, season: int, *, rounds: Sequence[int] | None = None, force: bool = False
    ) -> list[LoadReport]:
        """Load all (or selected) races of a season.

        A failure of one race is reported and does not stop the others.

        Args:
            season: Season year, ``OPENF1_FIRST_SEASON`` or later.
            rounds: Only these rounds; all rounds of the schedule by default.
            force: Reload races that are already in the database.

        Returns:
            One report per race, in schedule order.

        Raises:
            SeasonNotSupportedError: If the season is older than OpenF1 data.
            UnknownRoundError: If a requested round is not in the schedule.
        """
        if season < OPENF1_FIRST_SEASON:
            raise SeasonNotSupportedError(
                f"OpenF1 has lap and tyre data from {OPENF1_FIRST_SEASON}; got {season}"
            )
        schedule = self._jolpica.schedule(season)
        if rounds is not None:
            missing = set(rounds) - {int(race["round"]) for race in schedule}
            if missing:
                raise UnknownRoundError(f"Season {season} has no round(s) {sorted(missing)}")
            schedule = [race for race in schedule if int(race["round"]) in rounds]

        sessions = self._openf1.race_sessions(season)
        reports = []
        for race in schedule:
            report = self._load_race(race, sessions, force=force)
            logger.info(report.describe())
            reports.append(report)
        return reports

    def load_race(self, season: int, round_number: int, *, force: bool = False) -> LoadReport:
        """Load a single race; see ``load_season``."""
        return self.load_season(season, rounds=[round_number], force=force)[0]

    def _load_race(
        self, race: JsonObject, sessions: list[JsonObject], *, force: bool
    ) -> LoadReport:
        """Fetch, transform and write one race, turning expected failures into reports."""
        season, round_number = int(race["season"]), int(race["round"])

        def report(status: LoadStatus, **kwargs: object) -> LoadReport:
            return LoadReport(season, round_number, race["raceName"], status, **kwargs)

        if not force and self.is_loaded(race_id_for(season, round_number)):
            return report(LoadStatus.SKIPPED)
        try:
            results = self._jolpica.results(season, round_number)
            if not results:
                return report(LoadStatus.NOT_AVAILABLE, error="no results yet")
            session = match_session(race, sessions)
            key = session["session_key"]
            rows = build_race_rows(
                race,
                session,
                results=results,
                pit_stops=self._jolpica.pit_stops(season, round_number),
                qualifying=self._jolpica.qualifying(season, round_number),
                laps=self._openf1.laps(key),
                stints=self._openf1.stints(key),
                weather=self._openf1.weather(key),
                race_control=self._openf1.race_control(key),
            )
            write_race(self._engine, rows, self._clock())
        except (HttpError, TransformError, SQLAlchemyError) as error:
            return report(LoadStatus.FAILED, error=f"{type(error).__name__}: {error}")
        return report(LoadStatus.LOADED, row_counts=rows.row_counts())

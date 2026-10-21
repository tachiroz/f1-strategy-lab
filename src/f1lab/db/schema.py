"""Database schema (SQLAlchemy Core).

Conventions:
    * durations are stored in seconds (REAL), timestamps as ISO 8601 strings in UTC;
    * ``race_id = season * 100 + round`` (see ``config.RACE_ID_SEASON_MULTIPLIER``);
    * every race-scoped table has ``race_id`` in its primary key, so reloading a race
      means deleting its rows and inserting fresh ones inside one transaction.

Sources: races, drivers, results and pit stops come from Jolpica-F1; laps, stints,
weather and race control messages come from OpenF1. Nullable columns mirror fields
that are missing in real payloads (e.g. sector times during red flags).
"""

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


def _race_key() -> Column[int]:
    """Return the ``race_id`` primary-key column referencing ``races``."""
    return Column("race_id", Integer, ForeignKey("races.race_id"), primary_key=True)


def _driver_key() -> Column[str]:
    """Return the ``driver_id`` primary-key column referencing ``drivers``."""
    return Column("driver_id", String, ForeignKey("drivers.driver_id"), primary_key=True)


races = Table(
    "races",
    metadata,
    Column("race_id", Integer, primary_key=True, autoincrement=False),
    Column("season", Integer, nullable=False),
    Column("round", Integer, nullable=False),
    Column("race_name", String, nullable=False),
    Column("circuit_id", String, nullable=False),
    Column("circuit_name", String, nullable=False),
    Column("locality", String),
    Column("country", String),
    Column("start_time_utc", String, nullable=False),
    Column("openf1_session_key", Integer, unique=True),
    Column("openf1_meeting_key", Integer),
    UniqueConstraint("season", "round"),
)

drivers = Table(
    "drivers",
    metadata,
    Column("driver_id", String, primary_key=True, comment="Jolpica driverId"),
    Column("code", String),
    Column("permanent_number", Integer),
    Column("given_name", String, nullable=False),
    Column("family_name", String, nullable=False),
    Column("date_of_birth", String),
    Column("nationality", String),
)

results = Table(
    "results",
    metadata,
    _race_key(),
    _driver_key(),
    Column("car_number", Integer, nullable=False),
    Column("constructor_id", String, nullable=False),
    Column("constructor_name", String, nullable=False),
    Column("grid", Integer, nullable=False),
    Column("position", Integer, nullable=False),
    Column("position_text", String, nullable=False, comment="'R' retired, 'D' DSQ, 'W' DNS"),
    Column("points", Float, nullable=False),
    Column("laps", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("race_time_ms", Integer),
    Column("fastest_lap", Integer),
    Column("fastest_lap_rank", Integer),
    Column("fastest_lap_time_s", Float),
    UniqueConstraint("race_id", "car_number"),
)

pit_stops = Table(
    "pit_stops",
    metadata,
    _race_key(),
    _driver_key(),
    Column("stop", Integer, primary_key=True),
    Column("lap", Integer, nullable=False),
    Column("time_of_day", String, nullable=False, comment="local time at the track"),
    Column(
        "duration_s",
        Float,
        comment="pit lane time, red flags included; NULL when the source has no duration",
    ),
)

laps = Table(
    "laps",
    metadata,
    _race_key(),
    _driver_key(),
    Column("lap", Integer, primary_key=True),
    Column("start_time_utc", String),
    Column("lap_time_s", Float),
    Column("sector1_s", Float),
    Column("sector2_s", Float),
    Column("sector3_s", Float),
    Column("i1_speed_kph", Integer),
    Column("i2_speed_kph", Integer),
    Column("st_speed_kph", Integer),
    Column("is_pit_out_lap", Boolean, nullable=False),
)

stints = Table(
    "stints",
    metadata,
    _race_key(),
    _driver_key(),
    Column("stint", Integer, primary_key=True),
    Column("compound", String, comment="SOFT, MEDIUM, HARD, INTERMEDIATE, WET or UNKNOWN"),
    Column("lap_start", Integer),
    Column("lap_end", Integer),
    Column("tyre_age_at_start", Integer),
)

weather = Table(
    "weather",
    metadata,
    _race_key(),
    Column("time_utc", String, primary_key=True),
    Column("air_temp_c", Float, nullable=False),
    Column("track_temp_c", Float, nullable=False),
    Column("humidity_pct", Float, nullable=False),
    Column("pressure_mbar", Float, nullable=False),
    Column("rainfall", Boolean, nullable=False),
    Column("wind_speed_ms", Float, nullable=False),
    Column("wind_direction_deg", Integer, nullable=False),
)

race_control = Table(
    "race_control",
    metadata,
    _race_key(),
    Column("seq", Integer, primary_key=True, comment="order of the message within the race"),
    Column("time_utc", String, nullable=False),
    Column("lap", Integer),
    Column("category", String, nullable=False, comment="Flag, SafetyCar, Drs, ..."),
    Column("flag", String),
    Column("scope", String),
    Column("sector", Integer),
    Column("driver_id", String, ForeignKey("drivers.driver_id")),
    Column("message", Text, nullable=False),
)

ingest_runs = Table(
    "ingest_runs",
    metadata,
    _race_key(),
    Column("loaded_at_utc", String, nullable=False),
    Column("row_counts", Text, nullable=False, comment="JSON object: table -> rows"),
)

schema_meta = Table(
    "schema_meta",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
)

RACE_TABLES: tuple[Table, ...] = (
    results,
    pit_stops,
    laps,
    stints,
    weather,
    race_control,
    ingest_runs,
)
"""Tables whose rows belong to a single race; deleted and reinserted on reload."""

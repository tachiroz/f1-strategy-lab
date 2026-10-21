"""Pure transformations from API payloads to database rows.

Functions take already fetched JSON and return dicts keyed by the column names of
``f1lab.db.schema``. Nothing here performs I/O, so every rule is unit-tested on
recorded responses.

OpenF1 identifies drivers by car number, Jolpica by ``driverId``. Car numbers are
mapped through the race classification (``Results[].number``), which is correct
even when a driver races with a number other than their permanent one.
"""

from dataclasses import dataclass, fields
from datetime import date, datetime

from f1lab.config import RACE_ID_SEASON_MULTIPLIER, SESSION_MATCH_TOLERANCE_DAYS
from f1lab.ingest.http import JsonObject, JsonValue

type Row = dict[str, str | int | float | bool | None]

SECONDS_PER_UNIT = 60
"""Ergast durations are "h:mm:ss.sss": each colon-separated part is 60x the next."""
MAX_DURATION_PARTS = 3
DURATION_DECIMALS = 3
"""Durations are given to the millisecond; rounding removes float noise."""


class TransformError(ValueError):
    """A payload cannot be mapped onto the schema."""


@dataclass(frozen=True)
class RaceRows:
    """All rows of one race, ready to be written in a single transaction."""

    race: Row
    drivers: list[Row]
    results: list[Row]
    pit_stops: list[Row]
    laps: list[Row]
    stints: list[Row]
    weather: list[Row]
    race_control: list[Row]

    def row_counts(self) -> dict[str, int]:
        """Return the number of rows per race-scoped table."""
        return {
            field.name: len(getattr(self, field.name))
            for field in fields(self)
            if field.name not in ("race", "drivers")
        }


def race_id_for(season: int, round_number: int) -> int:
    """Return the stable race id, e.g. 202401 for round 1 of 2024."""
    return season * RACE_ID_SEASON_MULTIPLIER + round_number


def parse_duration_s(text: str) -> float:
    """Parse an Ergast-style duration into seconds.

    Args:
        text: ``"ss.sss"``, ``"m:ss.sss"`` or ``"h:mm:ss.sss"``,
            e.g. ``"25.208"``, ``"23:44.659"``, ``"1:31:44.742"``.

    Returns:
        Duration in seconds, rounded to the millisecond.

    Raises:
        TransformError: If the text is not a duration.
    """
    parts = text.strip().split(":")
    if len(parts) > MAX_DURATION_PARTS or not all(parts):
        raise TransformError(f"Not a duration: {text!r}")
    seconds = 0.0
    try:
        for part in parts:
            seconds = seconds * SECONDS_PER_UNIT + float(part)
    except ValueError as error:
        raise TransformError(f"Not a duration: {text!r}") from error
    return round(seconds, DURATION_DECIMALS)


def _optional_int(value: JsonValue) -> int | None:
    """Convert a numeric string (or number) to int, keeping None."""
    return None if value is None else int(str(value))


def race_start_utc(race: JsonObject) -> str:
    """Return the race start as ``"YYYY-MM-DDTHH:MM:SSZ"`` from Jolpica date and time.

    Raises:
        TransformError: If the start time is missing (true for old seasons only).
    """
    if "time" not in race:
        raise TransformError(f"{race['season']} R{race['round']}: no start time")
    return f"{race['date']}T{race['time']}"


def match_session(race: JsonObject, sessions: list[JsonObject]) -> JsonObject:
    """Find the OpenF1 race session of a Jolpica race.

    Sessions are matched by date with a tolerance of
    ``SESSION_MATCH_TOLERANCE_DAYS`` because the two sources may disagree by a day
    (Las Vegas 2024). Cancelled sessions (Imola 2023) are ignored.

    Args:
        race: Jolpica race from the season schedule.
        sessions: OpenF1 race sessions of the same year.

    Returns:
        The single matching session.

    Raises:
        TransformError: If no session or more than one session matches.
    """
    race_day = date.fromisoformat(race["date"])
    candidates = [
        session
        for session in sessions
        if not session.get("is_cancelled")
        and abs((datetime.fromisoformat(session["date_start"]).date() - race_day).days)
        <= SESSION_MATCH_TOLERANCE_DAYS
    ]
    if len(candidates) != 1:
        raise TransformError(
            f"{race['season']} R{race['round']} {race['raceName']}: expected one OpenF1 race "
            f"session within {SESSION_MATCH_TOLERANCE_DAYS} day(s) of {race_day}, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def race_row(race: JsonObject, session: JsonObject) -> Row:
    """Build the ``races`` row from a Jolpica race and its OpenF1 session."""
    season, round_number = int(race["season"]), int(race["round"])
    circuit = race["Circuit"]
    location = circuit.get("Location", {})
    return {
        "race_id": race_id_for(season, round_number),
        "season": season,
        "round": round_number,
        "race_name": race["raceName"],
        "circuit_id": circuit["circuitId"],
        "circuit_name": circuit["circuitName"],
        "locality": location.get("locality"),
        "country": location.get("country"),
        "start_time_utc": race_start_utc(race),
        "openf1_session_key": session["session_key"],
        "openf1_meeting_key": session.get("meeting_key"),
    }


def driver_row(driver: JsonObject) -> Row:
    """Build a ``drivers`` row from a Jolpica ``Driver`` object."""
    return {
        "driver_id": driver["driverId"],
        "code": driver.get("code"),
        "permanent_number": _optional_int(driver.get("permanentNumber")),
        "given_name": driver["givenName"],
        "family_name": driver["familyName"],
        "date_of_birth": driver.get("dateOfBirth"),
        "nationality": driver.get("nationality"),
    }


def result_row(race_id: int, result: JsonObject) -> Row:
    """Build a ``results`` row; time and fastest lap are None when absent (DNS, DSQ)."""
    fastest = result.get("FastestLap", {})
    fastest_time = fastest.get("Time", {}).get("time")
    return {
        "race_id": race_id,
        "driver_id": result["Driver"]["driverId"],
        "car_number": int(result["number"]),
        "constructor_id": result["Constructor"]["constructorId"],
        "constructor_name": result["Constructor"]["name"],
        "grid": int(result["grid"]),
        "position": int(result["position"]),
        "position_text": result["positionText"],
        "points": float(result["points"]),
        "laps": int(result["laps"]),
        "status": result["status"],
        "race_time_ms": _optional_int(result.get("Time", {}).get("millis")),
        "fastest_lap": _optional_int(fastest.get("lap")),
        "fastest_lap_rank": _optional_int(fastest.get("rank")),
        "fastest_lap_time_s": None if fastest_time is None else parse_duration_s(fastest_time),
    }


def car_number_map(results: list[JsonObject]) -> dict[int, str]:
    """Map the car numbers used in a race to Jolpica driver ids.

    Raises:
        TransformError: If two drivers share a number in the classification.
    """
    mapping = {int(r["number"]): r["Driver"]["driverId"] for r in results}
    if len(mapping) != len(results):
        raise TransformError("Duplicate car numbers in the race results")
    return mapping


def _driver_for_number(numbers: dict[int, str], driver_number: int, context: str) -> str:
    """Return the driver id of a car number, failing loudly for unknown numbers."""
    try:
        return numbers[driver_number]
    except KeyError:
        raise TransformError(
            f"{context}: car number {driver_number} is not in the race results"
        ) from None


def pit_stop_row(race_id: int, stop: JsonObject) -> Row:
    """Build a ``pit_stops`` row.

    Red-flag periods appear as very long stops. Jolpica sometimes records a stop
    with an empty duration (e.g. Tsunoda, British GP 2024): the stop is kept and
    its duration is None rather than invented.
    """
    duration = stop["duration"].strip()
    return {
        "race_id": race_id,
        "driver_id": stop["driverId"],
        "stop": int(stop["stop"]),
        "lap": int(stop["lap"]),
        "time_of_day": stop["time"],
        "duration_s": parse_duration_s(duration) if duration else None,
    }


def lap_row(race_id: int, lap: JsonObject, numbers: dict[int, str]) -> Row:
    """Build a ``laps`` row from an OpenF1 lap; timing fields may be None."""
    return {
        "race_id": race_id,
        "driver_id": _driver_for_number(numbers, lap["driver_number"], "laps"),
        "lap": lap["lap_number"],
        "start_time_utc": lap.get("date_start"),
        "lap_time_s": lap.get("lap_duration"),
        "sector1_s": lap.get("duration_sector_1"),
        "sector2_s": lap.get("duration_sector_2"),
        "sector3_s": lap.get("duration_sector_3"),
        "i1_speed_kph": lap.get("i1_speed"),
        "i2_speed_kph": lap.get("i2_speed"),
        "st_speed_kph": lap.get("st_speed"),
        "is_pit_out_lap": bool(lap["is_pit_out_lap"]),
    }


def stint_row(race_id: int, stint: JsonObject, numbers: dict[int, str]) -> Row:
    """Build a ``stints`` row; the lap range is None for drivers who never started."""
    return {
        "race_id": race_id,
        "driver_id": _driver_for_number(numbers, stint["driver_number"], "stints"),
        "stint": stint["stint_number"],
        "compound": stint.get("compound"),
        "lap_start": stint.get("lap_start"),
        "lap_end": stint.get("lap_end"),
        "tyre_age_at_start": stint.get("tyre_age_at_start"),
    }


def weather_row(race_id: int, sample: JsonObject) -> Row:
    """Build a ``weather`` row from a per-minute OpenF1 sample."""
    return {
        "race_id": race_id,
        "time_utc": sample["date"],
        "air_temp_c": sample["air_temperature"],
        "track_temp_c": sample["track_temperature"],
        "humidity_pct": sample["humidity"],
        "pressure_mbar": sample["pressure"],
        "rainfall": bool(sample["rainfall"]),
        "wind_speed_ms": sample["wind_speed"],
        "wind_direction_deg": sample["wind_direction"],
    }


def race_control_rows(
    race_id: int, messages: list[JsonObject], numbers: dict[int, str]
) -> list[Row]:
    """Build ``race_control`` rows numbered in API (chronological) order.

    A message about a car that is not in the classification keeps ``driver_id``
    None; the number is still in the message text.
    """
    return [
        {
            "race_id": race_id,
            "seq": seq,
            "time_utc": message["date"],
            "lap": message.get("lap_number"),
            "category": message["category"],
            "flag": message.get("flag"),
            "scope": message.get("scope"),
            "sector": message.get("sector"),
            "driver_id": numbers.get(message["driver_number"])
            if message.get("driver_number") is not None
            else None,
            "message": message["message"],
        }
        for seq, message in enumerate(messages, start=1)
    ]


def build_race_rows(
    race: JsonObject,
    session: JsonObject,
    *,
    results: list[JsonObject],
    pit_stops: list[JsonObject],
    laps: list[JsonObject],
    stints: list[JsonObject],
    weather: list[JsonObject],
    race_control: list[JsonObject],
) -> RaceRows:
    """Transform all payloads of one race into table rows.

    Args:
        race: Jolpica race from the schedule.
        session: Matching OpenF1 race session (see ``match_session``).
        results: Jolpica classification.
        pit_stops: Jolpica pit stops.
        laps: OpenF1 laps.
        stints: OpenF1 stints.
        weather: OpenF1 weather samples.
        race_control: OpenF1 race control messages.

    Returns:
        Rows for every table, drivers deduplicated.

    Raises:
        TransformError: If the race has no results or a payload is inconsistent.
    """
    row = race_row(race, session)
    race_id = int(row["race_id"])
    if not results:
        raise TransformError(f"{row['season']} R{row['round']} {row['race_name']}: no results")
    numbers = car_number_map(results)
    return RaceRows(
        race=row,
        drivers=[driver_row(result["Driver"]) for result in results],
        results=[result_row(race_id, result) for result in results],
        pit_stops=[pit_stop_row(race_id, stop) for stop in pit_stops],
        laps=[lap_row(race_id, lap, numbers) for lap in laps],
        stints=[stint_row(race_id, stint, numbers) for stint in stints],
        weather=[weather_row(race_id, sample) for sample in weather],
        race_control=race_control_rows(race_id, race_control, numbers),
    )

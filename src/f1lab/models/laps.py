"""Load laps and race context for the tyre model from the database."""

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, bindparam, select, text

from f1lab.config import MODEL_LAPS_SQL
from f1lab.db import schema

TIMESTAMP_DTYPE = "datetime64[ns, UTC]"
"""One resolution everywhere: pandas refuses to merge timestamps of different units."""


def _to_utc(series: pd.Series) -> pd.Series:
    """Parse ISO 8601 strings (with offsets) into UTC timestamps of ``TIMESTAMP_DTYPE``."""
    return pd.to_datetime(series, utc=True, format="ISO8601").astype(TIMESTAMP_DTYPE)


def load_model_laps(
    engine: Engine, seasons: Sequence[int], sql_path: Path = MODEL_LAPS_SQL
) -> pd.DataFrame:
    """Return every lap of the given seasons with its tyre and pit context.

    Args:
        engine: Database with loaded races.
        seasons: Seasons to include.
        sql_path: Query file (``sql/model_laps.sql`` by default).

    Returns:
        One row per lap: race and circuit ids, driver, lap number, start time
        (UTC timestamp), lap time, pit in/out flags, stint, compound, tyre age.
        Tyre columns are missing (NA) for laps that no stint covers.
    """
    query = text(sql_path.read_text(encoding="utf-8")).bindparams(
        bindparam("seasons", expanding=True)
    )
    with engine.connect() as conn:
        laps = pd.read_sql(query, conn, params={"seasons": list(seasons)})
    laps["start_time_utc"] = _to_utc(laps["start_time_utc"])
    laps["is_pit_out_lap"] = laps["is_pit_out_lap"].astype(bool)
    laps["is_pit_in_lap"] = laps["is_pit_in_lap"].astype(bool)
    laps["stint"] = laps["stint"].astype("Int64")
    laps["tyre_age"] = laps["tyre_age"].astype("Int64")
    return laps


def load_race_control(engine: Engine, race_ids: Sequence[int]) -> pd.DataFrame:
    """Return race control messages of the given races in chronological order."""
    table = schema.race_control
    query = (
        select(table.c.race_id, table.c.seq, table.c.time_utc, table.c.category)
        .add_columns(table.c.flag, table.c.scope, table.c.message)
        .where(table.c.race_id.in_(list(race_ids)))
        .order_by(table.c.race_id, table.c.seq)
    )
    with engine.connect() as conn:
        messages = pd.read_sql(query, conn)
    messages["time_utc"] = _to_utc(messages["time_utc"])
    return messages


def load_rainfall(engine: Engine, race_ids: Sequence[int]) -> pd.DataFrame:
    """Return the per-minute rainfall samples (``race_id, time_utc, rainfall``)."""
    table = schema.weather
    query = (
        select(table.c.race_id, table.c.time_utc, table.c.rainfall)
        .where(table.c.race_id.in_(list(race_ids)))
        .order_by(table.c.race_id, table.c.time_utc)
    )
    with engine.connect() as conn:
        samples = pd.read_sql(query, conn)
    samples["time_utc"] = _to_utc(samples["time_utc"])
    samples["rainfall"] = samples["rainfall"].astype(bool)
    return samples

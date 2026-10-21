"""Tests for loading model laps from the database (recorded 2024 races)."""

import pandas as pd
from sqlalchemy import Engine, update

from f1lab.db import schema
from f1lab.ingest.openf1 import OpenF1Client
from f1lab.models.laps import load_model_laps, load_race_control, load_rainfall

BAHRAIN, SAO_PAULO = 202401, 202421


def verstappen_bahrain(laps: pd.DataFrame) -> pd.DataFrame:
    rows = laps[(laps["race_id"] == BAHRAIN) & (laps["driver_id"] == "max_verstappen")]
    return rows.set_index("lap")


def test_columns_and_types(loaded: Engine) -> None:
    laps = load_model_laps(loaded, [2024])
    assert {"race_id", "season", "circuit_id", "driver_id", "lap", "lap_time_s", "compound"} <= set(
        laps.columns
    )
    assert isinstance(laps["start_time_utc"].dtype, pd.DatetimeTZDtype)
    assert laps["is_pit_in_lap"].dtype == bool
    assert set(laps["race_id"]) == {BAHRAIN, SAO_PAULO}


def test_tyre_age_counts_from_stint_start(loaded: Engine, openf1: OpenF1Client) -> None:
    first_stint = next(
        s for s in openf1.stints(9472) if s["driver_number"] == 1 and s["stint_number"] == 1
    )
    lap = verstappen_bahrain(load_model_laps(loaded, [2024])).loc[10]
    assert lap["compound"] == "SOFT"
    assert lap["tyre_age"] == first_stint["tyre_age_at_start"] + 10 - first_stint["lap_start"]


def test_pit_flags(loaded: Engine) -> None:
    laps = verstappen_bahrain(load_model_laps(loaded, [2024]))
    assert list(laps.index[laps["is_pit_in_lap"]]) == [17, 37]
    assert list(laps.index[laps["is_pit_out_lap"]]) == [18, 38]
    assert laps.loc[18, "tyre_age"] == 0


def test_shared_boundary_lap_belongs_to_older_stint(loaded: Engine) -> None:
    with loaded.begin() as conn:
        conn.execute(
            update(schema.stints)
            .where(schema.stints.c.race_id == BAHRAIN)
            .where(schema.stints.c.driver_id == "max_verstappen")
            .where(schema.stints.c.stint == 2)
            .values(lap_start=17)
        )
    laps = verstappen_bahrain(load_model_laps(loaded, [2024]))
    assert (laps.loc[17, "stint"], laps.loc[17, "compound"]) == (1, "SOFT")
    assert laps.index.is_unique


def test_season_filter(loaded: Engine) -> None:
    assert load_model_laps(loaded, [2023]).empty


def test_race_control_and_rainfall(loaded: Engine) -> None:
    messages = load_race_control(loaded, [SAO_PAULO])
    assert messages["time_utc"].is_monotonic_increasing
    assert "RED" in set(messages["flag"].dropna())
    rain = load_rainfall(loaded, [BAHRAIN, SAO_PAULO])
    assert rain.groupby("race_id")["rainfall"].any().to_dict() == {BAHRAIN: False, SAO_PAULO: True}

"""Clean-lap rules for the tyre model.

Every lap gets the first reason (in the order of ``Exclusion``) that makes it
unrepresentative of race pace, or no reason if it is clean. Keeping the reason
instead of silently dropping rows makes the filter auditable: the report shows
how many laps each rule removed.
"""

from enum import StrEnum

import pandas as pd

from f1lab.config import (
    DRY_COMPOUNDS,
    FIRST_MODEL_LAP,
    MIN_CLEAN_LAPS_PER_DRIVER,
    NEUTRALISATION_RECOVERY_LAPS,
    OUTLIER_MAX_SLOWDOWN,
)
from f1lab.models.laps import TIMESTAMP_DTYPE
from f1lab.models.neutralisation import flag_neutralised_laps, neutralisation_periods

RACE_DRIVER = ["race_id", "driver_id"]


class Exclusion(StrEnum):
    """Why a lap is left out of the model, in the order the rules are applied."""

    UNTIMED = "untimed"
    FIRST_LAP = "first lap"
    PIT_IN = "pit in-lap"
    PIT_OUT = "pit out-lap"
    NO_TYRE = "unknown tyre"
    NOT_DRY = "not a dry compound"
    NEUTRALISED = "SC/VSC/red flag"
    AFTER_NEUTRALISATION = "restart after SC/VSC/red flag"
    RAIN = "rain"
    OUTLIER = "slow outlier"
    FEW_LAPS = "too few clean laps"


def _rain_during_lap(laps: pd.DataFrame, rainfall: pd.DataFrame) -> pd.Series:
    """Return True where the latest weather sample at lap start or lap end reports rain."""
    rain = pd.Series(False, index=laps.index)
    placed = laps[laps["start_time_utc"].notna()]
    if placed.empty or rainfall.empty:
        return rain
    samples = rainfall.assign(time_utc=rainfall["time_utc"].astype(TIMESTAMP_DTYPE))
    samples = samples.sort_values("time_utc")
    lap_start = placed["start_time_utc"].astype(TIMESTAMP_DTYPE)
    lap_end = lap_start + pd.to_timedelta(placed["lap_time_s"].fillna(0), unit="s")
    for moment in (lap_start, lap_end):
        probe = pd.DataFrame(
            {
                "race_id": placed["race_id"],
                "time_utc": moment.astype(TIMESTAMP_DTYPE),
                "row": placed.index,
            }
        )
        matched = pd.merge_asof(
            probe.sort_values("time_utc"),
            samples,
            on="time_utc",
            by="race_id",
            direction="backward",
        )
        raining = matched.set_index("row")["rainfall"].astype("boolean").fillna(False)
        rain.loc[raining.index] |= raining.astype(bool)
    return rain


def _after_neutralisation(laps: pd.DataFrame, neutralised: pd.Series) -> pd.Series:
    """Return True for the laps right after a neutralised lap of the same driver."""
    grouped = neutralised.groupby([laps["race_id"], laps["driver_id"]])
    after = pd.Series(False, index=laps.index)
    for offset in range(1, NEUTRALISATION_RECOVERY_LAPS + 1):
        after |= grouped.shift(offset, fill_value=False).astype(bool)
    return after & ~neutralised


def annotate_laps(
    laps: pd.DataFrame, race_control: pd.DataFrame, rainfall: pd.DataFrame
) -> pd.DataFrame:
    """Add ``neutralised`` and ``exclusion`` columns to the model laps.

    Args:
        laps: Output of ``f1lab.models.laps.load_model_laps``, ordered by race,
            driver and lap.
        race_control: Race control messages of the same races.
        rainfall: Rainfall samples of the same races.

    Returns:
        A copy of ``laps``; ``exclusion`` is an ``Exclusion`` value or NA for clean laps.
    """
    annotated = laps.copy()
    periods = {
        race_id: neutralisation_periods(messages)
        for race_id, messages in race_control.groupby("race_id")
    }
    neutralised = flag_neutralised_laps(annotated, periods)
    annotated["neutralised"] = neutralised

    rules: list[tuple[Exclusion, pd.Series]] = [
        (Exclusion.UNTIMED, annotated["lap_time_s"].isna()),
        (Exclusion.FIRST_LAP, annotated["lap"] < FIRST_MODEL_LAP),
        (Exclusion.PIT_IN, annotated["is_pit_in_lap"]),
        (Exclusion.PIT_OUT, annotated["is_pit_out_lap"]),
        (Exclusion.NO_TYRE, annotated["compound"].isna() | annotated["tyre_age"].isna()),
        (Exclusion.NOT_DRY, ~annotated["compound"].isin(DRY_COMPOUNDS)),
        (Exclusion.NEUTRALISED, neutralised),
        (Exclusion.AFTER_NEUTRALISATION, _after_neutralisation(annotated, neutralised)),
        (Exclusion.RAIN, _rain_during_lap(annotated, rainfall)),
    ]
    exclusion = pd.Series(pd.NA, index=annotated.index, dtype="string")
    for reason, mask in rules:
        exclusion = exclusion.mask(exclusion.isna() & mask.astype(bool), reason.value)

    candidate = exclusion.isna()
    median = (
        annotated["lap_time_s"]
        .where(candidate)
        .groupby([annotated["race_id"], annotated["driver_id"]])
        .transform("median")
    )
    slow = annotated["lap_time_s"] > median * (1 + OUTLIER_MAX_SLOWDOWN)
    exclusion = exclusion.mask(candidate & slow, Exclusion.OUTLIER.value)

    clean_count = (
        exclusion.isna().groupby([annotated["race_id"], annotated["driver_id"]]).transform("sum")
    )
    few = clean_count < MIN_CLEAN_LAPS_PER_DRIVER
    exclusion = exclusion.mask(exclusion.isna() & few, Exclusion.FEW_LAPS.value)

    annotated["exclusion"] = exclusion
    return annotated


def clean_laps(annotated: pd.DataFrame) -> pd.DataFrame:
    """Return only the laps without an exclusion reason."""
    return annotated[annotated["exclusion"].isna()].copy()


def exclusion_summary(annotated: pd.DataFrame) -> pd.Series:
    """Count laps per exclusion reason (in rule order) plus the clean ones."""
    counts = annotated["exclusion"].fillna("clean").value_counts()
    order = [reason.value for reason in Exclusion] + ["clean"]
    return counts.reindex(order, fill_value=0)

"""Tests for the automatic race report: wording, facts, rendering and the CLI.

Recorded races: Bahrain 2024 (dry, no neutralisation) and São Paulo 2024 (wet,
VSC, two Safety Cars and a red flag).
"""

import dataclasses
import re
from pathlib import Path

import pytest
from sqlalchemy import Engine

from f1lab.config import CALIBRATION_SEASONS
from f1lab.db.engine import create_sqlite_engine
from f1lab.report import text
from f1lab.report.__main__ import EXIT_OK, EXIT_USAGE, main
from f1lab.report.facts import PitLanePasses, RaceFacts, RaceNotFoundError, race_facts
from f1lab.report.render import NUMBER_FORMATS, ReportCharts, render_report, report_stem
from f1lab.sim.calibration import calibrate, load_history
from f1lab.sim.engine import SimulationParams
from f1lab.sim.setup import race_setup

BAHRAIN, SAO_PAULO = 202401, 202421
NUMBER = re.compile(r"\d+(?:,\d+)?")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
PNG = b"\x89PNG"


@pytest.fixture(scope="module")
def engine(race_db: Path) -> Engine:
    return create_sqlite_engine(race_db)


@pytest.fixture(scope="module")
def bahrain(engine: Engine) -> RaceFacts:
    """Bahrain 2024 with the simulator's view (few runs)."""
    calibration, models = calibrate(load_history(engine, CALIBRATION_SEASONS))
    setup = race_setup(engine, BAHRAIN, calibration, models)
    return race_facts(engine, BAHRAIN, setup, SimulationParams(runs=200), SimulationParams(runs=50))


@pytest.fixture(scope="module")
def sao_paulo(engine: Engine) -> RaceFacts:
    return race_facts(engine, SAO_PAULO, "São Paulo: ['INTERMEDIATE', 'WET'] tyres used; dry-only")


# --- wording -----------------------------------------------------------------


def test_numbers_use_a_decimal_comma_and_a_true_minus() -> None:
    assert text.number(15.499, 1) == "15,5"
    assert text.number(-0.0734, 3) == f"{text.MINUS}0,073"
    assert text.signed(10, 0) == "+10"
    assert text.signed(-6, 0) == f"{text.MINUS}6"
    assert text.signed(0.001, 2) == "0,00"
    assert text.unsigned(-0.162, 2) == "0,16"


def test_percent_lap_time_and_date() -> None:
    assert text.percent(0.424) == "42%"
    assert text.percent(0.001) == "<1%"
    assert text.lap_time(95.14) == "1:35,140"
    assert text.lap_time(80.472) == "1:20,472"
    assert text.long_date("2024-11-03") == "3 ноября 2024"


@pytest.mark.parametrize(
    ("count", "form"), [(1, "круг"), (2, "круга"), (5, "кругов"), (11, "кругов"), (22, "круга")]
)
def test_plural(count: int, form: str) -> None:
    assert text.plural(count, "круг", "круга", "кругов") == form


def test_names_of_things() -> None:
    assert text.compounds(("SOFT", "INTERMEDIATE", "WET")) == "Soft → Inter → Wet"
    assert text.compounds(()) == "—"
    assert text.status("Accident") == "авария"
    assert text.status("Fuel pressure") == "fuel pressure"
    assert text.neutralisation("VSC") == "виртуальный сейфти-кар"
    assert "мокрая" in text.setup_reason("X: ['INTERMEDIATE'] tyres used; dry-only")
    assert "нет составов" in text.setup_reason("X: ['UNKNOWN'] tyres used; dry-only")
    assert "нет модели" in text.setup_reason("No tyre model for interlagos")


# --- facts -------------------------------------------------------------------


def test_bahrain_facts(bahrain: RaceFacts) -> None:
    assert (bahrain.race_name, bahrain.season) == ("Bahrain Grand Prix", 2024)
    assert bahrain.race_laps == 57
    assert bahrain.starters == 20
    winner = bahrain.podium[0]
    assert (winner.driver_id, winner.position, winner.grid) == ("max_verstappen", 1, 1)
    assert bahrain.pole == winner
    assert bahrain.fastest_lap is not None
    assert bahrain.fastest_lap.driver_id == "max_verstappen"
    assert bahrain.winner_margin_s == pytest.approx(22.457, abs=0.01)
    assert bahrain.neutralisations == ()
    assert not bahrain.wet
    assert sum(count.drivers for count in bahrain.stop_counts) == bahrain.classified
    stops = [count.stops for count in bahrain.stop_counts]
    assert stops == sorted(stops)
    assert bahrain.pit_lane_passes is None


def test_movers_are_ordered_and_consistent(bahrain: RaceFacts) -> None:
    gains = [driver.gained for driver in bahrain.gainers]
    assert gains == sorted(gains, reverse=True)
    assert all(gain > 0 for gain in gains)
    assert all(driver.gained < 0 for driver in bahrain.losers)
    for driver in bahrain.finishers:
        assert driver.gained == driver.start_slot - driver.position


def test_simulator_view(bahrain: RaceFacts) -> None:
    view = bahrain.simulation
    assert view is not None
    assert view.runs == 200
    assert view.in_sample  # 2024 is a calibration season
    assert view.band_share == pytest.approx(0.8)
    assert 0 <= view.winner_p_win <= view.favourite_p_win <= 1
    assert view.winner_rank >= 1
    for surprise in view.over:
        assert surprise.position < surprise.band_low
    for surprise in view.under:
        assert surprise.position > surprise.band_high
    for idea in view.strategy_ideas:
        assert idea.delta_high < 0
        assert idea.delta <= -view.strategy_min_gain
        assert idea.better != idea.actual


def test_wet_race_with_a_red_flag(sao_paulo: RaceFacts) -> None:
    assert sao_paulo.wet
    assert [line.kind for line in sao_paulo.neutralisations] == ["VSC", "SC", "RED", "SC"]
    assert sao_paulo.has_safety_car
    assert sao_paulo.has_red_flag_changes
    assert sao_paulo.simulation is None
    assert "INTERMEDIATE" in (sao_paulo.simulation_reason or "")
    verstappen = sao_paulo.driver("max_verstappen")
    assert verstappen.red_flag_changes >= 1
    assert "INTERMEDIATE" in verstappen.compounds


def test_unknown_race(engine: Engine) -> None:
    with pytest.raises(RaceNotFoundError, match="190001"):
        race_facts(engine, 190001)


# --- rendering ---------------------------------------------------------------


def allowed_numbers(value: object) -> set[str]:
    """Every number the template could print from the facts (any field, any filter)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        found: set[str] = set()
        for item in dataclasses.fields(value):
            found |= allowed_numbers(getattr(value, item.name))
        return found
    if isinstance(value, tuple | list):
        return set().union(*(allowed_numbers(item) for item in value)) if value else set()
    if isinstance(value, str):
        return set(NUMBER.findall(value))
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, int | float):
        return {token for fmt in NUMBER_FORMATS for token in NUMBER.findall(fmt(value))}
    return set()


def printed_numbers(markdown: str) -> set[str]:
    return set(NUMBER.findall(LINK_TARGET.sub("]", markdown)))


@pytest.mark.parametrize("race", ["bahrain", "sao_paulo"])
def test_every_number_comes_from_the_facts(race: str, request: pytest.FixtureRequest) -> None:
    facts = request.getfixturevalue(race)
    markdown = render_report(facts, ReportCharts(stints="a.png", outcome="b.png"))
    assert printed_numbers(markdown) <= allowed_numbers(facts)


def test_allowed_numbers_catch_an_invented_number(bahrain: RaceFacts) -> None:
    assert "12345" not in allowed_numbers(bahrain)
    assert printed_numbers("ровно 12345 кругов") - allowed_numbers(bahrain) == {"12345"}


def test_dry_report_sections(bahrain: RaceFacts) -> None:
    markdown = render_report(bahrain)
    assert markdown.startswith("# Bahrain Grand Prix 2024: разбор гонки")
    for heading in ("## Итог", "## Позиции", "## Пит-стопы и шины", "## Нейтрализации"):
        assert heading in markdown
    assert "## Взгляд симулятора" in markdown
    assert "Оценка модели, а не факт" in markdown
    assert "Победил **Max Verstappen**" in markdown
    assert "без сейфти-кара, VSC и красного флага" in markdown
    assert "## Графики" not in markdown
    assert "None" not in markdown


def test_pit_lane_passes_are_explained(bahrain: RaceFacts) -> None:
    facts = dataclasses.replace(bahrain, pit_lane_passes=PitLanePasses(47, 2, 4))
    markdown = render_report(facts)
    assert "47 «пит-стопов» на кругах 2–4 без смены шин" in markdown
    assert printed_numbers(markdown) <= allowed_numbers(facts)
    single = dataclasses.replace(bahrain, pit_lane_passes=PitLanePasses(1, 3, 3))
    assert "1 «пит-стоп» на 3-м круге" in render_report(single)
    assert "через пит-лейн" not in render_report(bahrain)


def test_wet_report_explains_the_missing_simulation(sao_paulo: RaceFacts) -> None:
    markdown = render_report(sao_paulo, ReportCharts(stints="stints.png"))
    assert "Симулятор эту гонку не считал: мокрая гонка" in markdown
    assert "Красный флаг: круги" in markdown
    assert "под красным флагом" in markdown
    assert "![Шины по стинтам](stints.png)" in markdown
    assert "Прогноз против факта" not in markdown


# --- command line ------------------------------------------------------------


def test_report_stem() -> None:
    assert report_stem(2025, 4, "bahrain") == "2025-04-bahrain"


def test_cli_writes_markdown_and_charts(race_db: Path, tmp_path: Path) -> None:
    args = ["--db", str(race_db), "--out", str(tmp_path), "--runs", "50", "--strategy-runs", "20"]
    assert main([*args, "--season", "2024", "--round", "1"]) == EXIT_OK
    report = tmp_path / "2024-01-bahrain.md"
    assert "![Прогноз против факта](2024-01-bahrain-outcome.png)" in report.read_text("utf-8")
    for chart in ("2024-01-bahrain-outcome.png", "2024-01-bahrain-stints.png"):
        assert (tmp_path / chart).read_bytes()[:4] == PNG
    assert b"\r\n" not in report.read_bytes()

    assert main([*args, "--season", "2024", "--round", "21"]) == EXIT_OK
    assert (tmp_path / "2024-21-interlagos-stints.png").exists()
    assert not (tmp_path / "2024-21-interlagos-outcome.png").exists()


def test_cli_unknown_race(race_db: Path, tmp_path: Path) -> None:
    args = ["--db", str(race_db), "--out", str(tmp_path), "--season", "1900", "--round", "1"]
    assert main(args) == EXIT_USAGE

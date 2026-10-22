"""Tests for the simulator charts and the ``python -m f1lab.sim`` commands."""

from pathlib import Path

import pytest
from sqlalchemy import Engine

from f1lab.sim.__main__ import EXIT_OK, EXIT_USAGE, main, render_backtest
from f1lab.sim.backtest import backtest
from f1lab.sim.montecarlo import compare_strategies
from f1lab.sim.plots import (
    pick_showcase,
    plot_backtest_races,
    plot_backtest_scores,
    plot_strategy_comparison,
)
from f1lab.sim.strategy import parse_strategy
from synthetic import actual, complete_stints, make_setup, params

PNG = b"\x89PNG"


def is_png(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:4] == PNG


@pytest.fixture
def db(loaded: Engine) -> str:
    """Fixture database where every 2024 Bahrain starter has a dry strategy."""
    complete_stints(loaded, 202401, laps=57)
    return str(loaded.url.database)


def small_backtest() -> object:
    setup = make_setup([0.0, 1.0, 2.0], lap_noise_sd_s=0.5)
    prepared = [(setup, actual([1, 2, 3], [1, 2, 3])), (setup, actual([2, 1, 3], [1, 2, 3]))]
    return backtest(prepared, params(), skipped={202421: "wet race"})


def test_pick_showcase_orders_by_quality() -> None:
    result = small_backtest()
    picks = pick_showcase(result)
    assert len(picks) == 2
    assert picks[0].spearman >= picks[-1].spearman


def test_charts_are_png(tmp_path: Path) -> None:
    result = small_backtest()
    setup = make_setup([0.0, 0.2, 0.4], lap_noise_sd_s=0.5)
    plans = [parse_strategy("M-10-H"), parse_strategy("S-6-M-14-H")]
    table = compare_strategies(setup, "car0", plans, params(runs=100))
    paths = [
        plot_backtest_races(pick_showcase(result), tmp_path / "races.png"),
        plot_backtest_scores(result, tmp_path / "scores.png"),
        plot_strategy_comparison(table, "Test GP", tmp_path / "compare.png"),
    ]
    assert all(is_png(path) for path in paths)


def test_backtest_markdown() -> None:
    text = render_backtest(small_backtest(), params(), [2025])
    assert "## Итог" in text
    assert "финиш = решётка" in text
    assert "## Пропущенные гонки" in text
    assert "wet race" in text


def test_race_command(db: str, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--db", db, "race", "--season", "2024", "--round", "1", "--runs", "50"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "Bahrain Grand Prix 2024" in out
    assert "in-sample" in out
    assert "max_verstappen" in out


def test_compare_command_writes_a_chart(
    db: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chart = tmp_path / "compare.png"
    args = ["--db", db, "compare", "--season", "2024", "--round", "1", "--runs", "50"]
    args += ["--driver", "max_verstappen", "--strategy", "S-20-H", "--chart", str(chart)]
    assert main(args) == EXIT_OK
    out = capsys.readouterr().out
    assert "фактическая" in out
    assert "S-20-H" in out
    assert is_png(chart)


@pytest.mark.parametrize(
    "extra",
    [
        ["--driver", "nobody", "--strategy", "S-20-H"],
        ["--driver", "max_verstappen", "--strategy", "X-20-H"],
        ["--driver", "max_verstappen", "--strategy", "S-20-S"],
    ],
)
def test_compare_usage_errors(db: str, extra: list[str]) -> None:
    args = ["--db", db, "compare", "--season", "2024", "--round", "1", "--runs", "20", *extra]
    assert main(args) == EXIT_USAGE


def test_wet_race_is_a_usage_error(db: str) -> None:
    assert main(["--db", db, "race", "--season", "2024", "--round", "21"]) == EXIT_USAGE


def test_backtest_command(db: str, tmp_path: Path) -> None:
    args = ["--db", db, "backtest", "--season", "2024", "--runs", "50", "--out", str(tmp_path)]
    assert main(args) == EXIT_OK
    report = (tmp_path / "backtest.md").read_text(encoding="utf-8")
    assert "Bahrain Grand Prix 2024" in report
    assert "202421" in report  # São Paulo skipped: wet
    assert is_png(tmp_path / "backtest_races.png")
    assert b"\r\n" not in (tmp_path / "backtest.md").read_bytes()


def test_race_craft_command(db: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--db", db, "race-craft", "--runs", "10", "--out", str(tmp_path)]) == EXIT_OK
    assert "Best:" in capsys.readouterr().out
    assert "порог обгона" in (tmp_path / "race_craft.md").read_text(encoding="utf-8")

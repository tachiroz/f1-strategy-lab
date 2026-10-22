"""Command line entry point: ``python -m f1lab.sim <command>``.

Commands:
    race        simulate a race with the strategies actually run
    compare     compare strategies of one driver (the actual one comes first)
    backtest    score past races out of sample and write docs/sim
    race-craft  grid-search the overtaking / dirty-air parameters (calibration seasons)

Examples:
    python -m f1lab.sim race --season 2025 --round 4
    python -m f1lab.sim compare --season 2025 --round 4 --driver piastri
        --strategy M-18-H --strategy S-15-H-38-M      (one line)
    python -m f1lab.sim backtest
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from f1lab.config import (
    BACKTEST_SEASONS,
    CALIBRATION_SEASONS,
    RACE_CRAFT_DIRTY_AIR_PENALTIES_S,
    RACE_CRAFT_OVERTAKE_DELTAS_S,
    RACE_CRAFT_SEARCH_RUNS,
    SIM_REPORT_DIR,
    SIM_RUNS,
    get_db_path,
)
from f1lab.console import tolerate_console_encoding
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.ingest.transform import race_id_for
from f1lab.markdown import markdown_table
from f1lab.models.degradation import CircuitModel
from f1lab.sim.backtest import (
    Backtest,
    backtest,
    best_race_craft,
    prepare_races,
    search_race_craft,
    season_race_ids,
)
from f1lab.sim.calibration import Calibration, calibrate, load_history
from f1lab.sim.engine import SimulationParams, simulate
from f1lab.sim.montecarlo import compare_strategies, summarise
from f1lab.sim.plots import (
    pick_showcase,
    plot_backtest_races,
    plot_backtest_scores,
    plot_strategy_comparison,
)
from f1lab.sim.setup import SetupError, race_setup
from f1lab.sim.strategy import StrategyError, parse_strategy, validate_strategy

EXIT_OK = 0
EXIT_USAGE = 2
BACKTEST_FILE = "backtest.md"
RACE_CRAFT_FILE = "race_craft.md"
PERCENT = "{:.0%}".format


def _calibrated(engine: Engine) -> tuple[Calibration, dict[str, CircuitModel]]:
    """Calibrate on ``CALIBRATION_SEASONS``."""
    return calibrate(load_history(engine, CALIBRATION_SEASONS))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _sample_note(season: int) -> str:
    if season in CALIBRATION_SEASONS:
        return "Внимание: сезон входит в калибровку, результат в выборке (in-sample)."
    return "Сезон не входит в калибровку: честный прогноз вне выборки."


def cmd_race(engine: Engine, args: argparse.Namespace) -> int:
    """Print the outcome distribution of every driver with the actual strategies."""
    calibration, models = _calibrated(engine)
    setup = race_setup(engine, race_id_for(args.season, args.round), calibration, models)
    table = summarise(simulate(setup, SimulationParams(runs=args.runs)))
    table.insert(0, "strategy", [setup.strategies[d].notation() for d in table.index])
    shown = table[["strategy", "mean_position", "p_win", "p_podium", "p_points", "p_retire"]]
    print(f"{setup.race_name}: {args.runs} прогонов. {_sample_note(args.season)}")
    print(
        shown.to_string(
            formatters={
                "mean_position": "{:.2f}".format,
                **dict.fromkeys(["p_win", "p_podium", "p_points", "p_retire"], PERCENT),
            }
        )
    )
    return EXIT_OK


def cmd_compare(engine: Engine, args: argparse.Namespace) -> int:
    """Compare strategies of one driver against the same field."""
    calibration, models = _calibrated(engine)
    setup = race_setup(engine, race_id_for(args.season, args.round), calibration, models)
    if args.driver not in setup.drivers:
        print(
            f"error: {args.driver} did not start; drivers: {', '.join(setup.drivers)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    actual = replace(setup.strategies[args.driver], label="фактическая")
    plans = [parse_strategy(text) for text in args.strategy]
    for plan in plans:
        validate_strategy(plan, setup.race_laps)
    table = compare_strategies(
        setup, args.driver, [actual, *plans], SimulationParams(runs=args.runs)
    )
    print(f"{setup.race_name}, {args.driver}: {args.runs} прогонов. {_sample_note(args.season)}")
    for row in table.itertuples(index=False):
        print(
            f"  {row.strategy:>14} {row.notation:<16} позиция {row.mean_position:5.2f} "
            f"[{row.mean_low:.2f}; {row.mean_high:.2f}]  подиум {row.p_podium:4.0%} "
            f"очки {row.p_points:4.0%}  разница {row.delta_vs_first:+.2f} "
            f"[{row.delta_low:+.2f}; {row.delta_high:+.2f}]"
        )
    if args.chart:
        title = f"{setup.race_name}: стратегии {args.driver}"
        plot_strategy_comparison(table, title, args.chart)
        print(f"Chart: {args.chart}")
    return EXIT_OK


def render_backtest(result: Backtest, params: SimulationParams, seasons: Sequence[int]) -> str:
    """Generated Markdown of a backtest."""
    overall = result.overall()
    summary = result.summary().drop(columns="race_id")
    skipped = pd.DataFrame(
        [{"race_id": race_id, "причина": reason} for race_id, reason in result.skipped.items()]
    )
    lines = [
        "# Симулятор: бэктест",
        "",
        "> Сгенерировано командой `python -m f1lab.sim backtest`, вручную не редактировать.",
        "> Метод и допущения: [../assumptions.md](../assumptions.md).",
        "",
        f"Сезоны теста: {', '.join(map(str, seasons))}. Калибровка: "
        f"{', '.join(map(str, CALIBRATION_SEASONS))}. Прогонов на гонку: {params.runs}, "
        f"seed {params.seed}. Обгон: преимущество от {params.overtake_delta_s} с/круг, "
        f"грязный воздух {params.dirty_air_penalty_s} с/круг.",
        "",
        "Для каждой сухой гонки симулятор знает квалификацию, решётку и стратегии, которые пилоты "
        "реально выбрали. Сравнивается средняя позиция в симуляции с реальным финишем "
        "классифицированных пилотов; базовая модель - «финиш = позиция на решётке».",
        "",
        "## Итог",
        "",
        markdown_table(
            pd.DataFrame(
                [
                    {
                        "модель": "симулятор",
                        "Spearman": overall["spearman"],
                        "MAE, позиций": overall["mae"],
                    },
                    {
                        "модель": "финиш = решётка",
                        "Spearman": overall["grid_spearman"],
                        "MAE, позиций": overall["grid_mae"],
                    },
                ]
            )
        ),
        "",
        f"Гонок: {int(overall['races'])}; симулятор точнее решётки по MAE в "
        f"{int(overall['races_better_than_grid'])}.",
        "",
        "![Бэктест трёх гонок](backtest_races.png)",
        "",
        "![Ошибка по гонкам](backtest_scores.png)",
        "",
        "## По гонкам",
        "",
        markdown_table(summary),
        "",
    ]
    if not skipped.empty:
        lines += ["## Пропущенные гонки", "", markdown_table(skipped), ""]
    return "\n".join(lines)


def cmd_backtest(engine: Engine, args: argparse.Namespace) -> int:
    """Score the test seasons out of sample and write the report."""
    calibration, models = _calibrated(engine)
    seasons = args.season or list(BACKTEST_SEASONS)
    prepared, skipped = prepare_races(engine, season_race_ids(engine, seasons), calibration, models)
    params = SimulationParams(runs=args.runs)
    result = backtest(prepared, params, skipped)
    out: Path = args.out
    plot_backtest_races(pick_showcase(result), out / "backtest_races.png")
    plot_backtest_scores(result, out / "backtest_scores.png")
    _write(out / BACKTEST_FILE, render_backtest(result, params, seasons))
    overall = result.overall()
    print(f"Report: {out}")
    print(
        f"{int(overall['races'])} races, skipped {len(skipped)}: "
        f"Spearman {overall['spearman']:.3f} (grid {overall['grid_spearman']:.3f}), "
        f"MAE {overall['mae']:.2f} (grid {overall['grid_mae']:.2f})"
    )
    return EXIT_OK


def cmd_race_craft(engine: Engine, args: argparse.Namespace) -> int:
    """Grid-search overtaking and dirty air on the calibration seasons and write the table."""
    calibration, models = _calibrated(engine)
    prepared, _ = prepare_races(
        engine, season_race_ids(engine, CALIBRATION_SEASONS), calibration, models
    )
    search = search_race_craft(
        prepared,
        RACE_CRAFT_OVERTAKE_DELTAS_S,
        RACE_CRAFT_DIRTY_AIR_PENALTIES_S,
        SimulationParams(runs=args.runs),
    )
    delta, penalty = best_race_craft(search)
    content = "\n".join(
        [
            "# Симулятор: подбор параметров обгона",
            "",
            "> Сгенерировано командой `python -m f1lab.sim race-craft`, вручную не редактировать.",
            "",
            f"Гонки калибровки ({', '.join(map(str, CALIBRATION_SEASONS))}), {args.runs} прогонов "
            "на гонку, диапазоны заданы заранее как физически правдоподобные. Лучшая пара по MAE: "
            f"порог обгона **{delta} с/круг**, грязный воздух **{penalty} с/круг**.",
            "",
            markdown_table(search),
            "",
        ]
    )
    _write(args.out / RACE_CRAFT_FILE, content)
    print(search.head(5).round(3).to_string(index=False))
    print(f"Best: OVERTAKE_DELTA_S = {delta}, DIRTY_AIR_PENALTY_S = {penalty} (set them in config)")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(prog="python -m f1lab.sim")
    parser.add_argument("--db", type=Path, help="SQLite file (default: <data dir>/f1lab.sqlite)")
    commands = parser.add_subparsers(dest="command", required=True)

    race = commands.add_parser("race", help="simulate a race with the actual strategies")
    compare = commands.add_parser("compare", help="compare strategies of one driver")
    for sub in (race, compare):
        sub.add_argument("--season", type=int, required=True)
        sub.add_argument("--round", type=int, required=True)
        sub.add_argument("--runs", type=int, default=SIM_RUNS)
    compare.add_argument("--driver", required=True, help="driver id, e.g. max_verstappen")
    compare.add_argument(
        "--strategy", action="append", required=True, help="e.g. M-18-H or S3-15-H-38-M; repeatable"
    )
    compare.add_argument("--chart", type=Path, help="write a PNG chart here")

    test = commands.add_parser("backtest", help="score past races out of sample")
    test.add_argument("--season", type=int, action="append", help="test season, repeatable")
    test.add_argument("--runs", type=int, default=SIM_RUNS)
    test.add_argument("--out", type=Path, default=SIM_REPORT_DIR)

    craft = commands.add_parser("race-craft", help="grid-search overtaking / dirty air")
    craft.add_argument("--runs", type=int, default=RACE_CRAFT_SEARCH_RUNS)
    craft.add_argument("--out", type=Path, default=SIM_REPORT_DIR)
    return parser


COMMANDS = {
    "race": cmd_race,
    "compare": cmd_compare,
    "backtest": cmd_backtest,
    "race-craft": cmd_race_craft,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run a subcommand and return the process exit code."""
    args = build_parser().parse_args(argv)
    tolerate_console_encoding()
    engine = create_sqlite_engine(args.db or get_db_path())
    init_db(engine)
    try:
        return COMMANDS[args.command](engine, args)
    except (SetupError, StrategyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line entry point: ``python -m f1lab.models`` builds the tyre model report.

It loads the laps, applies the clean-lap filters, evaluates the model on the
test seasons, fits the final per-circuit parameters on all seasons and writes
charts, a parameters CSV and a generated ``results.md`` to the report directory.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from f1lab.config import MODEL_REPORT_DIR, TEST_SEASONS, TRAIN_SEASONS, get_db_path
from f1lab.db.engine import create_sqlite_engine, init_db
from f1lab.models.degradation import fit_circuits, parameters_table
from f1lab.models.evaluate import FINAL_VARIANT, Evaluation, evaluate
from f1lab.models.filters import annotate_laps, clean_laps, exclusion_summary
from f1lab.models.laps import load_model_laps, load_race_control, load_rainfall
from f1lab.models.plots import (
    pick_showcase,
    plot_actual_vs_model,
    plot_degradation,
    plot_mae_by_circuit,
    plot_mae_overall,
)

PARAMS_FILE = "degradation_params.csv"
RESULTS_FILE = "results.md"
EXIT_OK = 0
EXIT_NO_DATA = 1


def _markdown_table(frame: pd.DataFrame, float_format: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub Markdown table (no extra dependency)."""

    def cell(value: object) -> str:
        if isinstance(value, float):
            return "—" if pd.isna(value) else float_format.format(value)
        return str(value)

    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def render_results(evaluation: Evaluation, summary: pd.Series, params: pd.DataFrame) -> str:
    """Return the generated Markdown with all result tables."""
    seasons = ", ".join(map(str, evaluation.train_seasons))
    tests = ", ".join(map(str, evaluation.test_seasons))
    exclusions = summary.rename_axis("причина").reset_index(name="кругов")
    exclusions["доля"] = (exclusions["кругов"] / exclusions["кругов"].sum()).map("{:.1%}".format)
    overall = evaluation.mae().reset_index(names="вариант").rename(columns={"mae_s": "MAE, с"})
    by_compound = evaluation.mae(by="compound").reset_index(names="состав")
    by_circuit = evaluation.mae(by="circuit_id").reset_index(names="трасса")
    table = params.assign(
        interval=params["degradation_low"].map("{:.3f}".format)
        + " … "
        + params["degradation_high"].map("{:.3f}".format)
    )[
        [
            "circuit_id",
            "compound",
            "laps",
            "degradation_s_per_lap",
            "interval",
            "max_tyre_age",
            "offset_s",
            "fuel_s_per_lap",
        ]
    ].rename(
        columns={
            "circuit_id": "трасса",
            "compound": "состав",
            "laps": "кругов",
            "degradation_s_per_lap": "деградация, с/круг",
            "interval": "95% интервал",
            "max_tyre_age": "макс. возраст шины",
            "offset_s": "сдвиг к эталону, с",
            "fuel_s_per_lap": "топливо, с/круг",
        }
    )
    return "\n".join(
        [
            "# Модель шин: результаты",
            "",
            "> Сгенерировано командой `python -m f1lab.models`, вручную не редактировать.",
            "> Метод и выводы: [tyre_model.md](tyre_model.md).",
            "",
            f"Обучение: {seasons}. Тест: {tests}. Кругов в тесте: {len(evaluation.predictions)}, "
            f"покрытие {evaluation.coverage:.1%} (остальные круги на трассах или составах, "
            "которых нет в обучении).",
            "",
            "## Фильтр кругов",
            "",
            _markdown_table(exclusions),
            "",
            "## MAE на отложенных гонках",
            "",
            f"Итоговый вариант: **{FINAL_VARIANT.value}**. Остальные строки - абляция, "
            "которая его обосновывает.",
            "",
            _markdown_table(overall),
            "",
            "### По составам",
            "",
            _markdown_table(by_compound),
            "",
            "### По трассам",
            "",
            _markdown_table(by_circuit),
            "",
            "## Параметры по трассам (все сезоны, итоговый вариант)",
            "",
            "Деградация сжата к общему наклону состава; дальше максимального возраста шины "
            "износ не экстраполируется. Сдвиг состава считается относительно эталонного "
            "(MEDIUM, если он есть на трассе).",
            "",
            _markdown_table(table),
            "",
        ]
    )


def build_report(
    annotated: pd.DataFrame,
    out_dir: Path,
    train_seasons: tuple[int, ...] = TRAIN_SEASONS,
    test_seasons: tuple[int, ...] = TEST_SEASONS,
) -> Evaluation:
    """Evaluate the model, fit final parameters and write charts, CSV and Markdown.

    Args:
        annotated: Laps with exclusion reasons (``f1lab.models.filters.annotate_laps``).
        out_dir: Report directory (created if missing).
        train_seasons: Seasons used to fit the evaluated models.
        test_seasons: Seasons the models are scored on.

    Returns:
        The evaluation, for printing a summary.
    """
    clean = clean_laps(annotated)
    evaluation = evaluate(clean, train_seasons, test_seasons)
    final_models = fit_circuits(
        clean[clean["season"].isin({*train_seasons, *test_seasons})], pooled=True
    )
    params = parameters_table(final_models.values())

    out_dir.mkdir(parents=True, exist_ok=True)
    # LF everywhere: the report is committed and must not depend on the OS it was built on.
    params.to_csv(out_dir / PARAMS_FILE, index=False, float_format="%.4f", lineterminator="\n")
    if not evaluation.predictions.empty:
        plot_actual_vs_model(evaluation, pick_showcase(evaluation), out_dir / "actual_vs_model.png")
        plot_mae_overall(evaluation, out_dir / "mae_overall.png")
        plot_mae_by_circuit(evaluation, out_dir / "mae_by_circuit.png")
    if final_models:
        plot_degradation(final_models.values(), out_dir / "degradation.png")
    (out_dir / RESULTS_FILE).write_text(
        render_results(evaluation, exclusion_summary(annotated), params),
        encoding="utf-8",
        newline="\n",
    )
    return evaluation


def main(argv: Sequence[str] | None = None) -> int:
    """Build the tyre model report from the database and print the headline numbers."""
    parser = argparse.ArgumentParser(prog="python -m f1lab.models")
    parser.add_argument("--db", type=Path, help="SQLite file (default: <data dir>/f1lab.sqlite)")
    parser.add_argument("--out", type=Path, default=MODEL_REPORT_DIR, help="report directory")
    parser.add_argument("--train-season", type=int, action="append", dest="train")
    parser.add_argument("--test-season", type=int, action="append", dest="test")
    args = parser.parse_args(argv)
    train = tuple(args.train or TRAIN_SEASONS)
    test = tuple(args.test or TEST_SEASONS)

    engine = create_sqlite_engine(args.db or get_db_path())
    init_db(engine)
    laps = load_model_laps(engine, sorted({*train, *test}))
    if laps.empty:
        print(
            "error: no laps for these seasons; load them with python -m f1lab.ingest",
            file=sys.stderr,
        )
        return EXIT_NO_DATA
    race_ids = laps["race_id"].unique().tolist()
    annotated = annotate_laps(
        laps, load_race_control(engine, race_ids), load_rainfall(engine, race_ids)
    )
    evaluation = build_report(annotated, args.out, train, test)
    print(f"Report: {args.out}")
    print(evaluation.mae().round(3).to_string())
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

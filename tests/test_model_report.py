"""Tests for the tyre model charts and the report command."""

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine

from f1lab.models.__main__ import EXIT_NO_DATA, EXIT_OK, build_report, main
from f1lab.models.degradation import fit_circuits
from f1lab.models.evaluate import FINAL_VARIANT, Evaluation, evaluate
from f1lab.models.plots import (
    pick_showcase,
    plot_actual_vs_model,
    plot_degradation,
    plot_mae_by_circuit,
    plot_mae_overall,
)

PNG_SIGNATURE = b"\x89PNG"


@pytest.fixture
def evaluation(synthetic_laps: pd.DataFrame) -> Evaluation:
    return evaluate(synthetic_laps, train_seasons=(2023, 2024), test_seasons=(2025,))


def is_png(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:4] == PNG_SIGNATURE


def test_pick_showcase(evaluation: Evaluation) -> None:
    picks = pick_showcase(evaluation)
    assert picks == [(202501, picks[0][1])]  # one test race in the synthetic data
    assert picks[0][1].startswith("driver_")


def test_pick_showcase_of_empty_evaluation(synthetic_laps: pd.DataFrame) -> None:
    assert pick_showcase(evaluate(synthetic_laps, test_seasons=(2030,))) == []


def test_charts_are_written(
    evaluation: Evaluation, synthetic_laps: pd.DataFrame, tmp_path: Path
) -> None:
    paths = [
        plot_actual_vs_model(evaluation, pick_showcase(evaluation), tmp_path / "a.png"),
        plot_mae_overall(evaluation, tmp_path / "b.png"),
        plot_mae_by_circuit(evaluation, tmp_path / "c.png"),
        plot_degradation(fit_circuits(synthetic_laps).values(), tmp_path / "d.png"),
    ]
    assert all(is_png(path) for path in paths)


def test_build_report(synthetic_laps: pd.DataFrame, tmp_path: Path) -> None:
    annotated = synthetic_laps.assign(exclusion=pd.Series(pd.NA, dtype="string"))
    build_report(annotated, tmp_path, train_seasons=(2023, 2024), test_seasons=(2025,))
    for name in ("actual_vs_model.png", "mae_overall.png", "mae_by_circuit.png", "degradation.png"):
        assert is_png(tmp_path / name), name
    params = pd.read_csv(tmp_path / "degradation_params.csv")
    assert set(params["compound"]) == {"SOFT", "MEDIUM", "HARD"}
    results = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "## MAE на отложенных гонках" in results
    assert FINAL_VARIANT.value in results
    assert "макс. возраст шины" in results
    for name in ("results.md", "degradation_params.csv"):
        assert b"\r\n" not in (tmp_path / name).read_bytes(), name  # same bytes on every OS


def test_cli_on_recorded_races(loaded: Engine, tmp_path: Path) -> None:
    db = str(loaded.url.database)
    out = tmp_path / "report"
    args = ["--db", db, "--out", str(out), "--train-season", "2024", "--test-season", "2024"]
    assert main(args) == EXIT_OK
    assert (out / "results.md").is_file()
    assert is_png(out / "degradation.png")


def test_cli_without_data(loaded: Engine, tmp_path: Path) -> None:
    db = str(loaded.url.database)
    args = ["--db", db, "--out", str(tmp_path), "--train-season", "2019", "--test-season", "2020"]
    assert main(args) == EXIT_NO_DATA

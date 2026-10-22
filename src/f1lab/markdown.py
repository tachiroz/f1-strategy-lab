"""Plain GitHub Markdown tables for generated reports (no extra dependency)."""

import pandas as pd


def markdown_table(frame: pd.DataFrame, float_format: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub Markdown table (no extra dependency)."""

    def cell(value: object) -> str:
        if isinstance(value, float):
            return "—" if pd.isna(value) else float_format.format(value)
        return str(value)

    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])

"""Apply a compiled regex to one column on a DataFrame copy (never mutates stored uploads)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import regex
from django.conf import settings

FLAG_MAP: dict[str, int] = {
    "IGNORECASE": regex.IGNORECASE,
    "MULTILINE": regex.MULTILINE,
    "DOTALL": regex.DOTALL,
    "VERBOSE": regex.VERBOSE,
}

NESTED_QUANTIFIER_RE = regex.compile(
    r"\((?:[^()\\]|\\.)+[+*][^()]*\)[+*{]"
)
EMPTY_ALTERNATION_RE = regex.compile(r"\(\||\|\)")
FORMULA_PREFIXES = ("=", "+", "-", "@")


def compile_regex(pattern: str, flag_names: list[str]) -> regex.Pattern[str]:
    validate_regex_pattern(pattern)
    bits = 0
    for name in flag_names:
        if name not in FLAG_MAP:
            raise ValueError(f"Unknown regex flag: {name}")
        bits |= FLAG_MAP[name]
    return regex.compile(pattern, bits)


def validate_regex_pattern(pattern: str) -> None:
    if len(pattern) > settings.MAX_REGEX_PATTERN_LENGTH:
        raise ValueError(
            f"Regular expression is too long. Limit: {settings.MAX_REGEX_PATTERN_LENGTH} characters."
        )
    if NESTED_QUANTIFIER_RE.search(pattern):
        raise ValueError(
            "Regular expression is too risky: nested quantifiers can make matching extremely slow."
        )
    if EMPTY_ALTERNATION_RE.search(pattern):
        raise ValueError(
            "Regular expression is too broad: empty alternatives can match almost anything."
        )


def apply_regex_to_column(
    df: pd.DataFrame,
    column: str,
    compiled: regex.Pattern[str],
    replacement: str,
) -> tuple[pd.DataFrame, int, int]:
    """
    Return (transformed_df, matched_cells_count, changed_rows_count).
    matched_cells_count: non-null cells where search finds at least one match.
    changed_rows_count: rows where the string value of the cell changed after sub.
    """
    df_work = df.copy()
    series = df_work[column]

    matched_cells = 0
    changed_rows = 0
    new_values: list[Any] = []

    for i in range(len(series)):
        val = series.iloc[i]
        if pd.isna(val):
            new_values.append(val)
            continue
        s = str(val)
        if len(s) > settings.MAX_CELL_CHARS:
            raise ValueError(
                f"Column '{column}' contains a cell longer than {settings.MAX_CELL_CHARS} characters. "
                "Shorten that cell or raise MAX_CELL_CHARS only if your deployment can process it safely."
            )
        try:
            if compiled.search(s, timeout=settings.REGEX_TIMEOUT_SECONDS):
                matched_cells += 1
            new_s = compiled.sub(
                lambda _match: replacement,
                s,
                timeout=settings.REGEX_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise ValueError(
                "Regular expression exceeded the execution time limit. Review or simplify it."
            ) from exc
        if new_s != s:
            changed_rows += 1
        new_values.append(new_s)

    df_work[column] = new_values
    return df_work, matched_cells, changed_rows


def sanitize_for_csv_export(df: pd.DataFrame) -> pd.DataFrame:
    """Prevent spreadsheet formula execution when users open exported CSVs."""
    return df.map(_escape_formula_cell)


def _escape_formula_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value and value.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + value
    return value

"""Load tabular uploads with pandas and build API-friendly structures."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pandas as pd
from django.conf import settings

ALLOWED_EXTENSIONS = frozenset({".csv", ".xlsx"})


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Please upload a .csv or .xlsx file."
        )
    return ext


def read_uploaded_tabular(uploaded_file, ext: str) -> pd.DataFrame:
    if uploaded_file.size and uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        max_mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise ValueError(f"The uploaded file is too large. Limit: {max_mb:.1f} MB.")

    raw = uploaded_file.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")
    buffer = io.BytesIO(raw)
    try:
        if ext == ".csv":
            df = pd.read_csv(
                buffer,
                encoding="utf-8-sig",
                nrows=settings.MAX_UPLOAD_ROWS + 1,
            )
        else:
            df = pd.read_excel(buffer, engine="openpyxl", nrows=settings.MAX_UPLOAD_ROWS + 1)
    except Exception as exc:
        raise ValueError(
            "Could not read the file. Make sure it is a valid CSV or XLSX."
        ) from exc
    df.columns = df.columns.map(lambda c: str(c).strip())
    validate_shape(df)
    return df


def assert_non_empty(df: pd.DataFrame) -> None:
    if len(df.columns) == 0:
        raise ValueError("The file has no columns.")
    if df.empty:
        raise ValueError("The file contains no data rows.")


def validate_shape(df: pd.DataFrame) -> None:
    if len(df) > settings.MAX_UPLOAD_ROWS:
        raise ValueError(f"The file has too many rows. Limit: {settings.MAX_UPLOAD_ROWS}.")
    if len(df.columns) > settings.MAX_UPLOAD_COLUMNS:
        raise ValueError(
            f"The file has too many columns. Limit: {settings.MAX_UPLOAD_COLUMNS}."
        )
    blank_columns = [i + 1 for i, name in enumerate(df.columns) if not str(name).strip()]
    if blank_columns:
        raise ValueError("The file contains blank column names.")
    duplicates = df.columns[df.columns.duplicated()].tolist()
    columns = [str(c) for c in df.columns]
    mangled_duplicates = []
    for name in columns:
        match = re.fullmatch(r"(.+)\.\d+", name)
        if match and match.group(1) in columns:
            mangled_duplicates.append(match.group(1))
    if duplicates or mangled_duplicates:
        joined = ", ".join(sorted(set(map(str, duplicates + mangled_duplicates)))[:5])
        raise ValueError(f"The file contains duplicate column names: {joined}.")


def long_text_warnings(df: pd.DataFrame) -> list[str]:
    long_cells = 0
    for column in df.columns:
        series = df[column].dropna()
        long_cells += sum(len(str(value)) > settings.MAX_CELL_CHARS for value in series)
    if not long_cells:
        return []
    return [
        f"{long_cells} cell(s) exceed {settings.MAX_CELL_CHARS} characters. "
        "They are preserved, but regex apply may reject that target column for safety."
    ]


def has_non_empty_values(series: pd.Series) -> bool:
    for value in series:
        if pd.isna(value):
            continue
        if str(value).strip():
            return True
    return False


def preview_records(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    chunk = df.head(limit)
    return json.loads(chunk.to_json(orient="records", date_format="iso"))


def text_column_names(df: pd.DataFrame) -> list[str]:
    subset = df.select_dtypes(include=["object", "string"])
    return [str(c) for c in subset.columns]

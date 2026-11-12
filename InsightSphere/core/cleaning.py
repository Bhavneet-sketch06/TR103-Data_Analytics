"""
core/cleaning.py

Safe, automatic preprocessing for any uploaded dataset.

clean_dataset() never mutates the dataframe passed in — it works on a copy and
returns a NEW dataframe plus a report describing exactly what was changed, with
counts derived from the actual data (never fabricated).

Missing numbers are deliberately left missing: filling revenue or profit with a
median would invent sales that never happened. Pandas aggregations skip NaN,
and the report tells the user how many cells are still empty.
"""

import re

import pandas as pd


# ==========================================================
# MAIN CLEANING ENTRY POINT
# ==========================================================

def clean_dataset(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Performs SAFE, automatic preprocessing on a raw dataframe.

    Returns (cleaned_df, report). raw_df is never modified in place —
    a single .copy() is made up front and all further operations
    happen on that copy.
    """
    df = raw_df.copy()

    report = {
        "original_rows": len(raw_df),
        "original_cols": raw_df.shape[1],
        "original_missing_values": int(raw_df.isna().sum().sum()),
        "blank_rows_removed": 0,
        "duplicates_removed": 0,
        "missing_values_handled": 0,
        "columns_type_converted": 0,
        "invalid_records_handled": 0,
    }

    df, report = _remove_blank_rows(df, report)
    df, report = _remove_duplicates(df, report)
    df, report = _standardize_text_columns(df, report)
    df, report = _convert_obvious_types(df, report)
    df, report = _handle_missing_values(df, report)

    report["cleaned_rows"] = len(df)
    report["cleaned_cols"] = df.shape[1]
    report["final_missing_values"] = int(df.isna().sum().sum())

    return df, report


# ==========================================================
# A. DUPLICATE ROWS
# ==========================================================

def _remove_blank_rows(df: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, dict]:
    """Rows with no values at all (spacer lines in exports) aren't duplicates; count them apart."""
    blank = df.isna() | df.astype(str).apply(lambda col: col.str.strip() == "")
    keep = ~blank.all(axis=1)
    report["blank_rows_removed"] = int((~keep).sum())
    return df[keep], report


def _remove_duplicates(df: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, dict]:
    before = len(df)
    df = df.drop_duplicates()
    report["duplicates_removed"] = before - len(df)
    return df, report


# ==========================================================
# B. STANDARDIZE CATEGORICAL / TEXT VALUES
# ==========================================================

def _standardize_text_columns(df: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, dict]:
    text_cols = df.select_dtypes(include=["object", "string"]).columns

    for col in text_cols:
        series = df[col]
        # Strip whitespace on non-null values only; leave NaN as NaN.
        df[col] = series.where(series.isna(), series.astype(str).str.strip())

    # Normalize case-inconsistent duplicate categories (e.g. "West" / "west" / "WEST")
    # ONLY on columns that behave like low-cardinality categories, so we never
    # touch free-text fields like descriptions or names.
    for col in text_cols:
        series = df[col]
        non_null = series.dropna().astype(str)
        if non_null.empty:
            continue

        n_unique = non_null.nunique()
        is_low_cardinality = n_unique <= 50 and n_unique < max(1, len(non_null) * 0.5)
        if not is_low_cardinality:
            continue

        lower_groups = non_null.groupby(non_null.str.lower())
        if lower_groups.ngroups == n_unique:
            continue

        canonical_map = {}
        for _, group in lower_groups:
            canonical = group.mode().iloc[0]  # most frequent casing wins
            for val in group.unique():
                canonical_map[val] = canonical

        df[col] = series.map(lambda v: canonical_map.get(v, v) if pd.notna(v) else v)

    return df, report


# ==========================================================
# C. CONVERT OBVIOUS DATA TYPES
# ==========================================================

_NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})")


def detect_dayfirst(series: pd.Series) -> bool | None:
    """
    For dates like 07/04/2023: True when the column is day-first (some first
    numbers are above 12), False when it's month-first (some second numbers
    are above 12), None when the column doesn't say (or isn't that format).
    Looking at the whole column matters: pandas otherwise guesses from the
    first value and silently drops every date that doesn't fit the guess.
    """
    parts = series.dropna().astype(str).str.extract(_NUMERIC_DATE)
    if parts.empty or parts[0].isna().all():
        return None
    first, second = pd.to_numeric(parts[0], errors="coerce"), pd.to_numeric(parts[1], errors="coerce")
    if (first > 12).any() and not (second > 12).any():
        return True
    if (second > 12).any() and not (first > 12).any():
        return False
    return None


def parse_dates(series: pd.Series) -> pd.Series:
    """Parses dates (day-first or month-first, detected), falling back to per-value parsing."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    dayfirst = detect_dayfirst(series)
    if dayfirst is not None:
        return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=dayfirst)
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().sum() < 0.8 * series.notna().sum():
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    return parsed


def _convert_obvious_types(df: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, dict]:
    type_converted_cols = 0
    bool_map = {"true": True, "false": False, "yes": True, "no": False}

    for col in df.columns:
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue

        non_null = df[col].dropna()
        if non_null.empty:
            continue

        lowered = non_null.astype(str).str.strip().str.lower()

        # Boolean-like columns
        if set(lowered.unique()).issubset(set(bool_map.keys())):
            df[col] = df[col].astype(str).str.strip().str.lower().map(bool_map)
            type_converted_cols += 1
            continue

        # Date-like columns (only attempt when the name hints at a date,
        # and only commit if the vast majority of values actually parse)
        if "date" in str(col).lower() or "time" in str(col).lower():
            converted = parse_dates(df[col])
            valid_ratio = converted.notna().sum() / max(len(non_null), 1)
            if valid_ratio >= 0.8:
                newly_invalid = int(converted.isna().sum() - df[col].isna().sum())
                report["invalid_records_handled"] += max(newly_invalid, 0)
                df[col] = converted
                type_converted_cols += 1
                continue

        # Numeric-like columns, including "$1,234.50" and "12%"
        cleaned_values = (
            non_null.astype(str)
            .str.replace(r"[,$€£₹\s]", "", regex=True)
            .str.rstrip("%")
        )
        numeric_attempt = pd.to_numeric(cleaned_values, errors="coerce")
        valid_ratio = numeric_attempt.notna().sum() / len(non_null)
        if valid_ratio >= 0.95:
            full_cleaned = (
                df[col].astype(str)
                .str.replace(r"[,$€£₹\s]", "", regex=True)
                .str.rstrip("%")
            )
            numeric_full = pd.to_numeric(full_cleaned, errors="coerce")
            newly_invalid = int(numeric_full.isna().sum() - df[col].isna().sum())
            report["invalid_records_handled"] += max(newly_invalid, 0)
            df[col] = numeric_full
            type_converted_cols += 1

    report["columns_type_converted"] = type_converted_cols
    return df, report


# ==========================================================
# D. HANDLE MISSING VALUES (COLUMN-AWARE)
# ==========================================================

def _handle_missing_values(df: pd.DataFrame, report: dict) -> tuple[pd.DataFrame, dict]:
    """
    Text categories get an explicit "Unknown" bucket so they still show up in
    breakdowns. Numbers, dates and booleans stay missing — they are never guessed.
    """
    missing_before = int(df.isna().sum().sum())

    for col in df.columns:
        if df[col].isna().sum() == 0:
            continue
        series = df[col]
        if pd.api.types.is_bool_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue
        if pd.api.types.is_numeric_dtype(series):
            continue
        df[col] = series.fillna("Unknown")

    missing_after = int(df.isna().sum().sum())
    report["missing_values_handled"] = max(missing_before - missing_after, 0)
    return df, report

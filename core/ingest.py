"""
Ingest pipeline: file bytes -> raw frame -> cleaned frame -> canonical frame.

    read_file()      CSV/XLSX with encoding fallback
    clean_dataset()  core/cleaning.py
    apply_mapping()  rename source columns to canonical keys
    derive()         typed columns + derived fields (profit from cost, ship_days, ...)

The bundled sample goes through exactly the same steps as an upload.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from core.cleaning import clean_dataset, parse_dates
from core.schema import FIELD_BY_KEY, suggest_mapping

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / "data" / "Sample - Superstore.csv"
SAMPLE_NAME = "Sample - Superstore.csv"
UPLOAD_DIR = ROOT / "data" / "uploads"

ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "latin1"]


@dataclass
class Dataset:
    df: pd.DataFrame            # canonical columns + any unmapped extras
    name: str
    digest: str                 # sha1 of the raw file (+ mapping), used as cache/URL key
    is_sample: bool
    mapping: dict
    report: dict = field(default_factory=dict)

    @property
    def date_span(self) -> str:
        dates = self.df["order_date"]
        return f"{dates.min():%b %Y} – {dates.max():%b %Y}"


# ----------------------------------------------------------
# Reading
# ----------------------------------------------------------

def file_digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


def read_file(data: bytes, filename: str) -> tuple[pd.DataFrame, str]:
    """Returns (raw_df, encoding_or_format). Raises ValueError with a readable message."""
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(data))
        source = "Excel"
    else:
        df, source = None, None
        for encoding in ENCODINGS:
            try:
                df = pd.read_csv(io.BytesIO(data), encoding=encoding, sep=None, engine="python")
                source = encoding
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        if df is None:
            raise ValueError("This file couldn't be read as CSV (tried UTF-8, Windows-1252 and Latin-1).")
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise ValueError("The file is empty.")
    df.columns = [str(c).strip() for c in df.columns]
    return df, source


# ----------------------------------------------------------
# Mapping + derivation
# ----------------------------------------------------------

def apply_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Renames mapped source columns to canonical keys; keeps unmapped extras."""
    rename = {src: key for key, src in mapping.items() if src}
    out = df.rename(columns=rename)
    # Drop extras that would collide with a canonical name.
    out = out.loc[:, ~out.columns.duplicated()]
    return out


def derive(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Types canonical columns and adds derived fields. Rows without a valid order
    date or revenue are dropped (they can't be placed on a timeline or summed)
    and counted in the returned notes.
    """
    out = df.copy()
    notes = {"rows_dropped_no_date": 0, "rows_dropped_no_revenue": 0, "derived": []}

    for key in out.columns:
        spec = FIELD_BY_KEY.get(key)
        if spec is None:
            continue
        if spec.kind == "date":
            out[key] = parse_dates(out[key])
        elif spec.kind == "number":
            out[key] = pd.to_numeric(out[key], errors="coerce")
        else:
            col = out[key]
            if pd.api.types.is_float_dtype(col) and (col.dropna() % 1 == 0).all():
                col = col.astype("Int64")  # 1001.0 -> "1001" for numeric IDs
            out[key] = col.astype(str).where(col.notna(), "Unknown")

    before = len(out)
    out = out[out["order_date"].notna()]
    notes["rows_dropped_no_date"] = before - len(out)
    before = len(out)
    out = out[out["revenue"].notna()]
    notes["rows_dropped_no_revenue"] = before - len(out)

    if "discount" in out.columns and out["discount"].max(skipna=True) > 1:
        out["discount"] = out["discount"] / 100
        notes["derived"].append("Discount converted from percent to fraction")

    if "profit" not in out.columns and "cost" in out.columns:
        out["profit"] = out["revenue"] - out["cost"]
        notes["derived"].append("Profit = revenue − cost")

    if "ship_date" in out.columns:
        days = (out["ship_date"] - out["order_date"]).dt.days
        out["ship_days"] = days.where(days >= 0)
        notes["derived"].append("Ship days = ship date − order date")

    if "order_id" not in out.columns:
        # Without order IDs each line is treated as one order, so AOV still works.
        out["order_id"] = np.arange(len(out)).astype(str)
        notes["synthetic_order_id"] = True
        notes["derived"].append("Each row treated as one order (no Order ID mapped)")

    out["month"] = out["order_date"].dt.to_period("M").dt.to_timestamp()
    out = out.sort_values("order_date").reset_index(drop=True)
    return out, notes


# ----------------------------------------------------------
# Full pipeline (cached)
# ----------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=8)
def read_and_clean(data: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    raw, source = read_file(data, filename)
    cleaned, report = clean_dataset(raw)
    report["source_format"] = source
    return cleaned, report


@st.cache_data(show_spinner=False, max_entries=8)
def build(data: bytes, filename: str, mapping_json: str) -> tuple[pd.DataFrame, dict]:
    cleaned, report = read_and_clean(data, filename)
    mapping = json.loads(mapping_json)
    canonical = apply_mapping(cleaned, mapping)
    df, notes = derive(canonical)
    return df, {**report, **notes, "final_rows": len(df)}


def mapping_json(mapping: dict) -> str:
    return json.dumps({k: mapping.get(k) for k in sorted(mapping)}, sort_keys=True)


def load_dataset(data: bytes, filename: str, mapping: dict, *, is_sample: bool) -> Dataset:
    df, report = build(data, filename, mapping_json(mapping))
    return Dataset(
        df=df, name=filename, digest=file_digest(data), is_sample=is_sample,
        mapping=mapping, report=report,
    )


@st.cache_data(show_spinner=False)
def sample_bytes() -> bytes:
    return SAMPLE_PATH.read_bytes()


def load_sample() -> Dataset:
    data = sample_bytes()
    cleaned, _ = read_and_clean(data, SAMPLE_NAME)
    return load_dataset(data, SAMPLE_NAME, suggest_mapping(cleaned.columns), is_sample=True)


# ----------------------------------------------------------
# Upload persistence (so a page reload or shared link keeps the dataset)
# ----------------------------------------------------------

def save_upload(data: bytes, filename: str, mapping: dict) -> str:
    digest = file_digest(data)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / f"{digest}.bin").write_bytes(data)
    (UPLOAD_DIR / f"{digest}.json").write_text(
        json.dumps({"filename": filename, "mapping": mapping}), encoding="utf-8"
    )
    return digest


def load_upload(digest: str) -> Dataset | None:
    if not digest or not digest.isalnum():
        return None
    data_path = UPLOAD_DIR / f"{digest}.bin"
    meta_path = UPLOAD_DIR / f"{digest}.json"
    if not (data_path.exists() and meta_path.exists()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return load_dataset(data_path.read_bytes(), meta["filename"], meta["mapping"], is_sample=False)

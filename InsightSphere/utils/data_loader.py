"""
utils/data_loader.py

Centralized, single source of truth for InsightSphere's ACTIVE DATASET.

Every page must retrieve its working dataframe through get_active_dataset()
(or the convenience helpers below) instead of calling pd.read_csv() directly.
This guarantees that once a user uploads a dataset, every page uses it -- and
that no page silently falls back to the sample dataset while another page has
already switched to an uploaded one.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================================
# DEFAULT / FALLBACK DATASET
# ==========================================================

DEFAULT_DATASET_PATH = "data/Sample - Superstore.csv"
DEFAULT_DATASET_ENCODING = "latin1"
DEFAULT_DATASET_LABEL = "Sample - Superstore.csv"

# ==========================================================
# SESSION STATE KEYS (single canonical set, used everywhere)
# ==========================================================

SESSION_KEY_DATASET = "insightsphere_dataset"
SESSION_KEY_FILENAME = "insightsphere_dataset_filename"
SESSION_KEY_UPLOAD_TIME = "insightsphere_dataset_upload_time"
SESSION_KEY_CLEANING_REPORT = "insightsphere_cleaning_report"
SESSION_KEY_COMPATIBILITY = "insightsphere_prediction_compatibility"


@st.cache_data
def _load_default_dataset() -> pd.DataFrame:
    """Loads the bundled sample dataset. Cached so this only hits disk once."""
    return pd.read_csv(DEFAULT_DATASET_PATH, encoding=DEFAULT_DATASET_ENCODING)


def is_dataset_uploaded() -> bool:
    """True once a user has uploaded and cleaned a dataset this session."""
    return st.session_state.get(SESSION_KEY_DATASET) is not None


def get_active_dataset():
    """
    Central accessor for the ACTIVE DATASET.

    Returns:
        (df, is_uploaded, label)

        df          -- a fresh copy of the active dataframe (the uploaded +
                        cleaned dataset if one exists this session, otherwise
                        the bundled sample dataset).
        is_uploaded -- True if this is a user-uploaded dataset.
        label       -- display name (uploaded filename, or the sample
                        dataset's filename as a fallback).
    """
    uploaded_df = st.session_state.get(SESSION_KEY_DATASET)

    if uploaded_df is not None:
        label = st.session_state.get(SESSION_KEY_FILENAME, "Uploaded dataset")
        return uploaded_df.copy(), True, label

    default_df = _load_default_dataset()
    return default_df.copy(), False, DEFAULT_DATASET_LABEL


def set_active_dataset(df: pd.DataFrame, filename: str, cleaning_report: dict,
                        prediction_compatibility: dict) -> None:
    """
    Called ONLY by the Home page after a new file has been uploaded and
    cleaned. Overwrites any previously active uploaded dataset -- there is
    never more than one active dataset in session state at a time, so a
    second upload cleanly replaces the first (Required Change #8).
    """
    st.session_state[SESSION_KEY_DATASET] = df
    st.session_state[SESSION_KEY_FILENAME] = filename
    st.session_state[SESSION_KEY_UPLOAD_TIME] = datetime.now().strftime("%H:%M:%S")
    st.session_state[SESSION_KEY_CLEANING_REPORT] = cleaning_report
    st.session_state[SESSION_KEY_COMPATIBILITY] = prediction_compatibility


def get_cleaning_report():
    return st.session_state.get(SESSION_KEY_CLEANING_REPORT)


def get_prediction_compatibility():
    return st.session_state.get(SESSION_KEY_COMPATIBILITY)


def get_upload_time():
    return st.session_state.get(SESSION_KEY_UPLOAD_TIME, "-")


# ==========================================================
# PREDICTION FEATURE DERIVATION
# ==========================================================
# The existing model was trained on Year / Month / Shipping Days as
# explicit features. These were never literal columns in the raw
# Superstore CSV either -- the original pages derived them on the fly
# from Order Date / Ship Date. This helper centralizes that SAME
# derivation logic so it runs once, consistently, for ANY active
# dataset (uploaded or sample) instead of being duplicated across
# pages. It only derives columns that are unambiguously computable
# from real data already present -- it never invents a value.

def derive_prediction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a NEW dataframe with Year / Month / Shipping Days added
    when (and only when) they can be safely derived from existing,
    genuine columns. Never fabricates a column it can't derive."""
    out = df.copy()

    if "Order Date" in out.columns:
        order_date = pd.to_datetime(out["Order Date"], errors="coerce")

        if "Year" not in out.columns and order_date.notna().any():
            out["Year"] = order_date.dt.year

        if "Month" not in out.columns and order_date.notna().any():
            out["Month"] = order_date.dt.month

        if "Ship Date" in out.columns and "Shipping Days" not in out.columns:
            ship_date = pd.to_datetime(out["Ship Date"], errors="coerce")
            out["Shipping Days"] = (ship_date - order_date).dt.days

    return out


def get_prediction_ready_dataset():
    """
    Convenience helper for the AI Sales Prediction page: active dataset
    with Year / Month / Shipping Days derived, plus the label/uploaded
    flag, so pages never re-implement this themselves.
    """
    df, is_uploaded, label = get_active_dataset()
    df = derive_prediction_features(df)
    return df, is_uploaded, label


def has_columns(df: pd.DataFrame, columns) -> bool:
    """Small readability helper used across pages for graceful degradation."""
    return all(col in df.columns for col in columns)
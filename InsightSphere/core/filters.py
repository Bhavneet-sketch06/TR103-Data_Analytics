"""
Global filters: date range, comparison period and dimension filters.

Widgets use fixed keys with bind="query-params" (shareable, reload-safe URLs)
and persist_state="session" (kept while switching pages). The date window is
anchored to the dataset's last order date, not today, so "Last 12 months" on a
historical dataset means its last 12 months of activity.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from core.schema import FIELD_BY_KEY

PRESETS = ["Last 30 days", "Last 90 days", "Quarter to date", "Year to date",
           "Last 12 months", "All time", "Custom"]
DEFAULT_PRESET = "Last 12 months"

COMPARE = ["Previous period", "Same period last year", "No comparison"]
DEFAULT_COMPARE = "Same period last year"
COMPARE_SHORT = {"Previous period": "vs prev. period", "Same period last year": "vs LY"}

FILTER_DIMS = ["region", "category", "segment"]

K_PRESET, K_CUSTOM, K_COMPARE = "range", "custom", "compare"
K_DIM = {dim: f"f_{dim}" for dim in FILTER_DIMS}
K_DIGEST = "_filters_for_digest"
K_PENDING = "_pending_filters"
K_SEL_NONCE = "_selection_nonce"


@dataclass(frozen=True)
class Window:
    start: pd.Timestamp
    end: pd.Timestamp              # inclusive (end of day)
    prev_start: pd.Timestamp | None
    prev_end: pd.Timestamp | None
    preset: str
    compare: str

    @property
    def label(self) -> str:
        s, e = self.start, self.end
        if s.year == e.year:
            return f"{s:%b} {s.day} – {e:%b} {e.day}, {e.year}"
        return f"{s:%b} {s.day}, {s.year} – {e:%b} {e.day}, {e.year}"

    @property
    def compare_short(self) -> str:
        return COMPARE_SHORT.get(self.compare, "") if self.prev_start is not None else ""


# ----------------------------------------------------------
# Window math (pure, unit-tested)
# ----------------------------------------------------------

def compute_window(preset: str, compare: str, data_min: pd.Timestamp, data_max: pd.Timestamp,
                   custom: tuple | None = None) -> Window:
    end = data_max.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    anchor = data_max.normalize()

    if preset == "Last 30 days":
        start = anchor - pd.Timedelta(days=29)
    elif preset == "Last 90 days":
        start = anchor - pd.Timedelta(days=89)
    elif preset == "Quarter to date":
        start = anchor.to_period("Q").start_time
    elif preset == "Year to date":
        start = pd.Timestamp(year=anchor.year, month=1, day=1)
    elif preset == "Last 12 months":
        # Month-aligned so monthly charts don't start with a one-day stub bin.
        start = (anchor.to_period("M") - 11).start_time
    elif preset == "Custom" and custom and len(custom) == 2 and custom[0] and custom[1]:
        start = pd.Timestamp(custom[0])
        end = pd.Timestamp(custom[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    else:  # All time (and incomplete custom ranges)
        start = data_min.normalize()

    start = max(start, data_min.normalize())

    prev_start = prev_end = None
    if compare == "Same period last year":
        prev_start, prev_end = start - pd.DateOffset(years=1), end - pd.DateOffset(years=1)
    elif compare == "Previous period":
        length = end - start
        prev_end = start - pd.Timedelta(microseconds=1)
        prev_start = prev_end - length
    if prev_start is not None and prev_start < data_min.normalize():
        # The comparison window must be fully covered by data; a partly empty
        # window would show inflated growth.
        prev_start = prev_end = None

    return Window(start, end, prev_start, prev_end, preset, compare)


def apply_dimension_filters(df: pd.DataFrame, selections: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for dim, values in selections.items():
        if values and dim in df.columns:
            mask &= df[dim].isin(values)
    return df[mask]


def slice_window(df: pd.DataFrame, start, end) -> pd.DataFrame:
    return df[(df["order_date"] >= start) & (df["order_date"] <= end)]


# ----------------------------------------------------------
# Session-aware helpers
# ----------------------------------------------------------

def reset_if_dataset_changed(digest: str) -> None:
    if st.session_state.get(K_DIGEST) != digest:
        for key in [K_PRESET, K_CUSTOM, K_COMPARE, *K_DIM.values()]:
            st.session_state.pop(key, None)
        st.session_state[K_DIGEST] = digest


def _init(key: str, default) -> None:
    """Seeds a widget's value unless the session or the URL already has one."""
    if key not in st.session_state and key not in st.query_params:
        st.session_state[key] = default


def reset_filters() -> None:
    st.session_state[K_PRESET] = DEFAULT_PRESET
    st.session_state[K_COMPARE] = DEFAULT_COMPARE
    for key in K_DIM.values():
        st.session_state[key] = []


def selections() -> dict:
    return {dim: st.session_state.get(key, []) or [] for dim, key in K_DIM.items()}


# Cross-filtering. A chart click can't write to the sidebar multiselects
# directly (they were already drawn this run), so the value is queued, the
# app reruns, and the queue is applied before the widgets are drawn. Bumping
# the nonce gives selectable charts a fresh key, which clears their selection.

def queue_filter(dim: str, values) -> None:
    pending = st.session_state.setdefault(K_PENDING, [])
    pending.extend((dim, str(v)) for v in values)
    st.session_state[K_SEL_NONCE] = st.session_state.get(K_SEL_NONCE, 0) + 1


def apply_pending() -> None:
    for dim, value in st.session_state.pop(K_PENDING, []):
        key = K_DIM.get(dim)
        if key is None:
            continue
        current = list(st.session_state.get(key, []) or [])
        if value not in current:
            st.session_state[key] = current + [value]


def selection_nonce() -> int:
    return st.session_state.get(K_SEL_NONCE, 0)


def current_window(df: pd.DataFrame) -> Window:
    return compute_window(
        st.session_state.get(K_PRESET, DEFAULT_PRESET),
        st.session_state.get(K_COMPARE, DEFAULT_COMPARE),
        df["order_date"].min(), df["order_date"].max(),
        st.session_state.get(K_CUSTOM),
    )


def filtered(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame, Window]:
    """
    (current-period rows, comparison-period rows or None, history, window).
    History is every row up to the window end, with dimension filters, for
    sparklines and anything that needs a customer's full past.
    """
    window = current_window(df)
    dims = apply_dimension_filters(df, selections())
    current = slice_window(dims, window.start, window.end)
    previous = slice_window(dims, window.prev_start, window.prev_end) if window.prev_start is not None else None
    history = dims[dims["order_date"] <= window.end]
    return current, previous, history, window


# ----------------------------------------------------------
# Widgets
# ----------------------------------------------------------

def date_controls(df: pd.DataFrame) -> None:
    """Date preset + comparison, rendered in the page header's right column."""
    _init(K_PRESET, DEFAULT_PRESET)
    _init(K_COMPARE, DEFAULT_COMPARE)
    with st.container(horizontal=True, horizontal_alignment="right", gap="small"):
        st.selectbox(
            "Date range", PRESETS, key=K_PRESET,
            label_visibility="collapsed", width=170,
            bind="query-params", persist_state="session",
        )
        st.selectbox(
            "Compare to", COMPARE, key=K_COMPARE,
            label_visibility="collapsed", width=200,
            bind="query-params", persist_state="session",
        )
    if st.session_state.get(K_PRESET) == "Custom":
        lo, hi = df["order_date"].min().date(), df["order_date"].max().date()
        st.date_input(
            "Custom range", value=(lo, hi), min_value=lo, max_value=hi, key=K_CUSTOM,
            label_visibility="collapsed", persist_state="session",
        )


def dimension_controls(df: pd.DataFrame) -> None:
    """Dimension multiselects for the sidebar (only for mapped fields)."""
    for dim, key in K_DIM.items():
        if dim not in df.columns:
            continue
        options = sorted(df[dim].dropna().astype(str).unique().tolist())
        current = [v for v in st.session_state.get(key, []) if v in options]
        if current != st.session_state.get(key, current):
            st.session_state[key] = current
        st.multiselect(
            FIELD_BY_KEY[dim].label, options, key=key, placeholder="All",
            bind="query-params", persist_state="session",
        )


def _remove_value(key: str, value: str) -> None:
    st.session_state[key] = [v for v in st.session_state.get(key, []) if v != value]


def filter_chips() -> None:
    """Removable chips for active dimension filters (renders nothing when none)."""
    active = [(dim, v) for dim, values in selections().items() for v in values]
    if not active:
        return
    with st.container(key="chips", horizontal=True, gap="small"):
        for dim, value in active:
            st.button(
                f"{FIELD_BY_KEY[dim].label}: {value}  ✕", key=f"chip-{dim}-{value}",
                on_click=_remove_value, args=(K_DIM[dim], value),
            )
        with st.container(key="chip-clear", width="content"):
            st.button("Clear all", key="chip-clear-btn", on_click=lambda: [
                st.session_state.__setitem__(k, []) for k in K_DIM.values()
            ])

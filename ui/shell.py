"""
App shell shared by every page: theme CSS, sidebar (filters, dataset chip,
theme toggle) and the page header with global date controls.

Pages call `shell.page(...)` first and get back everything they need:

    ctx = shell.page("Overview", "Sales performance at a glance")
    ctx.cur, ctx.prev, ctx.window, ctx.dataset
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import filters, state
from core.ingest import Dataset
from core.schema import missing_for
from ui import components as ui
from ui.tokens import css_variables

UI_DIR = Path(__file__).resolve().parent
LOGO = UI_DIR / "assets" / "logo.svg"

THEMES = ["Light", "Dark", "System"]
THEME_ICONS = {"Light": ":material/light_mode:", "Dark": ":material/dark_mode:",
               "System": ":material/contrast:"}
K_THEME = "theme"
K_PATHS = "_page_paths"


@dataclass
class PageContext:
    dataset: Dataset
    df: pd.DataFrame                 # full dataset (dimension filters NOT applied)
    cur: pd.DataFrame                # current window + dimension filters
    prev: pd.DataFrame | None        # comparison window + dimension filters
    hist: pd.DataFrame               # all rows up to the window end + dimension filters
    window: filters.Window


# ----------------------------------------------------------
# Global (called once per run from app.py)
# ----------------------------------------------------------

def _stylesheet() -> str:
    return css_variables() + (UI_DIR / "theme.css").read_text(encoding="utf-8")


def inject_css() -> None:
    st.html(f"<style>{_stylesheet()}</style>")


def logo() -> None:
    st.logo(str(LOGO), size="large", icon_image=str(LOGO))


def set_page_paths(paths: list[str]) -> None:
    """Called once per run by app.py so the theme toggle knows every page path."""
    st.session_state[K_PATHS] = paths


def _apply_theme(paths: list[str]) -> None:
    """Writes Streamlit's stored theme choice for every page path, then reloads.

    Streamlit keeps the theme in localStorage under a key per landing path, so
    all page paths are written to keep the choice consistent across pages.
    Filters and the active dataset survive the reload through the URL.
    """
    choice = st.session_state.get(K_THEME) or "System"
    script = (
        "<script>"
        f"const choice = {json.dumps(json.dumps(choice))};"
        f"const paths = {json.dumps(paths)};"
        "const ls = window.parent.localStorage;"
        "for (const p of paths) { ls.setItem('stActiveTheme-' + p + '-v2', choice); }"
        "window.parent.location.reload();"
        "</script>"
    )
    components.html(script, height=0)


def sidebar(dataset: Dataset) -> None:
    df = dataset.df
    filters.reset_if_dataset_changed(dataset.digest)
    filters.apply_pending()
    with st.sidebar:
        ui.section_label("Filters")
        filters.dimension_controls(df)
        st.button(
            "Reset filters", icon=":material/restart_alt:", width="stretch",
            on_click=filters.reset_filters, type="secondary",
        )
        st.space("small")
        ui.dataset_chip(dataset.name, len(df), dataset.date_span, dataset.is_sample)


def theme_toggle() -> None:
    """Light / dark / system switch shown at the top right of every page."""
    st.segmented_control(
        "Theme", THEMES, key=K_THEME, default="System", label_visibility="collapsed",
        format_func=THEME_ICONS.get, help="Theme: light, dark or follow your system",
        on_change=lambda: st.session_state.__setitem__("_theme_changed", True),
        bind="query-params",
    )
    if st.session_state.pop("_theme_changed", False):
        _apply_theme(st.session_state.get(K_PATHS, ["/"]))


# ----------------------------------------------------------
# Per page
# ----------------------------------------------------------

def header(title: str, subtitle: str = "", *, df: pd.DataFrame | None = None) -> None:
    """Page title on the left; date controls (when df is given) and the theme toggle on the right."""
    right = ui.page_header(title, subtitle)
    with right:
        with st.container(horizontal=True, horizontal_alignment="right", gap="small",
                          vertical_alignment="center"):
            if df is not None:
                filters.date_selects()
            theme_toggle()
        if df is not None:
            filters.custom_range(df)


def page(title: str, subtitle: str = "", *, needs: tuple[str, ...] = (),
         feature: str = "", date_controls: bool = True) -> PageContext | None:
    """
    Renders the header (title + global date controls + filter chips) and
    returns the filtered frames. Returns None after drawing a locked state if
    the dataset lacks fields the page needs.
    """
    dataset = state.get_dataset()
    df = dataset.df

    header(title, subtitle, df=df if date_controls else None)

    missing = missing_for(df, *needs) if needs else []
    if missing:
        st.space("small")
        ui.locked_state(feature or title, missing)
        return None

    cur, prev, hist, window = filters.filtered(df)
    if date_controls:
        meta = window.label + (f"  ·  {window.compare_short}" if window.compare_short else "")
        st.caption(meta)
    filters.filter_chips()
    return PageContext(dataset=dataset, df=df, cur=cur, prev=prev, hist=hist, window=window)

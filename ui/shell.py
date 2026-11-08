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
K_THEME = "theme"


@dataclass
class PageContext:
    dataset: Dataset
    df: pd.DataFrame                 # full dataset (dimension filters NOT applied)
    cur: pd.DataFrame                # current window + dimension filters
    prev: pd.DataFrame | None        # comparison window + dimension filters
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


def sidebar(dataset: Dataset, page_paths: list[str]) -> None:
    df = dataset.df
    filters.reset_if_dataset_changed(dataset.digest)
    with st.sidebar:
        ui.section_label("Filters")
        filters.dimension_controls(df)
        st.button(
            "Reset filters", icon=":material/restart_alt:", width="stretch",
            on_click=filters.reset_filters, type="secondary",
        )
        st.space("small")
        ui.dataset_chip(dataset.name, len(df), dataset.date_span, dataset.is_sample)
        st.space("small")
        ui.section_label("Appearance")
        st.segmented_control(
            "Theme", THEMES, key=K_THEME, label_visibility="collapsed",
            width="stretch", on_change=lambda: st.session_state.__setitem__("_theme_changed", True),
            bind="query-params",
        )
        if st.session_state.pop("_theme_changed", False):
            _apply_theme(page_paths)


# ----------------------------------------------------------
# Per page
# ----------------------------------------------------------

def page(title: str, subtitle: str = "", *, needs: tuple[str, ...] = (),
         feature: str = "", date_controls: bool = True) -> PageContext | None:
    """
    Renders the header (title + global date controls + filter chips) and
    returns the filtered frames. Returns None after drawing a locked state if
    the dataset lacks fields the page needs.
    """
    dataset = state.get_dataset()
    df = dataset.df

    right = ui.page_header(title, subtitle)
    if date_controls:
        with right:
            filters.date_controls(df)

    missing = missing_for(df, *needs) if needs else []
    if missing:
        st.space("small")
        ui.locked_state(feature or title, missing)
        return None

    cur, prev, window = filters.filtered(df)
    if date_controls:
        meta = window.label + (f"  ·  {window.compare_short}" if window.compare_short else "")
        st.caption(meta)
    filters.filter_chips()
    return PageContext(dataset=dataset, df=df, cur=cur, prev=prev, window=window)

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

from core import filters, state
from core.ingest import Dataset
from core.schema import missing_for
from ui import charts
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


# Streamlit's own theme names end with these words ("Custom Theme Light" when
# the theme comes from config.toml, "Light" otherwise; "Use system setting"
# is the built-in name for following the OS).
_THEME_SUFFIX = {"Light": ["Light"], "Dark": ["Dark"], "System": ["Auto", "Use system setting"]}


def _sync_switch_script(shown: str) -> str:
    """Presses the switch option matching the theme stored in the browser, if it differs."""
    icons = {name: icon.split("/")[1].rstrip(":") for name, icon in THEME_ICONS.items()}
    return f"""<script>
(() => {{
  let stored = 'System';
  try {{ stored = JSON.parse(localStorage.getItem('stActiveTheme-' + location.pathname + '-v2')) || 'System'; }} catch (e) {{}}
  const icons = {json.dumps(icons)};
  if (stored === {json.dumps(shown)} || !icons[stored]) return;
  // Wait for the switch to be drawn and interactive, then press the stored option.
  let tries = 0;
  const press = () => {{
    const b = [...document.querySelectorAll('.st-key-theme button')].find(b => b.innerText.trim() === icons[stored]);
    if (b) setTimeout(() => b.click(), 300);
    else if (++tries < 50) setTimeout(press, 100);
  }};
  setTimeout(press, 100);
}})();
</script>"""


def _switch_theme_script(choice: str, paths: list[str], chart_mode: str) -> str:
    """
    Switches Streamlit's theme in place, the same way its Settings menu does,
    so there is no page reload and no flash.

    Streamlit keeps the active theme in a React context ({activeTheme,
    setTheme, availableThemes}); the script finds it from the app's root
    element and calls setTheme. It also stores the choice for every page path,
    because Streamlit remembers the theme per landing path.

    Charts are colored on the server. For Light/Dark this run already used the
    new mode; for System the server only knows the previous theme, so when the
    OS setting differs the hidden sync button triggers one more rerun.
    If the theme context can't be found (a future Streamlit change), it falls
    back to reloading the page.
    """
    return f"""<script>
(() => {{
  const choice = {json.dumps(choice)};
  const suffixes = {json.dumps(_THEME_SUFFIX[choice])};
  const paths = {json.dumps(paths)};
  const chartMode = {json.dumps(chart_mode)};
  for (const p of paths) localStorage.setItem('stActiveTheme-' + p + '-v2', JSON.stringify(choice));
  const root = document.querySelector('.stApp');
  const fiberKey = root && Object.keys(root).find(k => k.startsWith('__reactFiber$'));
  let fiber = fiberKey ? root[fiberKey] : null, ctx = null;
  while (fiber && !ctx) {{
    const p = fiber.memoizedProps;
    if (p && typeof p.setTheme === 'function' && Array.isArray(p.availableThemes)) ctx = p;
    else if (p && p.value && typeof p.value.setTheme === 'function' && Array.isArray(p.value.availableThemes)) ctx = p.value;
    fiber = fiber.return;
  }}
  const theme = ctx && ctx.availableThemes.find(t => suffixes.some(s => t.name.endsWith(s)));
  if (!theme) {{ location.reload(); return; }}
  ctx.setTheme(theme);
  const dark = choice === 'Dark' || (choice === 'System' && matchMedia('(prefers-color-scheme: dark)').matches);
  if ((dark ? 'dark' : 'light') !== chartMode) {{
    setTimeout(() => document.querySelector('.st-key-theme-sync button')?.click(), 50);
  }}
}})();
</script>"""


def sidebar(dataset: Dataset | None) -> None:
    if dataset is None:
        with st.sidebar:
            ui.section_label("Dataset")
            ui.no_dataset_chip()
        return
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
        format_func=THEME_ICONS.get,
        on_change=lambda: st.session_state.__setitem__("_theme_changed", True),
    )
    # Hidden helpers: the switch script and a button the script can press to
    # rerun once more. display:none keeps them out of the header row's layout.
    with st.container(key="hidden-theme"):
        st.button("Sync theme", key="theme-sync")
        if not st.session_state.get("_theme_synced"):
            # First run of a session: the browser may remember a theme from a
            # previous visit; make the switch show it.
            st.session_state["_theme_synced"] = True
            st.html(_sync_switch_script(st.session_state.get(K_THEME) or "System"),
                    unsafe_allow_javascript=True)
        if st.session_state.pop("_theme_changed", False):
            choice = st.session_state.get(K_THEME) or "System"
            st.html(_switch_theme_script(choice, st.session_state.get(K_PATHS, ["/"]), charts.current_mode()),
                    unsafe_allow_javascript=True)


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
         feature: str = "", date_controls: bool = True, actions=None) -> PageContext | None:
    """
    Renders the header (title + global date controls + filter chips) and
    returns the filtered frames. `actions(ctx)` (a function drawing buttons) goes
    at the right of the date-range line. Returns None after drawing an upload prompt
    when no dataset is loaded yet, or a locked state when the dataset lacks
    fields the page needs.
    """
    dataset = state.get_dataset()
    if dataset is None:
        header(title, subtitle)
        st.space("small")
        ui.no_data_state(title)
        return None
    df = dataset.df

    header(title, subtitle, df=df if date_controls else None)

    missing = missing_for(df, *needs) if needs else []
    if missing:
        st.space("small")
        ui.locked_state(feature or title, missing)
        return None

    cur, prev, hist, window = filters.filtered(df)
    ctx = PageContext(dataset=dataset, df=df, cur=cur, prev=prev, hist=hist, window=window)
    if date_controls or actions:
        meta = window.label + (f"  ·  {window.compare_short}" if window.compare_short else "")
        with st.container(horizontal=True, vertical_alignment="center", key="page-meta"):
            if date_controls:
                st.caption(meta)
            if actions:
                with st.container(horizontal=True, horizontal_alignment="right"):
                    actions(ctx)
    filters.filter_chips()
    return ctx

"""
Plotly defaults and color rules shared by every chart.

Rules (from the dataviz method):
  * one y-axis per chart, never two
  * colors follow the entity, never its rank (stable_color_map)
  * 2px lines, 4px rounded bar ends, faint grid, unified hover
  * comparison periods are dashed and muted; forecasts dashed in the accent
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ui.tokens import DIVERGING, OTHER_COLOR, SEQUENTIAL, SERIES, tokens_for

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtons": [["toImage"]],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def current_mode() -> str:
    """
    'light' or 'dark'. An explicit choice in the header's theme switch wins,
    because the switch changes the theme without a reload and the browser's
    report (st.context.theme) only catches up on the next rerun. For System
    it falls back to that report, then to light.
    """
    choice = st.session_state.get("theme")   # ui.shell.K_THEME
    if choice in ("Light", "Dark"):
        return choice.lower()
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def series_colors(mode: str | None = None) -> list[str]:
    return SERIES[mode or current_mode()]


def stable_color_map(values, mode: str | None = None) -> dict:
    """
    Maps category values to palette slots by sorted name, so a value keeps its
    color when filters remove other values. Beyond 8 values the rest share the
    neutral "Other" color.
    """
    mode = mode or current_mode()
    palette = SERIES[mode]
    ordered = sorted({str(v) for v in values})
    return {
        v: (palette[i] if i < len(palette) else OTHER_COLOR[mode])
        for i, v in enumerate(ordered)
    }


def sequential_scale() -> list[list]:
    ramp = SEQUENTIAL if current_mode() == "light" else list(reversed(SEQUENTIAL))[:-1]
    n = len(ramp) - 1
    return [[i / n, c] for i, c in enumerate(ramp)]


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def heatmap_labels(fig: go.Figure, x, y, z, text) -> go.Figure:
    """
    Cell labels whose color follows each cell's fill: dark ink on light cells,
    white on dark ones. Plotly's heatmap text uses one color for every cell,
    which becomes unreadable on part of the ramp in one of the two themes.
    Cells with no value (NaN) get their text in the muted color.
    """
    import numpy as np

    values = np.asarray(z, dtype=float)
    lo, hi = np.nanmin(values), np.nanmax(values)
    scale = sequential_scale()
    ink = tokens_for(current_mode())
    for i in range(len(y)):
        for j in range(len(x)):
            label = text[i][j]
            if not label:
                continue
            v = values[i, j]
            if np.isnan(v):
                color = ink["text_2"]
            else:
                pos = 0.0 if hi == lo else (v - lo) / (hi - lo)
                fill = scale[min(int(round(pos * (len(scale) - 1))), len(scale) - 1)][1]
                color = "#111114" if _luminance(fill) > 0.32 else "#FFFFFF"
            # Positions by index: on a category axis a numeric-looking name such as
            # "2014" would be read as an index, so names aren't safe.
            fig.add_annotation(x=j, y=i, text=label, showarrow=False, font=dict(size=11, color=color))
    return fig


def diverging_scale() -> list[list]:
    """Orange (negative) -> gray (zero) -> blue (positive). Pair with a symmetric cmid=0 range."""
    ramp = DIVERGING[current_mode()]
    n = len(ramp) - 1
    return [[i / n, c] for i, c in enumerate(ramp)]


def style(fig: go.Figure, *, height: int = 320, legend: bool = False,
          y_format: str | None = None, x_format: str | None = None,
          hovermode: str = "x unified") -> go.Figure:
    """Applies the house layout. Colors that differ by mode come from tokens."""
    t = tokens_for(current_mode())
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=8, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color=t["text_2"]),
        hovermode=hovermode,
        hoverlabel=dict(
            bgcolor=t["surface"], bordercolor=t["border_strong"],
            font=dict(family="Inter, sans-serif", size=12, color=t["text"]),
        ),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            title_text="", font=dict(size=12, color=t["text_2"]),
            bgcolor="rgba(0,0,0,0)",
        ),
        bargap=0.28,
        bargroupgap=0.08,
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, showline=False, ticks="",
        tickfont=dict(size=11.5, color=t["text_3"]), title_text="",
        tickformat=x_format, automargin=True,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=t["grid"], gridwidth=1, zeroline=False,
        showline=False, ticks="", tickfont=dict(size=11.5, color=t["text_3"]),
        title_text="", tickformat=y_format, automargin=True,
    )
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4, marker_line_width=0)
    fig.update_traces(selector=dict(type="scatter", mode="lines"), line_width=2)
    return fig


def hbar_room(fig: go.Figure, max_value: float, room: float = 1.18) -> go.Figure:
    """Leaves space to the right of horizontal bars for their outside labels."""
    fig.update_xaxes(range=[0, max_value * room] if max_value > 0 else None)
    return fig


def table_height(rows: int, max_rows: int = 12) -> int:
    """Height that fits a dataframe exactly (rows are 31px at the 14px base font)."""
    return 36 + 31 * max(1, min(rows, max_rows))


def show(fig: go.Figure, *, key: str | None = None, on_select=None, selection_mode=None):
    """Renders with the house config. Pass on_select='rerun' for cross-filtering."""
    kwargs = dict(width="stretch", theme=None, config=PLOTLY_CONFIG, key=key)
    if on_select:
        kwargs["on_select"] = on_select
        kwargs["selection_mode"] = selection_mode or ("points",)
    return st.plotly_chart(fig, **kwargs)


# ----------------------------------------------------------
# Number formatting (used by charts, tiles and tables)
# ----------------------------------------------------------

def compact(value: float, prefix: str = "") -> str:
    """1284 -> 1.3K, 4_200_000 -> 4.2M. Keeps the sign in front of the prefix."""
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    v = abs(float(value))
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}{prefix}{v / threshold:.1f}{suffix}"
    if v >= 100:
        return f"{sign}{prefix}{v:,.0f}"
    return f"{sign}{prefix}{v:,.2f}".rstrip("0").rstrip(".") if prefix == "" else f"{sign}{prefix}{v:,.2f}"


def money(value: float, currency: str = "$") -> str:
    return compact(value, prefix=currency)


def pct(value: float, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"

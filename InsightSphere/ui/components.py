"""
Reusable UI pieces. Every function that renders user-provided text escapes it.

HTML pieces are rendered through st.markdown (st.html strips inline SVG);
bordered "cards" are native containers keyed `card-*` so they can hold widgets
and charts, and are styled by ui/theme.css.
"""

from __future__ import annotations

import html
from contextlib import contextmanager

import streamlit as st

# ----------------------------------------------------------
# Icons (inline SVG, 24px viewBox, stroke = currentColor)
# ----------------------------------------------------------

_ICON_PATHS = {
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "trend_up": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "trend_down": '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "sparkles": '<path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 16v-5"/><path d="M12 16V8"/><path d="M17 16v-8"/>',
    "layout": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
    "tag": '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0'
           'l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/>'
             '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "truck": '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/>'
             '<path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14"/>'
             '<circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
}


def icon(name: str, size: int = 16) -> str:
    path = _ICON_PATHS.get(name, _ICON_PATHS["info"])
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def render(markup: str) -> None:
    """Renders trusted HTML (st.html's sanitizer strips inline SVG, markdown keeps it)."""
    st.markdown(markup, unsafe_allow_html=True)


# ----------------------------------------------------------
# Page header
# ----------------------------------------------------------

def page_header(title: str, subtitle: str = "", eyebrow: str = ""):
    """
    Title block on the left; returns the right-hand column so the caller can
    place page-level controls (date range, comparison, export) next to it.
    """
    left, right = st.columns([1, 1.2], vertical_alignment="bottom")
    with left:
        render(
            '<div class="is-page-head">'
            + (f'<div class="is-eyebrow">{esc(eyebrow)}</div>' if eyebrow else "")
            + f'<div class="is-page-title">{esc(title)}</div>'
            + (f'<div class="is-page-sub">{esc(subtitle)}</div>' if subtitle else "")
            + "</div>"
        )
    return right


# ----------------------------------------------------------
# Delta badge + sparkline
# ----------------------------------------------------------

def delta_badge(change: float | None, *, higher_is_better: bool = True,
                kind: str = "pct", suffix: str = "") -> str:
    """
    change: relative change for kind='pct' (0.12 = +12%), or absolute
    percentage-point change for kind='pp' (0.004 = +0.4pp).
    Color = direction x whether up is good. Arrow + sign keep it readable
    without color.
    """
    if change is None:
        return '<span class="is-delta is-delta-flat">—</span>'
    magnitude = abs(change) * 100
    if magnitude < 0.05:
        cls, arrow = "is-delta-flat", "→"
    else:
        up = change > 0
        good = up == higher_is_better
        cls = "is-delta-good" if good else "is-delta-bad"
        arrow = "▲" if up else "▼"
    unit = "pp" if kind == "pp" else "%"
    text = f"{arrow} {magnitude:.1f}{unit}{suffix}"
    return f'<span class="{cls} is-delta">{esc(text)}</span>'


def sparkline_svg(values, width: int = 96, height: int = 30) -> str:
    """Muted line with the latest point marked in the accent color."""
    values = [float(v) for v in values if v == v]  # drop NaN
    if len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = (width - 6) / (len(values) - 1)
    pts = [
        (3 + i * step, height - 4 - ((v - lo) / span) * (height - 8))
        for i, v in enumerate(values)
    ]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"3,{height} " + poly + f" {pts[-1][0]:.1f},{height}"
    lx, ly = pts[-1]
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<polygon points="{area}" style="fill:var(--is-accent-soft)"/>'
        f'<polyline points="{poly}" style="fill:none;stroke:var(--is-text-3)" stroke-width="1.5" '
        f'stroke-linejoin="round" stroke-linecap="round" opacity="0.8"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.8" style="fill:var(--is-accent)"/>'
        "</svg>"
    )


# ----------------------------------------------------------
# KPI tile
# ----------------------------------------------------------

def kpi_tile(label: str, value: str, *, change: float | None = None,
             period: str = "", higher_is_better: bool = True, kind: str = "pct",
             spark=None, target_progress: float | None = None,
             target_label: str = "", help_text: str = "") -> None:
    badge = delta_badge(change, higher_is_better=higher_is_better, kind=kind) if change is not None else ""
    spark_html = f'<div class="is-kpi-spark">{sparkline_svg(spark)}</div>' if spark is not None else ""
    target_html = ""
    if target_progress is not None:
        fill = max(0.0, min(1.0, target_progress)) * 100
        target_html = (
            '<div class="is-kpi-target"><div class="is-meter">'
            f'<span style="width:{fill:.0f}%"></span></div>'
            f'<div class="is-meter-label">{esc(target_label)}</div></div>'
        )
    title_attr = f' title="{esc(help_text)}"' if help_text else ""
    render(
        f'<div class="is-kpi"{title_attr}>'
        f'<div class="is-kpi-top"><span class="is-kpi-label">{esc(label)}</span>{badge}</div>'
        f'<div class="is-kpi-value">{esc(value)}</div>'
        f'<div class="is-kpi-foot"><span class="is-kpi-period">{esc(period)}</span>{spark_html}</div>'
        f"{target_html}</div>"
    )


# ----------------------------------------------------------
# Card container
# ----------------------------------------------------------

@contextmanager
def card(key: str, title: str = "", subtitle: str = "", *, height="content"):
    """Bordered surface for a chart/table. Use as `with card("trend", "Revenue"):`."""
    with st.container(key=f"card-{key}", height=height):
        if title or subtitle:
            render(
                '<div class="is-card-head"><div>'
                + (f'<div class="is-card-title">{esc(title)}</div>' if title else "")
                + (f'<div class="is-card-sub">{esc(subtitle)}</div>' if subtitle else "")
                + "</div></div>"
            )
        yield


# ----------------------------------------------------------
# Lists, pills, chips
# ----------------------------------------------------------

def pill(text: str, tone: str = "neutral") -> str:
    return f'<span class="is-pill is-pill-{tone}">{esc(text)}</span>'


_TONE_ICON = {"good": "check", "warn": "alert", "bad": "trend_down", "info": "info"}


def item_list(items) -> None:
    """items: iterable of dicts {tone: good|warn|bad|info, title, body}."""
    rows = []
    for item in items:
        tone = item.get("tone", "info")
        rows.append(
            "<li>"
            f'<span class="is-list-icon {tone}">{icon(item.get("icon", _TONE_ICON.get(tone, "info")), 14)}</span>'
            f'<div><div class="is-list-title">{esc(item["title"])}</div>'
            + (f'<div class="is-list-body">{esc(item["body"])}</div>' if item.get("body") else "")
            + "</div></li>"
        )
    render(f'<ul class="is-list">{"".join(rows)}</ul>')


def stat_chips(pairs) -> None:
    """Small inline facts: [(label, value), ...]."""
    chips = "".join(
        f'<div class="is-chip"><div class="is-chip-label">{esc(label)}</div>'
        f'<div class="is-chip-value">{esc(value)}</div></div>'
        for label, value in pairs
    )
    render(f'<div class="is-chip-row">{chips}</div>')


def stepper(steps, active: int) -> None:
    """Horizontal progress steps. `active` is the 0-based current step."""
    parts = []
    for i, label in enumerate(steps):
        state = "done" if i < active else ("active" if i == active else "")
        dot = "✓" if i < active else str(i + 1)
        if i:
            parts.append('<span class="is-step-line"></span>')
        parts.append(
            f'<span class="is-step {state}"><span class="is-step-dot">{dot}</span>{esc(label)}</span>'
        )
    render(f'<div class="is-stepper">{"".join(parts)}</div>')


# ----------------------------------------------------------
# Empty / locked states
# ----------------------------------------------------------

def empty_state(title: str, body: str = "", icon_name: str = "search") -> None:
    render(
        '<div class="is-empty">'
        f'<div class="is-empty-icon">{icon(icon_name, 20)}</div>'
        f'<div class="is-empty-title">{esc(title)}</div>'
        + (f'<div class="is-empty-body">{esc(body)}</div>' if body else "")
        + "</div>"
    )


def locked_state(feature: str, missing_fields) -> None:
    fields = ", ".join(missing_fields)
    empty_state(
        f"{feature} needs more columns",
        f"Map {fields} on the Data page to unlock this view.",
        icon_name="lock",
    )
    st.page_link("views/data.py", label="Go to Data", icon=":material/arrow_forward:")


def section_label(text: str) -> None:
    render(f'<div class="is-side-label">{esc(text)}</div>')


def dataset_chip(name: str, rows: int, span: str, is_sample: bool) -> None:
    tag = pill("Sample", "neutral") if is_sample else pill("Uploaded", "info")
    render(
        '<div class="is-dataset">'
        f'<div class="is-dataset-icon">{icon("database", 15)}</div>'
        '<div style="min-width:0">'
        f'<div class="is-dataset-name" title="{esc(name)}">{esc(name)}</div>'
        f'<div class="is-dataset-meta">{rows:,} rows · {esc(span)}</div>'
        f'<div style="margin-top:6px">{tag}</div>'
        "</div></div>"
    )

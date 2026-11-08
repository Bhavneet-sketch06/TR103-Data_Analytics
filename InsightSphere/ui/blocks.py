"""
Composite blocks shared by the analytics pages: KPI rows, the trend card,
ranked bars, cross-filtering charts and downloadable tables.

They combine the metrics layer with the components in ui/components.py so
every page shows numbers, deltas and charts the same way.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import db, filters, metrics
from ui import charts
from ui import components as ui

METRIC_LABELS = {"revenue": "Revenue", "profit": "Profit", "orders": "Orders", "margin": "Profit margin"}
HOVER = {"money": "%{y:$,.0f}", "count": "%{y:,.0f}", "pct": "%{y:.1%}"}
METRIC_FMT = {"revenue": "money", "profit": "money", "orders": "count", "margin": "pct"}
AXIS_FMT = {"money": "$~s", "count": "~s", "pct": ".0%"}


def fmt(value, kind: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    return {
        "money": charts.money(value),
        "count": f"{value:,.0f}",
        "pct": charts.pct(value),
        "days": f"{value:.1f} days",
    }.get(kind, f"{value:,.2f}")


def period_label(window) -> str:
    return window.compare_short or window.preset


# ----------------------------------------------------------
# KPI row
# ----------------------------------------------------------

def _revenue_target(ctx) -> tuple[float | None, str]:
    """Progress toward the saved monthly targets that fall inside the window."""
    targets = db.load_targets(ctx.dataset.digest)
    if targets.empty:
        return None, ""
    months = pd.period_range(ctx.window.start, ctx.window.end, freq="M").astype(str)
    in_window = targets[targets["month"].isin(months)]
    total = in_window["revenue_target"].sum()
    if not total:
        return None, ""
    progress = ctx.cur["revenue"].sum() / total
    return progress, f"{progress:.0%} of {charts.money(total)} target"


def kpi_row(ctx, keys, labels: dict | None = None) -> None:
    """KPI tiles with change vs the comparison period and a 12-month sparkline."""
    now = metrics.kpis(ctx.cur)
    before = metrics.kpis(ctx.prev) if ctx.prev is not None and not ctx.prev.empty else {}
    keys = [k for k in keys if k in now]
    period = period_label(ctx.window)
    spark_from = (ctx.window.end - pd.DateOffset(months=12)).normalize()
    recent = ctx.hist[ctx.hist["order_date"] > spark_from]
    target, target_label = _revenue_target(ctx) if "revenue" in keys else (None, "")
    for col, key in zip(st.columns(len(keys)), keys):
        k = now[key]
        spark = metrics.kpi_series(recent, key).tolist() if not recent.empty else None
        with col:
            ui.kpi_tile(
                (labels or {}).get(key, k.label), fmt(k.value, k.fmt),
                change=metrics.change(k, before.get(key)),
                period=period, higher_is_better=k.higher_is_better, kind=k.kind,
                spark=spark,
                target_progress=target if key == "revenue" else None,
                target_label=target_label if key == "revenue" else "",
            )


# ----------------------------------------------------------
# Trend card
# ----------------------------------------------------------

def trend_chart(ctx, key: str, metric: str, grain: str, height: int = 300) -> None:
    """Current period as a solid line, the comparison period dashed and muted."""
    t = charts.tokens_for(charts.current_mode())
    kind = METRIC_FMT[metric]
    current = metrics.series(ctx.cur, metric, grain)
    fig = go.Figure()
    if ctx.prev is not None and not ctx.prev.empty:
        compared = metrics.comparison_series(ctx.prev, current, ctx.window, metric, grain)
        fig.add_scatter(
            x=current.index, y=compared.values, name="Comparison period", mode="lines",
            line=dict(dash="dot", color=t["text_3"], width=2), hovertemplate=HOVER[kind],
        )
    fig.add_scatter(
        x=current.index, y=current.values, name=METRIC_LABELS[metric],
        mode="lines+markers" if len(current) <= 36 else "lines",
        line=dict(color=t["accent"], width=2), marker=dict(size=6),
        hovertemplate=HOVER[kind],
    )
    x_format = {"Day": "%b %d", "Week": "%b %d", "Month": "%b %Y", "Quarter": "Q%q %Y"}[grain]
    charts.style(fig, height=height, legend=True, y_format=AXIS_FMT[kind], x_format=x_format)
    if kind == "money" and (current.min() if len(current) else 0) >= 0:
        fig.update_yaxes(rangemode="tozero")
    charts.show(fig, key=key)


def trend_card(ctx, key: str, title: str = "Trend", metrics_offered=("revenue", "profit", "orders")) -> None:
    offered = [m for m in metrics_offered if m in ("revenue", "orders") or "profit" in ctx.cur.columns]
    with ui.card(key, title, f"{ctx.window.label}" + (f" · dotted line {period_label(ctx.window)}"
                                                      if ctx.prev is not None else "")):
        a, b = st.columns([1, 1], vertical_alignment="center")
        metric = a.segmented_control(
            "Metric", offered, default=offered[0], key=f"{key}-metric",
            format_func=lambda m: METRIC_LABELS[m], label_visibility="collapsed",
        ) or offered[0]
        with b:
            with st.container(horizontal=True, horizontal_alignment="right"):
                grain = st.segmented_control(
                    "Grain", list(metrics.GRAIN_FREQ), key=f"{key}-grain",
                    default=metrics.auto_grain(ctx.window.start, ctx.window.end),
                    label_visibility="collapsed",
                ) or metrics.auto_grain(ctx.window.start, ctx.window.end)
        trend_chart(ctx, f"{key}-chart", metric, grain)


# ----------------------------------------------------------
# Ranked bars + cross-filtering
# ----------------------------------------------------------

def rank_bars(table: pd.DataFrame, dim: str, value: str = "revenue", *, color_map: dict | None = None,
              kind: str = "money", height: int | None = None, max_items: int = 12,
              note: str | None = None) -> go.Figure:
    """
    Horizontal bars, largest first, labelled outside the bar. Bars are one
    color unless a color_map is given (only when color must carry identity
    across charts). `note` names a 'pct' column appended to each label,
    e.g. note="margin" gives "$250.1K · 17.5% margin".
    """
    t = charts.tokens_for(charts.current_mode())
    data = table.nlargest(max_items, value) if len(table) > max_items else table.sort_values(value, ascending=False)
    labels = [fmt(v, kind) for v in data[value]]
    if note and note in data:
        labels = [f"{label}  ·  {fmt(n, 'pct')} {note}" for label, n in zip(labels, data[note])]
    base = charts.series_colors()[0]
    colors = [color_map.get(str(v), base) for v in data[dim]] if color_map else base
    fig = go.Figure(go.Bar(
        x=data[value], y=data[dim].astype(str), orientation="h", customdata=data[[dim]].astype(str),
        marker_color=colors, text=labels, textposition="outside", cliponaxis=False,
        textfont=dict(color=t["text_2"]),
        hovertemplate="%{y}: " + {"money": "%{x:$,.0f}", "count": "%{x:,.0f}", "pct": "%{x:.1%}"}[kind]
                      + "<extra></extra>",
    ))
    charts.style(fig, height=height or max(160, 34 * len(data) + 30), x_format=AXIS_FMT[kind],
                 hovermode="closest")
    fig.update_yaxes(showgrid=False, autorange="reversed", ticksuffix="  ")
    fig.update_xaxes(showgrid=True, gridcolor=t["grid"])
    if len(data) and data[value].min() >= 0:
        charts.hbar_room(fig, float(data[value].max()), room=1.6 if note else 1.18)
    return fig


def selected_values(event) -> list[str]:
    """Values picked in a chart (from customdata[0], else the point's label/y/location)."""
    points = getattr(getattr(event, "selection", None), "points", None) or []
    values = []
    for p in points:
        custom = p.get("customdata")
        if isinstance(custom, (list, tuple)) and custom:
            values.append(str(custom[0]))
        elif custom is not None and not isinstance(custom, (list, tuple)):
            values.append(str(custom))
        else:
            for field in ("label", "location", "y"):
                if p.get(field) is not None:
                    values.append(str(p[field]))
                    break
    return list(dict.fromkeys(values))


def filter_chart(fig: go.Figure, key: str, dim: str) -> None:
    """
    Chart whose clicks add a global filter (region, category, segment): the
    value becomes a chip and every chart on every page updates.
    """
    event = charts.show(fig, key=f"{key}-{filters.selection_nonce()}", on_select="rerun")
    values = selected_values(event)
    if values and dim in filters.FILTER_DIMS:
        filters.queue_filter(dim, values)
        st.rerun()


def drill_chart(fig: go.Figure, key: str) -> list[str]:
    """Chart whose clicks drill into the current page only. Returns the picked values."""
    return selected_values(charts.show(fig, key=key, on_select="rerun"))


# ----------------------------------------------------------
# Tables
# ----------------------------------------------------------

def download(df: pd.DataFrame, filename: str, key: str, label: str = "CSV") -> None:
    st.download_button(
        label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv",
        icon=":material/download:", key=key, type="tertiary",
    )


def pct_column(label: str, **kwargs) -> st.column_config.NumberColumn:
    """One-decimal percent. Pair with as_percent() so the column holds 12.5, not 0.125."""
    return st.column_config.NumberColumn(label, format="%.1f%%", **kwargs)


def as_percent(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    return df.assign(**{c: df[c] * 100 for c in cols if c in df})


def change_column(label: str = "Change") -> st.column_config.NumberColumn:
    """Signed percent. The column must hold percent units (12.5, not 0.125)."""
    return st.column_config.NumberColumn(label, format="%+.1f%%")

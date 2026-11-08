"""Component gallery: every UI building block, rendered with real sample data.

A review page for the design system (Phase 1 checkpoint). It uses the same
components and chart rules the real pages will use.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics
from ui import charts
from ui import components as ui
from ui import shell

ctx = shell.page("Design system", "Every component in one place, rendered with the active dataset.")
if ctx is None:
    st.stop()

cur, prev, window = ctx.cur, ctx.prev, ctx.window
period = window.compare_short or window.preset

# ----------------------------------------------------------
# KPI tiles
# ----------------------------------------------------------

st.space("small")
st.subheader("KPI tiles")

now, before = metrics.kpis(cur), (metrics.kpis(prev) if prev is not None else {})
monthly = {key: metrics.series(cur, key).tail(12).tolist() for key in ("revenue", "profit", "orders")}


def show_value(k: metrics.KPI) -> str:
    if k.value is None:
        return "—"
    return {
        "money": charts.money(k.value),
        "count": f"{k.value:,.0f}",
        "pct": charts.pct(k.value),
        "days": f"{k.value:.1f} days",
    }.get(k.fmt, f"{k.value:,.2f}")


tiles = [key for key in ("revenue", "profit", "margin", "orders", "aov") if key in now]
cols = st.columns(len(tiles))
for col, key in zip(cols, tiles):
    k = now[key]
    with col:
        ui.kpi_tile(
            k.label, show_value(k),
            change=metrics.change(k, before.get(key)),
            period=period, higher_is_better=k.higher_is_better, kind=k.kind,
            spark=monthly.get(key),
            target_progress=0.82 if key == "revenue" else None,
            target_label="82% of annual target (example)" if key == "revenue" else "",
        )

# ----------------------------------------------------------
# Chart cards
# ----------------------------------------------------------

st.space("small")
st.subheader("Chart cards")
left, right = st.columns([2, 1], gap="medium")

with left:
    with ui.card("trend", "Revenue trend", f"Monthly revenue, {window.label} {period}"):
        current = metrics.series(cur, "revenue")
        fig = go.Figure()
        if prev is not None and not prev.empty:
            previous = metrics.series(prev, "revenue")
            shifted = previous.copy()
            shifted.index = current.index[: len(previous)] if len(previous) <= len(current) else shifted.index
            fig.add_scatter(
                x=shifted.index, y=shifted.values, name="Comparison period", mode="lines",
                line=dict(dash="dot", color=charts.tokens_for(charts.current_mode())["text_3"]),
                hovertemplate="%{y:$,.0f}",
            )
        fig.add_scatter(
            x=current.index, y=current.values, name="Revenue", mode="lines+markers",
            line=dict(color=charts.series_colors()[0], width=2), marker=dict(size=6),
            hovertemplate="%{y:$,.0f}",
        )
        charts.style(fig, height=300, legend=True, y_format="$~s", x_format="%b %Y")
        charts.show(fig, key="g-trend")

with right:
    with ui.card("alerts", "Alerts", "Example alert styles (real anomaly detection arrives in Phase 3)."):
        ui.item_list([
            {"tone": "bad", "title": "Furniture margin down 4.1pp", "body": "Example of a critical alert."},
            {"tone": "warn", "title": "Average discount rising", "body": "Example of a warning."},
            {"tone": "good", "title": "Technology revenue up 20%", "body": "Example of a positive signal."},
            {"tone": "info", "title": "New customers steady", "body": "Example of an informational note."},
        ])

c1, c2 = st.columns(2, gap="medium")
with c1:
    by_cat = metrics.breakdown(cur, "category") if "category" in cur else None
    with ui.card("cats", "Revenue by category", "Colors follow the category, not its rank."):
        if by_cat is not None:
            cmap = charts.stable_color_map(ctx.df["category"].unique())
            fig = go.Figure(go.Bar(
                x=by_cat["revenue"], y=by_cat["category"], orientation="h",
                marker_color=[cmap[c] for c in by_cat["category"]],
                text=[charts.money(v) for v in by_cat["revenue"]], textposition="outside",
                cliponaxis=False, hovertemplate="%{y}: %{x:$,.0f}<extra></extra>",
            ))
            charts.style(fig, height=240, x_format="$~s", hovermode="closest")
            fig.update_yaxes(showgrid=False, autorange="reversed")
            fig.update_xaxes(showgrid=True, gridcolor=charts.tokens_for(charts.current_mode())["grid"])
            charts.hbar_room(fig, by_cat["revenue"].max())
            charts.show(fig, key="g-cats")
with c2:
    with ui.card("regions", "Region table", "Native table with formatted columns and inline bars."):
        if "region" in cur:
            table = metrics.breakdown(cur, "region")
            st.dataframe(
                table[["region", "revenue", "profit", "margin", "share"]] if "profit" in table else table,
                hide_index=True, width="stretch", height=charts.table_height(len(table)),
                column_config={
                    "region": st.column_config.TextColumn("Region"),
                    "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                    "profit": st.column_config.NumberColumn("Profit", format="dollar"),
                    "margin": st.column_config.NumberColumn("Margin", format="percent"),
                    "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=1),
                },
            )

# ----------------------------------------------------------
# Small pieces
# ----------------------------------------------------------

st.space("small")
st.subheader("Small pieces")
a, b = st.columns(2, gap="medium")
with a:
    with ui.card("pieces", "Pills, deltas, chips"):
        st.html(
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">'
            + ui.pill("On track", "good") + ui.pill("At risk", "warn") + ui.pill("Critical", "bad")
            + ui.pill("New", "info") + ui.pill("Sample", "neutral")
            + ui.delta_badge(0.204) + ui.delta_badge(-0.071) + ui.delta_badge(0.0016, higher_is_better=False, kind="pp")
            + "</div>"
        )
        ui.stat_chips([("Orders", "1,692"), ("Customers", "693"), ("Units", "12,503"), ("Avg ship", "3.9 days")])
        st.space("small")
        ui.stepper(["Upload", "Map columns", "Review"], active=1)
with b:
    with ui.card("states", "Empty and locked states"):
        ui.empty_state("No orders in this range", "Try a wider date range such as Last 12 months.")

st.space("small")
st.subheader("Controls")
with ui.card("controls", "Native widgets in the house style"):
    x, y, z = st.columns(3)
    x.segmented_control("Grain", ["Day", "Week", "Month", "Quarter"], default="Month", key="g-grain")
    y.selectbox("Metric", ["Revenue", "Profit", "Orders"], key="g-metric")
    z.slider("Horizon (months)", 3, 12, 6, key="g-h")
    b1, b2, b3, _ = st.columns([1, 1, 1, 2])
    b1.button("Primary", type="primary", width="stretch")
    b2.button("Secondary", width="stretch")
    b3.button("Tertiary", type="tertiary", width="stretch")

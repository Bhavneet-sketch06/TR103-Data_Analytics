"""Overview: headline KPIs, the trend, what changed, and where."""

from __future__ import annotations

import streamlit as st

from core import insights, metrics
from core.schema import FIELD_BY_KEY
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Overview", "How the business is doing in the selected period.")
if ctx is None:
    st.stop()
if ctx.cur.empty:
    ui.empty_state("No orders in this range", "Try a wider date range, or clear some filters.")
    st.stop()

cur, prev, window = ctx.cur, ctx.prev, ctx.window
period = blocks.period_label(window)

# ----------------------------------------------------------
# KPIs
# ----------------------------------------------------------

st.space("small")
preferred = ["revenue", "profit", "margin", "orders", "aov", "customers", "units"]
available = [k for k in preferred if k in metrics.kpis(cur)]
blocks.kpi_row(ctx, available[:5])

# ----------------------------------------------------------
# Trend + highlights
# ----------------------------------------------------------

st.space("small")
left, right = st.columns([2, 1], gap="medium")
with left:
    blocks.trend_card(ctx, "ov-trend", "Performance over time")
with right:
    with ui.card("ov-highlights", "What changed", f"Biggest moves {period}" if prev is not None else ""):
        items = insights.highlights(cur, prev, period)
        if items:
            ui.item_list(items)
        else:
            ui.empty_state("No comparison period",
                           "Choose “Same period last year” or “Previous period” to see what changed.",
                           icon_name="chart")

# ----------------------------------------------------------
# Breakdowns (click a bar to filter every page)
# ----------------------------------------------------------

dims = [d for d in ("category", "region", "segment") if d in cur.columns][:2]
if dims:
    st.space("small")
    for col, dim in zip(st.columns(len(dims), gap="medium"), dims):
        label = FIELD_BY_KEY[dim].label
        table = metrics.breakdown(cur, dim)
        with col:
            with ui.card(f"ov-{dim}", f"Revenue by {label.lower()}", "Click a bar to filter every page."):
                fig = blocks.rank_bars(table, dim, "revenue", note="margin" if "margin" in table else None,
                                       max_items=8)
                blocks.filter_chart(fig, f"ov-{dim}-bars", dim)

# ----------------------------------------------------------
# Top movers
# ----------------------------------------------------------

mover_dims = [d for d in ("category", "sub_category", "region", "state", "segment", "product") if d in cur.columns]
if mover_dims:
    st.space("small")
    subtitle = (f"Largest revenue changes {period}, gainers and decliners."
                if prev is not None else "Largest contributors in the selected period.")
    with ui.card("ov-movers", "Top movers", subtitle):
        a, b = st.columns([3, 1], vertical_alignment="center")
        dim = a.segmented_control(
            "Group by", mover_dims, default=mover_dims[min(1, len(mover_dims) - 1)], key="ov-movers-dim",
            format_func=lambda d: FIELD_BY_KEY[d].label, label_visibility="collapsed",
        ) or mover_dims[0]
        label = FIELD_BY_KEY[dim].label
        if prev is not None and not prev.empty:
            table = metrics.top_movers(cur, prev, dim, "revenue", n=10)
            table["change_pct"] = table["change_pct"] * 100
            config = {
                dim: st.column_config.TextColumn(label, width="medium"),
                "current": st.column_config.NumberColumn("Revenue", format="dollar"),
                "previous": st.column_config.NumberColumn(f"Revenue ({window.compare_short.replace('vs ', '')})",
                                                          format="dollar"),
                "change": st.column_config.NumberColumn("Change", format="dollar"),
                "change_pct": blocks.change_column("Change %"),
            }
        else:
            table = metrics.breakdown(cur, dim).head(10)
            table = table[[c for c in (dim, "revenue", "profit", "margin", "share") if c in table]]
            table = blocks.as_percent(table, "margin")
            config = {
                dim: st.column_config.TextColumn(label, width="medium"),
                "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                "profit": st.column_config.NumberColumn("Profit", format="dollar"),
                "margin": blocks.pct_column("Margin"),
                "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=1),
            }
        with b:
            with st.container(horizontal=True, horizontal_alignment="right"):
                blocks.download(table, f"top_movers_{dim}.csv", key="ov-movers-dl")
        st.dataframe(table, hide_index=True, width="stretch", height=charts.table_height(len(table)),
                     column_config=config)

"""Customers: who buys, who comes back, and who is slipping away."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics
from core.analytics import customers
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Customers", "Who buys, who comes back, and who is slipping away.",
                 needs=("customers",), feature="Customer analytics")
if ctx is None:
    st.stop()
if ctx.cur.empty:
    ui.empty_state("No orders in this range", "Try a wider date range, or clear some filters.")
    st.stop()

cur, prev, hist, window = ctx.cur, ctx.prev, ctx.hist, ctx.window
t = charts.tokens_for(charts.current_mode())
period = blocks.period_label(window)

# ----------------------------------------------------------
# KPIs
# ----------------------------------------------------------

st.space("small")
now = customers.summary(cur, hist, window.start)
before = None
if prev is not None and not prev.empty:
    before = customers.summary(prev, hist[hist["order_date"] <= window.prev_end], window.prev_start)


def _change(key: str, pp: bool = False):
    if before is None or now[key] is None or before[key] is None:
        return None
    if pp:
        return now[key] - before[key]
    return (now[key] - before[key]) / before[key] if before[key] else None


spark_from = (window.end - pd.DateOffset(months=12)).normalize()
recent = hist[hist["order_date"] > spark_from]
tiles = [
    ("Customers", f"{now['customers']:,}", _change("customers"), "pct",
     metrics.kpi_series(recent, "customers").tolist()),
    ("New customers", f"{now['new']:,}", _change("new"), "pct", None),
    ("Repeat rate", charts.pct(now["repeat_rate"]), _change("repeat_rate", pp=True), "pp", None),
    ("Avg spend", charts.money(now["revenue_per_customer"]), _change("revenue_per_customer"),
     "pct", None),
    ("Avg orders", f"{now['orders_per_customer']:.2f}", _change("orders_per_customer"), "pct", None),
]
helps = {
    "New customers": "Customers whose first-ever order falls in this period.",
    "Repeat rate": "Share of this period's customers who have ordered more than once, ever.",
    "Avg spend": "Revenue per customer in this period.",
    "Avg orders": "Orders per customer in this period.",
}
for col, (label, value, change, kind, spark) in zip(st.columns(len(tiles)), tiles):
    with col:
        ui.kpi_tile(label, value, change=change, period=period, kind=kind, spark=spark,
                    help_text=helps.get(label, ""))

# ----------------------------------------------------------
# RFM segments
# ----------------------------------------------------------

st.space("small")
rfm = customers.rfm(hist, as_of=window.end)
segments = customers.segment_summary(rfm)
with ui.card("cust-rfm", "Customer segments",
             f"RFM segments as of {window.end:%b %d, %Y}: how recently, how often and how much each customer buys."):
    left, right = st.columns([2, 3], gap="large")
    with left:
        fig = go.Figure(go.Bar(
            x=segments["customers"], y=segments["segment"], orientation="h",
            marker_color=charts.series_colors()[0],
            text=[f"{c:,}  ·  {s:.0%}" for c, s in zip(segments["customers"], segments["customer_share"])],
            textposition="outside", cliponaxis=False, textfont=dict(color=t["text_2"]),
            hovertemplate="%{y}: %{x:,} customers<extra></extra>",
        ))
        charts.style(fig, height=34 * len(segments) + 40, hovermode="closest")
        fig.update_yaxes(autorange="reversed", showgrid=False, ticksuffix="  ")
        fig.update_xaxes(showgrid=True, gridcolor=t["grid"])
        charts.hbar_room(fig, float(segments["customers"].max()), room=1.35)
        charts.show(fig, key="cust-rfm-bars")
    with right:
        st.dataframe(
            blocks.as_percent(segments, "revenue_share"), hide_index=True, width="stretch",
            height=charts.table_height(len(segments)),
            column_order=["segment", "revenue_share", "avg_recency", "avg_orders", "description"],
            column_config={
                "segment": st.column_config.TextColumn("Segment"),
                "revenue_share": blocks.pct_column("Revenue", width="small",
                                                   help="Share of all-time revenue from this segment"),
                "avg_recency": st.column_config.NumberColumn("Recency", format="%.0f d", width="small",
                                                             help="Average days since the last order"),
                "avg_orders": st.column_config.NumberColumn("Orders", format="%.1f", width="small",
                                                            help="Average orders per customer, all history"),
                "description": st.column_config.TextColumn("What it means", width="large"),
            },
        )
    with st.container(horizontal=True, horizontal_alignment="right"):
        export = rfm.merge(cur.groupby("customer_id", observed=True).size().rename("lines_in_period"),
                           left_on="customer_id", right_index=True, how="left")
        blocks.download(export.drop(columns=["r", "f", "m"]), "customer_segments.csv", key="cust-rfm-dl",
                        label="Customer list (CSV)")

# ----------------------------------------------------------
# Cohort retention
# ----------------------------------------------------------

st.space("small")
grain = customers.cohort_grain(hist)
unit = "month" if grain == "M" else "quarter"
matrix = customers.cohorts(hist, grain, n_cohorts=12, max_age=12, min_size=10)
with ui.card("cust-cohorts", "Retention by cohort",
             f"Customers grouped by the {unit} of their first order; each cell is the share who ordered again "
             f"that many {unit}s later. Cohorts under 10 customers are hidden."):
    if matrix.empty:
        ui.empty_state("Not enough customers for cohorts", "Each cohort needs at least 10 customers.")
    else:
        ages = [c for c in matrix.columns if c != "size"]
        labels = [(f"{d:%b %Y}" if grain == "M" else f"{d.year} Q{d.quarter}") + f"  ({n})"
                  for d, n in zip(matrix.index, matrix["size"])]
        z = matrix[ages].to_numpy(dtype=float)
        shown = z.copy()
        shown[:, 0] = float("nan")          # period 0 is always 100%; keep it out of the color scale
        text = [[("" if pd.isna(v) else f"{v:.0%}") for v in row] for row in z]
        x = [str(a) for a in ages]
        fig = go.Figure(go.Heatmap(
            z=shown, x=x, y=labels, text=text, colorscale=charts.sequential_scale(), showscale=False,
            xgap=2, ygap=2, hoverongaps=False,
            hovertemplate=f"%{{y}}<br>{unit.title()} %{{x}}: %{{text}} active<extra></extra>",
        ))
        charts.heatmap_labels(fig, x, labels, shown, text)
        charts.style(fig, height=34 * len(labels) + 60, hovermode="closest")
        fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
        fig.update_xaxes(side="top", type="category", title_text=f"{unit.title()}s since first order",
                         title_font=dict(size=11, color=t["text_3"]))
        charts.show(fig, key="cust-cohorts")
        st.caption(f"Cohort size in brackets. {unit.title()} 0 is the first {unit} (always 100%).")

# ----------------------------------------------------------
# New vs returning + top customers
# ----------------------------------------------------------

st.space("small")
left, right = st.columns([1, 1], gap="medium")

with left:
    mix_grain = "Month" if (window.end - window.start).days > 120 else "Week"
    mix = customers.new_vs_returning(hist, window.start, window.end, mix_grain)
    with ui.card("cust-mix", "New vs returning revenue", f"Revenue by {mix_grain.lower()} and customer type."):
        colors = charts.series_colors()
        fig = go.Figure()
        for kind, color in (("Returning", colors[0]), ("New", colors[1])):
            part = mix[mix["kind"] == kind]
            fig.add_bar(x=part["period"], y=part["revenue"], name=kind, marker_color=color,
                        hovertemplate=f"{kind}: %{{y:$,.0f}}<extra></extra>")
        charts.style(fig, height=300, legend=True, y_format="$~s",
                     x_format="%b %Y" if mix_grain == "Month" else "%b %d")
        fig.update_layout(barmode="stack", bargap=0.35)
        fig.update_traces(marker_line_width=2, marker_line_color=t["surface"])
        charts.show(fig, key="cust-mix")
        value = customers.lifetime_value(hist)
        new_share = mix.loc[mix["kind"] == "New", "revenue"].sum() / mix["revenue"].sum() if len(mix) else 0
        ui.stat_chips([
            ("From new customers", f"{new_share:.0%} of revenue"),
            ("Avg lifetime revenue", charts.money(value["avg_revenue"])),
            ("Value per year", charts.money(value["yearly_value"])),
        ])

with right:
    with ui.card("cust-top", "Top customers", "Highest revenue in the selected period."):
        top = customers.top_customers(cur, n=12)
        name_col = "customer_name" if "customer_name" in top else "customer_id"
        top = top.merge(rfm[["customer_id", "segment"]], on="customer_id", how="left")
        columns = [name_col, "segment", "revenue", "orders"]
        st.dataframe(
            top[columns], hide_index=True, width="stretch", height=charts.table_height(len(top)),
            column_config={
                name_col: st.column_config.TextColumn("Customer", width="medium"),
                "segment": st.column_config.TextColumn("Segment"),
                "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                "orders": st.column_config.NumberColumn("Orders", format="%d", width="small"),
                "profit": st.column_config.NumberColumn("Profit", format="dollar"),
            },
        )
        share = top["revenue"].sum() / cur["revenue"].sum()
        st.caption(f"These {len(top)} customers made {share:.0%} of revenue in the period.")

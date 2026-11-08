"""Operations: how discounting affects margin, and how fast orders ship."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics
from core.analytics import operations, products
from core.schema import FIELD_BY_KEY
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Operations", "How discounting affects margin, and how fast orders ship.")
if ctx is None:
    st.stop()
has_discount = "discount" in ctx.df.columns
has_shipping = "ship_days" in ctx.df.columns
if not (has_discount or has_shipping):
    ui.locked_state("Operations", [FIELD_BY_KEY["discount"].label, FIELD_BY_KEY["ship_date"].label])
    st.stop()
if ctx.cur.empty:
    ui.empty_state("No orders in this range", "Try a wider date range, or clear some filters.")
    st.stop()

cur, prev, window = ctx.cur, ctx.prev, ctx.window
t = charts.tokens_for(charts.current_mode())
has = set(cur.columns)
period = blocks.period_label(window)
has_prev = prev is not None and not prev.empty
diverging = charts.diverging_scale()
NEG, POS = diverging[1][1], diverging[-2][1]


# ----------------------------------------------------------
# KPIs
# ----------------------------------------------------------

def ops_numbers(df: pd.DataFrame) -> dict:
    out = {}
    if "discount" in df:
        out["discount"] = df["discount"].mean()
        out["discounted_share"] = df.loc[df["discount"] > 0, "revenue"].sum() / df["revenue"].sum()
    if "profit" in df:
        out["loss_share"] = (df["profit"] < 0).mean()
    if "ship_days" in df:
        per_order = df.groupby("order_id", observed=True)["ship_days"].max()
        out["ship_days"] = per_order.mean()
        out["slow_share"] = (per_order > 5).mean()
    return out


now = ops_numbers(cur)
before = ops_numbers(prev) if has_prev else {}


def delta(key: str, pp: bool):
    if key not in before or pd.isna(before[key]) or pd.isna(now[key]):
        return None
    return now[key] - before[key] if pp else ((now[key] - before[key]) / before[key] if before[key] else None)


tiles = []
if "discount" in now:
    tiles += [("Avg discount", charts.pct(now["discount"]), delta("discount", True), "pp",
               "Average discount across order lines."),
              ("Discounted sales", charts.pct(now["discounted_share"]), delta("discounted_share", True), "pp",
               "Share of revenue sold at any discount.")]
if "loss_share" in now:
    tiles.append(("Loss lines", charts.pct(now["loss_share"]), delta("loss_share", True), "pp",
                  "Share of order lines with negative profit."))
if "ship_days" in now:
    tiles += [("Avg ship time", f"{now['ship_days']:.1f} days", delta("ship_days", False), "pct",
               "Average days from order to shipment, per order."),
              ("Slow orders", charts.pct(now["slow_share"]), delta("slow_share", True), "pp",
               "Share of orders that took more than 5 days to ship.")]
st.space("small")
for col, (label, value, change, kind, help_text) in zip(st.columns(len(tiles)), tiles):
    with col:
        ui.kpi_tile(label, value, change=change, period=period, kind=kind,
                    higher_is_better=False, help_text=help_text)

# ----------------------------------------------------------
# Discounts
# ----------------------------------------------------------

if has_discount:
    st.space("medium")
    ui.render('<div class="is-section-title">Discounts</div>')
    bands = products.discount_bands(cur)
    if "margin" in bands:
        left, right = st.columns(2, gap="medium")
        with left:
            with ui.card("ops-band-margin", "Profit margin by discount band",
                         "Bigger discounts, thinner margins. Observed in your data, not proven cause and effect."):
                fig = go.Figure(go.Bar(
                    x=bands["band"].astype(str), y=bands["margin"],
                    marker_color=[POS if m >= 0 else NEG for m in bands["margin"]],
                    text=[charts.pct(m) for m in bands["margin"]], textposition="outside", cliponaxis=False,
                    textfont=dict(color=t["text_2"]),
                    hovertemplate="%{x}: %{y:.1%} margin<extra></extra>",
                ))
                charts.style(fig, height=300, y_format=".0%", hovermode="closest")
                fig.add_hline(y=0, line_color=t["border_strong"], line_width=1)
                lo, hi = float(bands["margin"].min()), float(bands["margin"].max())
                pad = (hi - lo) * 0.15 or 0.05
                fig.update_yaxes(range=[min(lo, 0) - pad, max(hi, 0) + pad])
                charts.show(fig, key="ops-band-margin")
        with right:
            with ui.card("ops-band-loss", "Loss-making lines by discount band",
                         "Share of order lines in each band that lost money."):
                fig = go.Figure(go.Bar(
                    x=bands["band"].astype(str), y=bands["loss_share"], marker_color=charts.series_colors()[0],
                    text=[charts.pct(v, 0) for v in bands["loss_share"]], textposition="outside",
                    cliponaxis=False, textfont=dict(color=t["text_2"]),
                    hovertemplate="%{x}: %{y:.1%} of lines lost money<extra></extra>",
                ))
                charts.style(fig, height=300, y_format=".0%", hovermode="closest")
                fig.update_yaxes(range=[0, min(1.08, float(bands["loss_share"].max()) * 1.2 + 0.02)])
                charts.show(fig, key="ops-band-loss")

    left, right = st.columns([5, 7], gap="medium")
    with left:
        with ui.card("ops-band-table", "Discount bands", "Volume and profit in each band."):
            cols = [c for c in ("band", "lines", "revenue_share", "profit", "margin") if c in bands]
            st.dataframe(
                blocks.as_percent(bands[cols].astype({"band": str}), "revenue_share", "margin"),
                hide_index=True, width="stretch", height=charts.table_height(len(bands)),
                column_config={
                    "band": st.column_config.TextColumn("Discount"),
                    "lines": st.column_config.NumberColumn("Lines", format="%d", width="small"),
                    "revenue_share": blocks.pct_column("Revenue", width="small"),
                    "profit": st.column_config.NumberColumn("Profit", format="dollar"),
                    "margin": blocks.pct_column("Margin", width="small"),
                },
            )
    with right:
        dim = "sub_category" if "sub_category" in has else ("category" if "category" in has else None)
        if dim and "profit" in has:
            label = FIELD_BY_KEY[dim].label
            with ui.card("ops-scatter", f"Discount vs margin by {label.lower()}",
                         "Bubble size = revenue. Loss-making ones are labelled."):
                agg = cur.groupby(dim, observed=True).agg(
                    discount=("discount", "mean"), revenue=("revenue", "sum"), profit=("profit", "sum"),
                ).reset_index()
                agg["margin"] = agg["profit"] / agg["revenue"].where(agg["revenue"] != 0)
                worst = set(agg[agg["margin"] < 0].nsmallest(5, "margin")[dim])
                sizes = 12 + 36 * (agg["revenue"] / agg["revenue"].max()) ** 0.5
                fig = go.Figure(go.Scatter(
                    x=agg["discount"], y=agg["margin"], mode="markers+text",
                    text=[str(v) if v in worst else "" for v in agg[dim]], textposition="top center",
                    textfont=dict(size=11, color=t["text_2"]),
                    marker=dict(size=sizes, color=[POS if m >= 0 else NEG for m in agg["margin"]],
                                opacity=0.85, line=dict(width=2, color=t["surface"])),
                    customdata=agg[[dim, "revenue"]],
                    hovertemplate="<b>%{customdata[0]}</b><br>Avg discount %{x:.1%}<br>Margin %{y:.1%}"
                                  "<br>Revenue %{customdata[1]:$,.0f}<extra></extra>",
                ))
                charts.style(fig, height=charts.table_height(len(bands)), y_format=".0%", x_format=".0%",
                             hovermode="closest")
                fig.add_hline(y=0, line_color=t["border_strong"], line_width=1)
                fig.update_xaxes(showgrid=True, gridcolor=t["grid"], title_text="Average discount",
                                 title_font=dict(size=11, color=t["text_3"]))
                fig.update_yaxes(title_text="Profit margin", title_font=dict(size=11, color=t["text_3"]))
                charts.show(fig, key="ops-scatter")

# ----------------------------------------------------------
# Shipping
# ----------------------------------------------------------

if has_shipping:
    st.space("medium")
    ui.render('<div class="is-section-title">Shipping</div>')
    left, right = st.columns([7, 5], gap="medium")
    with left:
        if "ship_mode" in has:
            with ui.card("ops-modes", "Ship modes", "Speed, volume and margin for each way of shipping."):
                modes = operations.shipping_summary(cur)
                cols = [c for c in ("ship_mode", "orders", "order_share", "avg_days", "p90_days", "margin")
                        if c in modes]
                st.dataframe(
                    blocks.as_percent(modes[cols], "order_share", "margin"), hide_index=True, width="stretch",
                    height=charts.table_height(len(modes)),
                    column_config={
                        "ship_mode": st.column_config.TextColumn("Ship mode"),
                        "orders": st.column_config.NumberColumn("Orders", format="%d"),
                        "order_share": blocks.pct_column("Share"),
                        "avg_days": st.column_config.NumberColumn("Avg days", format="%.1f"),
                        "p90_days": st.column_config.NumberColumn("90% within", format="%.0f days",
                                                                  help="90% of orders shipped within this many days"),
                        "margin": blocks.pct_column("Margin"),
                    },
                )
        with ui.card("ops-ship-trend", "Ship time over time", "Average days from order to shipment."):
            grain = "Month" if (window.end - window.start).days > 120 else "Week"
            per_order = cur.groupby("order_id", observed=True).agg(order_date=("order_date", "min"),
                                                                 ship_days=("ship_days", "max"))
            trend = metrics.kpi_series(per_order, "ship_days", grain)
            fig = go.Figure(go.Scatter(x=trend.index, y=trend.values, mode="lines+markers",
                                       line=dict(color=t["accent"], width=2), marker=dict(size=6),
                                       hovertemplate="%{y:.1f} days<extra></extra>"))
            charts.style(fig, height=220, x_format="%b %Y" if grain == "Month" else "%b %d")
            fig.update_yaxes(rangemode="tozero", ticksuffix=" d")
            charts.show(fig, key="ops-ship-trend")
    with right:
        with ui.card("ops-ship-dist", "How long orders take", "Orders by days from order to shipment."):
            dist = operations.ship_days_distribution(cur)
            share = dist["orders"] / dist["orders"].sum()
            fig = go.Figure(go.Bar(
                x=dist["days"], y=dist["orders"], marker_color=charts.series_colors()[0],
                text=[f"{s:.0%}" for s in share], textposition="outside", cliponaxis=False,
                textfont=dict(color=t["text_2"]),
                hovertemplate="%{x} days: %{y:,} orders<extra></extra>",
            ))
            charts.style(fig, height=300, hovermode="closest")
            fig.update_xaxes(dtick=1, title_text="Days to ship", title_font=dict(size=11, color=t["text_3"]))
            fig.update_yaxes(range=[0, float(dist["orders"].max()) * 1.15])
            charts.show(fig, key="ops-ship-dist")

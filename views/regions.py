"""Regions: where revenue and margin come from, down to state and city."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics
from core.analytics import operations
from core.schema import FIELD_BY_KEY
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Regions", "Where revenue and margin come from, down to state and city.")
if ctx is None:
    st.stop()
if not ({"region", "state"} & set(ctx.df.columns)):
    ui.locked_state("Regional analysis", [FIELD_BY_KEY["region"].label, FIELD_BY_KEY["state"].label])
    st.stop()
if ctx.cur.empty:
    ui.empty_state("No orders in this range", "Try a wider date range, or clear some filters.")
    st.stop()

cur, prev, hist, window = ctx.cur, ctx.prev, ctx.hist, ctx.window
t = charts.tokens_for(charts.current_mode())
has = set(cur.columns)
period = blocks.period_label(window)
has_prev = prev is not None and not prev.empty

# ----------------------------------------------------------
# Region tiles
# ----------------------------------------------------------

if "region" in has:
    st.space("small")
    table = metrics.breakdown(cur, "region")
    shown = table.head(5)
    spark_from = (window.end - pd.DateOffset(months=12)).normalize()
    recent = hist[hist["order_date"] > spark_from]
    prev_rev = prev.groupby("region", observed=True)["revenue"].sum() if has_prev else pd.Series(dtype=float)
    for col, (_, row) in zip(st.columns(len(shown)), shown.iterrows()):
        before = prev_rev.get(row["region"])
        change = (row["revenue"] - before) / before if before else None
        spark = metrics.series(recent[recent["region"] == row["region"]], "revenue").tolist()
        margin = f"{row['margin']:.1%} margin · " if "margin" in row and pd.notna(row.get("margin")) else ""
        with col:
            ui.kpi_tile(str(row["region"]), charts.money(row["revenue"]), change=change,
                        period=f"{margin}{row['share']:.0%} of revenue", spark=spark)
    if len(table) > len(shown):
        st.caption(f"Top {len(shown)} of {len(table)} regions by revenue.")

# ----------------------------------------------------------
# Map / state ranking
# ----------------------------------------------------------

picked_state = None
if "state" in has:
    st.space("small")
    states = metrics.breakdown(cur, "state")
    if has_prev:
        before = prev.groupby("state", observed=True)["revenue"].sum()
        states["change_pct"] = [(r - before.get(s, 0)) / before.get(s) * 100 if before.get(s) else None
                                for s, r in zip(states["state"], states["revenue"])]
    is_us = operations.looks_like_us_states(states["state"])
    left, right = st.columns([7, 5], gap="medium")
    with left:
        with ui.card("reg-map", "Revenue by state" if is_us else "Top states",
                     "Click a state to explore it below."):
            options = ["revenue"] + (["margin"] if "margin" in states else [])
            metric = st.segmented_control(
                "Color by", options, default="revenue", key="reg-map-metric",
                format_func=lambda m: {"revenue": "Revenue", "margin": "Profit margin"}[m],
                label_visibility="collapsed",
            ) or "revenue"
            if is_us:
                codes = states["state"].map(operations.state_code)
                if metric == "margin":
                    bound = max(0.05, min(0.6, states["margin"].abs().quantile(0.95)))
                    colors = dict(colorscale=charts.diverging_scale(), zmid=0, zmin=-bound, zmax=bound)
                    tick = ".0%"
                else:
                    colors = dict(colorscale=charts.sequential_scale())
                    tick = "$~s"
                fig = go.Figure(go.Choropleth(
                    locations=codes, z=states[metric], locationmode="USA-states",
                    customdata=states[["state"]], **colors,
                    marker_line_color=t["surface"], marker_line_width=1,
                    colorbar=dict(thickness=10, len=0.7, outlinewidth=0, tickformat=tick,
                                  tickfont=dict(color=t["text_3"])),
                    hovertemplate="<b>%{customdata[0]}</b><br>"
                                  + ("Margin %{z:.1%}" if metric == "margin" else "Revenue %{z:$,.0f}")
                                  + "<extra></extra>",
                ))
                charts.style(fig, height=380, hovermode="closest")
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), geo=dict(
                    scope="usa", bgcolor="rgba(0,0,0,0)", lakecolor="rgba(0,0,0,0)",
                    landcolor=t["surface_2"], showlakes=False, subunitcolor=t["surface"],
                ))
            else:
                fig = blocks.rank_bars(states, "state", metric, kind="pct" if metric == "margin" else "money",
                                       max_items=12)
            picked = blocks.drill_chart(fig, f"reg-map-{metric}")
            picked_state = picked[0] if picked else None
    with right:
        with ui.card("reg-states", "State ranking", f"Revenue and margin in the period"
                     + (f", change {period}" if has_prev else "") + "."):
            columns = [c for c in ("state", "revenue", "margin", "change_pct") if c in states]
            st.dataframe(
                blocks.as_percent(states[columns], "margin"), hide_index=True, width="stretch", height=430,
                column_config={
                    "state": st.column_config.TextColumn("State"),
                    "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                    "margin": blocks.pct_column("Margin", width="small"),
                    "change_pct": st.column_config.NumberColumn("Change", format="%+.0f%%", width="small"),
                },
            )

# ----------------------------------------------------------
# Breakdown table
# ----------------------------------------------------------

levels = [d for d in ("region", "state", "city") if d in has]
st.space("small")
with ui.card("reg-table", "Breakdown", "Revenue, profit and margin at each geographic level."):
    a, b = st.columns([3, 1], vertical_alignment="center")
    level = a.segmented_control("Level", levels, default=levels[0], key="reg-level",
                                format_func=lambda d: FIELD_BY_KEY[d].label,
                                label_visibility="collapsed") or levels[0]
    keys = levels[: levels.index(level) + 1]
    agg = {"revenue": ("revenue", "sum"), "orders": ("order_id", "nunique")}
    if "profit" in has:
        agg["profit"] = ("profit", "sum")
    if "customer_id" in has:
        agg["customers"] = ("customer_id", "nunique")
    table = cur.groupby(keys, observed=True).agg(**agg).reset_index()
    if "profit" in table:
        table["margin"] = table["profit"] / table["revenue"].where(table["revenue"] != 0)
    if has_prev:
        before = prev.groupby(keys, observed=True)["revenue"].sum().rename("previous").reset_index()
        table = table.merge(before, on=keys, how="left")
        table["change_pct"] = (table["revenue"] - table["previous"]) / table["previous"].where(table["previous"] != 0) * 100
        table = table.drop(columns="previous")
    table = table.sort_values("revenue", ascending=False)
    with b:
        with st.container(horizontal=True, horizontal_alignment="right"):
            blocks.download(table, f"breakdown_{level}.csv", key="reg-table-dl")
    config = {k: st.column_config.TextColumn(FIELD_BY_KEY[k].label) for k in keys}
    config.update({
        "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
        "orders": st.column_config.NumberColumn("Orders", format="%d"),
        "customers": st.column_config.NumberColumn("Customers", format="%d"),
        "profit": st.column_config.NumberColumn("Profit", format="dollar"),
        "margin": blocks.pct_column("Margin"),
        "change_pct": blocks.change_column("Change"),
    })
    st.dataframe(blocks.as_percent(table, "margin"), hide_index=True, width="stretch",
                 height=charts.table_height(len(table), 12), column_config=config)
    st.caption(f"{len(table):,} rows")

# ----------------------------------------------------------
# State explorer
# ----------------------------------------------------------

if "state" in has:
    st.space("small")
    ranked = metrics.breakdown(cur, "state")["state"].astype(str).tolist()
    # A map click picks the state once; the dropdown stays free to change afterwards.
    if picked_state in ranked and st.session_state.get("_reg-last-pick") != picked_state:
        st.session_state["reg-explore"] = picked_state
    st.session_state["_reg-last-pick"] = picked_state
    with ui.card("reg-explore-card", "State explorer", "Pick a state, or click one on the map above."):
        state = st.selectbox("State", ranked, key="reg-explore", label_visibility="collapsed")
        rows = cur[cur["state"].astype(str) == state]
        prev_rows = prev[prev["state"].astype(str) == state] if has_prev else None
        k = metrics.kpis(rows)
        chips = [("Revenue", charts.money(k["revenue"].value)), ("Orders", f"{k['orders'].value:,.0f}")]
        if "margin" in k:
            chips.append(("Margin", charts.pct(k["margin"].value)))
        if "customers" in k:
            chips.append(("Customers", f"{k['customers'].value:,.0f}"))
        chips.append(("Share of revenue", f"{k['revenue'].value / cur['revenue'].sum():.1%}"))
        ui.stat_chips(chips)
        st.space("xsmall")
        left, right = st.columns([3, 2], gap="medium")
        with left:
            sub = shell.PageContext(dataset=ctx.dataset, df=ctx.df, cur=rows, prev=prev_rows,
                                    hist=hist[hist["state"].astype(str) == state], window=window)
            blocks.trend_chart(sub, f"reg-explore-trend-{state}", "revenue",
                               metrics.auto_grain(window.start, window.end), height=260)
        with right:
            dim = "city" if "city" in has else ("product" if "product" in has else None)
            if dim:
                top = metrics.breakdown(rows, dim).head(8)
                columns = [c for c in (dim, "revenue", "margin") if c in top]
                st.dataframe(
                    blocks.as_percent(top[columns], "margin"), hide_index=True, width="stretch",
                    height=charts.table_height(len(top), 8),
                    column_config={
                        dim: st.column_config.TextColumn(f"Top {FIELD_BY_KEY[dim].label.lower()}"),
                        "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                        "margin": blocks.pct_column("Margin", width="small"),
                    },
                )

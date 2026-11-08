"""Sales: what sells, how concentrated revenue is, seasonality and loss-makers."""

from __future__ import annotations

import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics
from core.analytics import products
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Sales", "What sells, how concentrated revenue is, and where money is lost.")
if ctx is None:
    st.stop()
if ctx.cur.empty:
    ui.empty_state("No orders in this range", "Try a wider date range, or clear some filters.")
    st.stop()

cur = ctx.cur
t = charts.tokens_for(charts.current_mode())
has = set(cur.columns)

st.space("small")
blocks.kpi_row(ctx, ["revenue", "units", "orders", "aov", "discount"])

# ----------------------------------------------------------
# Product mix (treemap) + concentration (Pareto)
# ----------------------------------------------------------

st.space("small")
left, right = st.columns([7, 5], gap="medium")

with left:
    if "category" in has:
        levels = ["category"] + (["sub_category"] if "sub_category" in has else [])
        with ui.card("sales-mix", "Product mix",
                     "Size = revenue, color = profit margin. Click a tile to zoom in, the top bar to zoom out."
                     if "profit" in has else "Size = revenue. Click a tile to zoom in."):
            grouped = cur.groupby(levels, observed=True).agg(
                revenue=("revenue", "sum"), **({"profit": ("profit", "sum")} if "profit" in has else {}),
            ).reset_index()
            ids, parents, labels, values, margins = [], [], [], [], []
            for cat, part in grouped.groupby("category", observed=True):
                ids.append(str(cat)); parents.append(""); labels.append(str(cat))
                values.append(part["revenue"].sum())
                margins.append(part["profit"].sum() / part["revenue"].sum() if "profit" in part else None)
                if "sub_category" in levels:
                    for _, row in part.iterrows():
                        ids.append(f"{cat}/{row['sub_category']}"); parents.append(str(cat))
                        labels.append(str(row["sub_category"])); values.append(row["revenue"])
                        margins.append(row["profit"] / row["revenue"] if "profit" in row and row["revenue"] else None)
            trace = dict(ids=ids, parents=parents, labels=labels, values=values, branchvalues="total",
                         texttemplate="<b>%{label}</b><br>%{value:$,.3s}", textfont=dict(size=13),
                         marker=dict(line=dict(width=2, color=t["surface"]), cornerradius=6),
                         pathbar=dict(visible=True, thickness=22), tiling=dict(pad=2))
            if "profit" in has:
                bound = max(0.05, min(0.5, max(abs(m) for m in margins if m is not None)))
                trace["marker"].update(colors=margins, colorscale=charts.diverging_scale(), cmid=0,
                                       cmin=-bound, cmax=bound, showscale=True,
                                       colorbar=dict(title=dict(text="Margin", side="right"), tickformat=".0%",
                                                     thickness=10, len=0.8, outlinewidth=0,
                                                     tickfont=dict(color=t["text_3"])))
                trace["customdata"] = margins
                trace["hovertemplate"] = "<b>%{label}</b><br>Revenue %{value:$,.0f}<br>Margin %{customdata:.1%}<extra></extra>"
            else:
                trace["hovertemplate"] = "<b>%{label}</b><br>Revenue %{value:$,.0f}<extra></extra>"
            trace["root_color"] = t["surface"]
            fig = go.Figure(go.Treemap(**trace))
            charts.style(fig, height=380, hovermode="closest")
            fig.update_layout(margin=dict(l=0, r=0, t=4, b=0))
            charts.show(fig, key="sales-treemap")

with right:
    if "product" in has:
        table = products.pareto(cur, "product")
        abc = products.abc_summary(table).set_index("abc")
        with ui.card("sales-pareto", "Revenue concentration",
                     "Share of revenue made by the top x% of products."):
            fig = go.Figure()
            for cls, x0, x1 in (("A", 0, abc.loc["A", "item_share"]),
                                ("B", abc.loc["A", "item_share"], abc.loc[["A", "B"], "item_share"].sum())):
                fig.add_vrect(x0=x0, x1=x1, fillcolor=t["accent_soft"], opacity=0.9 if cls == "A" else 0.45,
                              line_width=0, layer="below",
                              annotation_text=f"Class {cls}", annotation_position="bottom right",
                              annotation_font=dict(size=11, color=t["text_3"]))
            fig.add_scatter(
                x=[0, *table["rank_share"]], y=[0, *table["cum_share"]], mode="lines",
                line=dict(color=t["accent"], width=2), name="Cumulative revenue",
                hovertemplate="Top %{x:.0%} of products → %{y:.0%} of revenue<extra></extra>",
            )
            charts.style(fig, height=300, y_format=".0%", x_format=".0%", hovermode="closest")
            fig.update_yaxes(range=[0, 1.02])
            fig.update_xaxes(range=[0, 1], showgrid=True, gridcolor=t["grid"])
            charts.show(fig, key="sales-pareto")
            ui.stat_chips([
                ("Top 20% of products", f"{products.top_share(table, 0.2):.0%} of revenue"),
                ("Class A", f"{int(abc.loc['A', 'items']):,} of {len(table):,} products"),
            ])

# ----------------------------------------------------------
# Seasonality + loss-makers
# ----------------------------------------------------------

st.space("small")
left, right = st.columns([7, 5], gap="medium")

with left:
    with ui.card("sales-season", "Seasonality", "Monthly revenue by year, all history. Darker = more revenue."):
        season = products.seasonality(ctx.hist)
        z = season.values
        text = [[charts.money(v) if pd.notna(v) else "" for v in row] for row in z]
        fig = go.Figure(go.Heatmap(
            z=z, x=[str(c) for c in season.columns], y=[calendar.month_abbr[m] for m in season.index],
            text=text, texttemplate="%{text}", textfont=dict(size=11),
            colorscale=charts.sequential_scale(), showscale=False, xgap=2, ygap=2,
            hovertemplate="%{y} %{x}: %{z:$,.0f}<extra></extra>",
        ))
        charts.style(fig, height=380, hovermode="closest")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(side="top", type="category")
        charts.show(fig, key="sales-season")

with right:
    if {"product", "profit"} <= has:
        with ui.card("sales-loss", "Biggest loss-makers", "Products with the most negative profit in this period."):
            losses = products.loss_makers(cur, "product", n=10)
            if losses.empty:
                ui.empty_state("No loss-making products", "Every product made a profit in this period.",
                               icon_name="check")
            else:
                st.dataframe(
                    blocks.as_percent(losses, "margin", "avg_discount"), hide_index=True, width="stretch",
                    height=charts.table_height(len(losses), 10),
                    column_order=[c for c in ("product", "profit", "margin", "avg_discount") if c in losses],
                    column_config={
                        "product": st.column_config.TextColumn("Product", width="medium"),
                        "profit": st.column_config.NumberColumn("Profit", format="dollar", width="small"),
                        "margin": blocks.pct_column("Margin", width="small"),
                        "avg_discount": blocks.pct_column("Discount", width="small"),
                    },
                )
                total_loss = losses["profit"].sum()
                st.caption(f"These {len(losses)} products lost {charts.money(-total_loss)} in total.")

# ----------------------------------------------------------
# Product table
# ----------------------------------------------------------

if "product" in has:
    st.space("small")
    with ui.card("sales-products", "Products", "Every product in the period with its ABC class and 12-month trend."):
        table = products.product_table(cur, ctx.hist)
        f1, f2, f3, f4 = st.columns([2, 1, 1, 0.5], vertical_alignment="bottom")
        search = f1.text_input("Search", placeholder="Search products…", label_visibility="collapsed",
                               icon=":material/search:", key="sales-search")
        cats = sorted(table["category"].dropna().unique()) if "category" in table else []
        cat = f2.selectbox("Category", ["All categories", *cats], label_visibility="collapsed",
                           key="sales-cat") if cats else "All categories"
        cls = f3.selectbox("ABC class", ["All classes", "A", "B", "C"], label_visibility="collapsed",
                           key="sales-abc")
        view = table
        if search:
            view = view[view["product"].astype(str).str.contains(search, case=False, regex=False)]
        if cat != "All categories":
            view = view[view["category"] == cat]
        if cls != "All classes":
            view = view[view["abc"] == cls]
        columns = [c for c in ("product", "category", "sub_category", "abc", "revenue", "units", "profit",
                               "margin", "share", "trend") if c in view]
        with f4:
            blocks.download(view[[c for c in columns if c != "trend"]], "products.csv", key="sales-products-dl")
        st.dataframe(
            blocks.as_percent(view[columns], "margin"), hide_index=True, width="stretch", height=charts.table_height(len(view), 14),
            column_config={
                "product": st.column_config.TextColumn("Product", width="medium"),
                "category": st.column_config.TextColumn("Category"),
                "sub_category": st.column_config.TextColumn("Sub-category"),
                "abc": st.column_config.TextColumn("Class", width="small",
                                                   help="A = first 80% of revenue, B = next 15%, C = the rest"),
                "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
                "units": st.column_config.NumberColumn("Units", format="%d", width="small"),
                "profit": st.column_config.NumberColumn("Profit", format="dollar"),
                "margin": blocks.pct_column("Margin", width="small"),
                "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, width="small",
                                                         max_value=float(view["share"].max() or 1) if len(view) else 1),
                "trend": st.column_config.LineChartColumn("Last 12 months", width="medium"),
            },
        )
        st.caption(f"{len(view):,} of {len(table):,} products")

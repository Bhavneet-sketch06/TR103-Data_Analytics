"""Overview: headline KPIs, the trend, alerts and what changed, and where."""

from __future__ import annotations

import streamlit as st

from core import anomalies, filters, insights, metrics
from core.schema import FIELD_BY_KEY
from ui import blocks, charts, report, shell
from ui import components as ui

def _report_button(page_ctx) -> None:
    """
    Download button for the HTML report. Streamlit builds a deferred download
    in a background thread with no session, so everything the report needs
    (data, filters, window) is captured now; only the work happens on click.
    """
    selections, key = filters.selections(), blocks.selection_key()
    history = filters.apply_dimension_filters(page_ctx.df, selections)
    digest, window_ = page_ctx.dataset.digest, page_ctx.window

    def build() -> str:
        alerts = blocks.cached_anomalies(digest, key, window_.start, window_.end, page_ctx.hist)
        try:
            forecast = blocks.cached_forecast(digest, key, "revenue", "Month", 6, "Auto", history)
        except ValueError:                 # not enough history to forecast: the report leaves it out
            forecast = None
        return report.build(page_ctx, selections, forecast=forecast, alerts=alerts)

    st.download_button(
        "Download report", data=build, file_name=report.file_name(page_ctx.dataset.name), mime="text/html",
        icon=":material/download:", key="ov-report", on_click="ignore",
        help="A one-page HTML report of this view: KPIs, trend, alerts, breakdowns and a 6-month forecast. "
             "Open it in any browser; use Print to save it as a PDF.",
    )


ctx = shell.page("Overview", "How the business is doing in the selected period.", actions=_report_button)
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
ui.verdict_banner(insights.overview_verdict(cur, prev, period))

st.space("small")
preferred = ["revenue", "profit", "margin", "orders", "aov", "customers", "units"]
available = [k for k in preferred if k in metrics.kpis(cur)]
blocks.kpi_row(ctx, available[:5])

# ----------------------------------------------------------
# Trend + highlights
# ----------------------------------------------------------

found = blocks.cached_anomalies(ctx.dataset.digest, blocks.selection_key(), window.start, window.end, ctx.hist)

st.space("small")
left, right = st.columns([2, 1], gap="medium")
with left:
    blocks.trend_card(ctx, "ov-trend", "Performance over time", alerts=found[found["scope"] == "Total"])
with right:
    subtitle = "Unusual months in this period" + (f", then the biggest moves {period}" if prev is not None else "")
    with ui.card("ov-highlights", "Alerts and changes", subtitle,
                 help="Green = good news, red = a problem, amber = worth watching. A month is flagged as "
                      "unusual when it's far from what the months before it suggested."):
        alerts = anomalies.as_items(found, limit=3)
        if not alerts:
            alerts = [{"tone": "info", "title": "No unusual months",
                       "body": "Every month in this period was within the normal range for its slice."}]
        moves = insights.highlights(cur, prev, period, limit=6 - len(alerts))
        ui.item_list(alerts + moves)
        if prev is None:
            st.caption("Choose “Same period last year” or “Previous period” to also see what changed.")

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
            with ui.card(f"ov-{dim}", f"Revenue by {label.lower()}", "Click a bar to filter every page.",
                         insight=insights.breakdown_summary(table),
                         help="Each bar is total sales. The % after it is the profit margin: how much of "
                              "each sale is profit. A negative margin means it loses money."):
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
    with ui.card("ov-movers", "Top movers", subtitle,
                 help="What grew or shrank the most compared with the comparison period. A positive change "
                      "means more sales than before; a negative one means fewer."):
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

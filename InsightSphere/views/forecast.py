"""Forecast: where the business is heading (Forecast), what would change it (What-if), and saved runs."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import db, filters, forecasting, insights, simulator
from core.schema import FIELD_BY_KEY
from ui import blocks, charts, shell
from ui import components as ui

ctx = shell.page("Forecast", "Where the business is heading, and what would change it.", date_controls=False)
if ctx is None:
    st.stop()

# Forecasts learn from all history (dimension filters still apply), not just the selected date range.
history = filters.apply_dimension_filters(ctx.df, filters.selections())
if history.empty:
    ui.empty_state("No orders match these filters", "Clear some filters to forecast.")
    st.stop()

t = charts.tokens_for(charts.current_mode())
selection_key = blocks.selection_key()
GRAIN_UNIT = {"Month": "month", "Week": "week"}


def _rounded(value: float, kind: str) -> str:
    """Whole thousands / one-decimal millions, so a range fits in a tile: $231K – $463K."""
    prefix = "$" if kind == "money" else ""
    if abs(value) >= 1e6:
        return f"{prefix}{value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"{prefix}{value / 1e3:.0f}K"
    return f"{prefix}{value:,.0f}"


forecast_tab, whatif_tab, runs_tab = st.tabs(
    [":material/insights: Forecast", ":material/tune: What-if", ":material/history: Saved runs"])

# ==========================================================
# FORECAST
# ==========================================================

with forecast_tab:
    st.space("xsmall")
    metric_options = [m for m in forecasting.METRICS
                      if m in ("revenue", "orders") or (m == "profit" and "profit" in history)
                      or (m == "units" and "quantity" in history)]
    c1, c2, c3, c4 = st.columns([2.2, 1.2, 2, 1.6], vertical_alignment="bottom", gap="medium")
    metric = c1.segmented_control("Metric", metric_options, default="revenue", key="fc-metric",
                                  format_func=forecasting.METRICS.get) or "revenue"
    grain = c2.segmented_control("Grain", list(forecasting.SEASON), default="Month", key="fc-grain") or "Month"
    max_h = 12 if grain == "Month" else 26
    horizon = c3.slider(f"Horizon ({GRAIN_UNIT[grain]}s ahead)", 3 if grain == "Month" else 4, max_h,
                        6 if grain == "Month" else 8, key=f"fc-h-{grain}")
    model = c4.selectbox("Method", ["Auto", *forecasting.models_for(grain)], key=f"fc-model-{grain}",
                         help="Auto uses the method that predicted your past data best.")

    try:
        with st.spinner("Fitting and back-testing models…"):
            result = blocks.cached_forecast(ctx.dataset.digest, selection_key, metric, grain, horizon, model, history)
    except ValueError as exc:
        ui.empty_state("Not enough history to forecast", str(exc), icon_name="chart")
        st.stop()

    f = result.forecast
    y = result.series
    table = result.comparison.set_index("model")
    chosen = table.loc[result.chosen]
    naive = table.loc[forecasting.NAIVE]
    kind = "count" if metric in ("orders", "units") else "money"
    unit = GRAIN_UNIT[grain]

    # Same periods one year earlier, for context.
    year_ago = f.index - (pd.DateOffset(years=1) if grain == "Month" else pd.Timedelta(weeks=52))
    last_year = y.reindex(year_ago)
    change = (f.mean.sum() - last_year.sum()) / last_year.sum() if last_year.notna().all() and last_year.sum() else None
    improvement = 1 - chosen["mase"] / naive["mase"] if pd.notna(chosen["mase"]) and naive["mase"] else None

    st.space("small")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        ui.kpi_tile(f"Next {horizon} {unit}s", blocks.fmt(f.mean.sum(), kind), change=change,
                    period="vs same period last year" if change is not None else f"{forecasting.METRICS[metric]} forecast")
    with k2:
        ui.kpi_tile("Likely range (80%)", f"{_rounded(f.lo80.sum(), kind)} – {_rounded(f.hi80.sum(), kind)}",
                    period="sum of the monthly 80% ranges" if grain == "Month" else "sum of the weekly 80% ranges",
                    help_text="Adding up each period's range overstates the total's uncertainty a little.")
    with k3:
        ui.kpi_tile("Method", result.chosen,
                    period="the most accurate on past data" if model == "Auto" else "chosen manually",
                    help_text="Three methods are tried on past data; the one that predicted it best is used.")
    with k4:
        if chosen["mape"] is not None and pd.notna(chosen["mape"]):
            accuracy, foot = f"{chosen['mape']:.1%}", "average error in back-tests"
        else:
            accuracy, foot = f"{chosen['mase']:.2f}", "error vs the simple baseline (lower is better)"
        if result.chosen != forecasting.NAIVE and improvement is not None:
            foot = (f"{improvement:.0%} more accurate than a simple guess" if improvement > 0
                    else "no better than a simple guess")
        ui.kpi_tile("Typical error", accuracy, period=foot,
                    help_text="How far off the method was, on average, when it predicted past months it hadn't "
                              "seen. The simple guess repeats last year's numbers.")

    st.space("small")
    ui.takeaways("fc-takeaways", insights.forecast_takeaways(result))

    # ---------- chart ----------
    st.space("small")
    shown = y.iloc[-(36 if grain == "Month" else 104):]
    accent = t["accent"]
    with ui.card("fc-chart", f"{forecasting.METRICS[metric]} forecast",
                 f"Solid: actual. Dashed: {result.chosen} forecast. Bands: 80% and 95% ranges.",
                 help="The dashed line is the most likely path. The darker band is where the real number will "
                      "probably land (8 times in 10); the lighter band is almost certain (19 times in 20)."):
        fig = go.Figure()
        band_x = [shown.index[-1], *f.index]
        for lo, hi, alpha, name in ((f.lo95, f.hi95, 0.10, "95% range"), (f.lo80, f.hi80, 0.20, "80% range")):
            fig.add_scatter(x=band_x + band_x[::-1],
                            y=[shown.iloc[-1], *hi] + [*lo[::-1], shown.iloc[-1]],
                            fill="toself", fillcolor=charts.rgba(accent, alpha), line=dict(width=0),
                            mode="lines", name=name, hoverinfo="skip")
        fig.add_scatter(x=shown.index, y=shown.values, name="Actual", mode="lines",
                        line=dict(color=t["text_2"], width=2), hovertemplate=blocks.HOVER[blocks.METRIC_FMT.get(metric, "count")])
        fig.add_scatter(x=band_x, y=[shown.iloc[-1], *f.mean], name="Forecast", mode="lines+markers",
                        line=dict(color=accent, width=2.5, dash="dash"), marker=dict(size=6),
                        hovertemplate=blocks.HOVER[blocks.METRIC_FMT.get(metric, "count")])
        fig.add_vline(x=shown.index[-1], line=dict(color=t["border_strong"], width=1, dash="dot"))
        charts.style(fig, height=380, legend=True, y_format=blocks.AXIS_FMT["money" if kind == "money" else "count"],
                     x_format="%b %Y" if grain == "Month" else "%b %d, %Y")
        fig.update_traces(selector=dict(fill="toself"), line_width=0)   # style() gives lines 2px; bands have none
        if metric in forecasting.NON_NEGATIVE:
            fig.update_yaxes(rangemode="tozero")
        charts.show(fig, key=f"fc-chart-{metric}-{grain}")
        for note in result.notes:
            st.caption(note)

    # ---------- back-test + table ----------
    st.space("small")
    left, right = st.columns([5, 7], gap="medium")
    with left:
        with ui.card("fc-backtest", "How accurate each method was",
                     f"Each method predicted {horizon} {unit}s ahead from several points in the past, using only "
                     f"the data before each point; we then compared with what really happened.",
                     help="Avg error: how far off the predictions were, on average. Error vs baseline: below 1 "
                          "means better than simply repeating last year's numbers."):
            scores = result.comparison.copy()
            scores["mape"] = scores["mape"].astype(float) * 100
            scores["pick"] = scores["chosen"].map({True: "Chosen", False: ""})
            st.dataframe(
                scores[["model", "mape", "mase", "pick"]], hide_index=True, width="stretch",
                height=charts.table_height(len(scores)),
                column_config={
                    "model": st.column_config.TextColumn("Method"),
                    "mape": blocks.pct_column("Avg error", help="How far off the predictions were, on average."),
                    "mase": st.column_config.NumberColumn(
                        "Error vs baseline", format="%.2f",
                        help="Below 1 = better than repeating last year's numbers. Lower is better."),
                    "pick": st.column_config.TextColumn("", width="small"),
                },
            )
            st.caption("Auto uses the method with the lowest error vs baseline. Seasonal naive simply repeats "
                       "last year's numbers, so it's the baseline to beat.")
    with right:
        with ui.card("fc-table", "Forecast values", f"Per {unit}, with 80% and 95% ranges."):
            out = f.frame().reset_index(names="period")
            st.dataframe(
                out, hide_index=True, width="stretch", height=charts.table_height(len(out), 8),
                column_config={
                    "period": st.column_config.DateColumn(unit.title(), format="MMM YYYY" if grain == "Month"
                                                          else "MMM D, YYYY"),
                    **{c: st.column_config.NumberColumn(label, format="dollar" if kind == "money" else "%d")
                       for c, label in (("forecast", "Forecast"), ("lo80", "80% low"), ("hi80", "80% high"),
                                        ("lo95", "95% low"), ("hi95", "95% high"))},
                },
            )
            a, b = st.columns([1, 1])
            with a:
                blocks.download(out, f"forecast_{metric}_{grain.lower()}.csv", key="fc-dl", label="Download CSV")
            with b:
                if st.button("Save run", icon=":material/bookmark_add:", width="stretch", key="fc-save"):
                    db.save_run(
                        dataset_name=ctx.dataset.name, dataset_digest=ctx.dataset.digest, metric=metric,
                        grain=grain, horizon=horizon, model=result.chosen,
                        mape=float(chosen["mape"]) if chosen["mape"] is not None and pd.notna(chosen["mape"]) else None,
                        params={"filters": filters.selections(), "requested_model": model,
                                "mase": float(chosen["mase"]) if pd.notna(chosen["mase"]) else None},
                        results={"index": [d.isoformat() for d in f.index],
                                 **{c: getattr(f, c).tolist() for c in ("mean", "lo80", "hi80", "lo95", "hi95")},
                                 "history_index": [d.isoformat() for d in shown.index],
                                 "history": shown.tolist()},
                    )
                    st.toast("Run saved. Find it under Saved runs.", icon=":material/check_circle:")

# ==========================================================
# WHAT-IF
# ==========================================================

with whatif_tab:
    st.space("xsmall")
    needed = [FIELD_BY_KEY[k].label for k in ("discount", "profit") if k not in history]
    if needed:
        ui.locked_state("The what-if simulator", needed)
    else:
        group = "category" if "category" in history else None
        recent = history[history["order_date"] > history["order_date"].max() - pd.DateOffset(months=12)]
        response = simulator.discount_response(recent, group or "category")
        base_h = horizon if grain == "Month" else 6
        try:
            baseline_run = blocks.cached_forecast(ctx.dataset.digest, selection_key, "revenue", "Month", base_h, "Auto", history)
            baseline_revenue = float(baseline_run.forecast.mean.sum())
            baseline_label = f"forecast revenue, next {base_h} months"
        except ValueError:
            baseline_revenue = float(recent["revenue"].sum())
            baseline_label = "revenue, last 12 months"

        def _reset_levers():
            for key in ("wi-discount", "wi-price", "wi-volume"):
                st.session_state[key] = 0

        left, right = st.columns([4, 8], gap="medium")
        with left:
            with ui.card("wi-levers", "Levers", f"Applied to the baseline: {baseline_label}."):
                d = st.slider("Average discount change (points)", -10, 10, 0, key="wi-discount",
                              help="+5 means every discount is 5 points deeper (e.g. 15% → 20%).")
                p = st.slider("Price change (%)", -10, 10, 0, key="wi-price",
                              help="List prices before discount. Costs stay the same.")
                v = st.slider("Volume change (%)", -20, 20, 0, key="wi-volume",
                              help="Units sold. Costs move with volume.")
                st.button("Reset levers", icon=":material/restart_alt:", on_click=_reset_levers, width="stretch",
                          key="wi-reset")
                st.caption("The discount effect comes from how margin moved with discount across your order "
                           "lines in the last 12 months. That's an observed pattern, not proof of cause, and "
                           "it assumes volume stays the same; use the volume lever for that.")
        result_sim = simulator.simulate(baseline_revenue, response, simulator.Levers(d / 100, p / 100, v / 100))
        with right:
            r1, r2, r3 = st.columns(3)
            base_rev, base_profit = result_sim["baseline_revenue"], result_sim["baseline_profit"]
            with r1:
                ui.kpi_tile("Revenue", charts.money(result_sim["revenue"]),
                            change=(result_sim["revenue"] - base_rev) / base_rev if base_rev else None,
                            period=f"baseline {charts.money(base_rev)}")
            with r2:
                ui.kpi_tile("Profit", charts.money(result_sim["profit"]),
                            change=(result_sim["profit"] - base_profit) / abs(base_profit) if base_profit else None,
                            period=(f"likely {charts.money(result_sim['profit_low'])} – "
                                    f"{charts.money(result_sim['profit_high'])}"
                                    if result_sim["profit_high"] - result_sim["profit_low"] > 1
                                    else f"baseline {charts.money(base_profit)}"))
            with r3:
                ui.kpi_tile("Profit margin", charts.pct(result_sim["margin"]),
                            change=(result_sim["margin"] - result_sim["baseline_margin"])
                            if result_sim["margin"] is not None else None, kind="pp",
                            period=f"baseline {charts.pct(result_sim['baseline_margin'])}")
            st.space("small")
            change = result_sim["profit"] - base_profit
            if abs(change) < 0.5:
                sentence = "Move the sliders to see how profit would change."
            else:
                sentence = (f"With these changes, profit would be {charts.money(result_sim['profit'])} instead of "
                            f"{charts.money(base_profit)}: {'more' if change > 0 else 'less'} by "
                            f"{charts.money(abs(change))}.")
            with ui.card("wi-waterfall", "Where the profit change comes from",
                         "Baseline profit, each lever's effect, and the scenario.", insight=sentence,
                         help="Start from today's expected profit (left), add or subtract the effect of each "
                              "slider, and you get the new profit (right). Blue raises profit, orange lowers it."):
                steps = result_sim["steps"]
                diverging = charts.diverging_scale()
                neg, pos = diverging[1][1], diverging[-2][1]
                fig = go.Figure(go.Waterfall(
                    x=[s for s, _ in steps] + ["Scenario"],
                    y=[v for _, v in steps] + [0],
                    measure=["absolute", "relative", "relative", "relative", "total"],
                    text=[charts.money(v) if i == 0 else ("—" if abs(v) < 0.5 else
                                                           ("+" if v > 0 else "") + charts.money(v))
                          for i, (_, v) in enumerate(steps)] + [charts.money(result_sim["profit"])],
                    textposition="outside", cliponaxis=False, textfont=dict(color=t["text_2"]),
                    connector=dict(line=dict(color=t["border_strong"], width=1, dash="dot")),
                    increasing=dict(marker=dict(color=pos)), decreasing=dict(marker=dict(color=neg)),
                    totals=dict(marker=dict(color=t["text_3"])),
                    hovertemplate="%{x}: %{y:$,.0f}<extra></extra>",
                ))
                charts.style(fig, height=300, y_format="$~s", hovermode="closest")
                top = max(base_profit, result_sim["profit"], result_sim["profit_high"])
                fig.update_yaxes(range=[min(0, result_sim["profit"]) * 1.2, top * 1.25])
                fig.update_layout(waterfallgap=0.35)
                charts.show(fig, key="wi-waterfall")
            if group:
                with ui.card("wi-table", "By category", "Baseline vs scenario, and how margin moved with "
                                                        "discount in your data."):
                    table = result_sim["table"].merge(response[[group, "slope", "discount"]],
                                                      left_on="group", right_on=group)
                    table["slope_pp"] = table["slope"]       # margin points per discount point
                    table["base_margin"] = table["baseline_profit"] / table["baseline_revenue"]
                    show = blocks.as_percent(table, "margin", "base_margin", "discount")
                    st.dataframe(
                        show[["group", "base_margin", "baseline_profit", "profit", "margin", "slope_pp"]],
                        hide_index=True, width="stretch", height=charts.table_height(len(show)),
                        column_config={
                            "group": st.column_config.TextColumn("Category"),
                            "base_margin": blocks.pct_column("Margin now", width="small"),
                            "baseline_profit": st.column_config.NumberColumn("Baseline profit", format="dollar"),
                            "profit": st.column_config.NumberColumn("Scenario profit", format="dollar"),
                            "margin": blocks.pct_column("New margin", width="small"),
                            "slope_pp": st.column_config.NumberColumn(
                                "Per +1pt discount", format="%.2f pt", width="small",
                                help="Observed change in margin (points) for each extra point of discount, "
                                     "across your order lines in the last 12 months."),
                        },
                    )

# ==========================================================
# SAVED RUNS
# ==========================================================

with runs_tab:
    st.space("xsmall")
    runs = db.list_runs()
    if runs.empty:
        ui.empty_state("No saved runs yet", "Run a forecast and press “Save run” to keep it here for later.",
                       icon_name="chart")
    else:
        runs = runs.assign(created_at=pd.to_datetime(runs["created_at"]), mape=runs["mape"] * 100)
        with ui.card("runs-table", "Saved runs", "Newest first. Select runs to compare them or delete them."):
            event = st.dataframe(
                runs, hide_index=True, width="stretch", height=charts.table_height(len(runs), 10),
                key="runs-select", on_select="rerun", selection_mode="multi-row",
                column_order=["created_at", "dataset_name", "metric", "grain", "horizon", "model", "mape"],
                column_config={
                    "created_at": st.column_config.DatetimeColumn("Saved", format="MMM D, YYYY h:mm a"),
                    "dataset_name": st.column_config.TextColumn("Dataset"),
                    "metric": st.column_config.TextColumn("Metric"),
                    "grain": st.column_config.TextColumn("Grain", width="small"),
                    "horizon": st.column_config.NumberColumn("Horizon", width="small"),
                    "model": st.column_config.TextColumn("Model"),
                    "mape": blocks.pct_column("Back-test error", width="small"),
                },
            )
            picked = runs.iloc[event.selection.rows]["id"].tolist() if event and event.selection.rows else []

            @st.dialog("Delete saved runs")
            def _confirm_delete(ids):
                st.write(f"Delete {len(ids)} saved run{'s' if len(ids) != 1 else ''}? This can't be undone.")
                a, b = st.columns(2)
                if a.button("Cancel", width="stretch"):
                    st.rerun()
                if b.button("Delete", type="primary", width="stretch"):
                    db.delete_runs(ids)
                    st.session_state.pop("runs-select", None)
                    st.rerun()

            with st.container(horizontal=True, horizontal_alignment="right"):
                if st.button("Delete selected", icon=":material/delete:", disabled=not picked, key="runs-delete"):
                    _confirm_delete(picked)
            if not picked:
                st.caption("Tip: select one or more rows to see them on a chart.")

        if picked:
            st.space("small")
            with ui.card("runs-compare", "Compare runs", "Each run's forecast, with the history it was made from."):
                fig = go.Figure()
                first = db.get_run(picked[0])["results"]
                fig.add_scatter(x=pd.to_datetime(first["history_index"]), y=first["history"], name="Actual",
                                mode="lines", line=dict(color=t["text_2"], width=2))
                colors = charts.series_colors()
                for i, run_id in enumerate(picked[:8]):
                    run = db.get_run(run_id)
                    res = run["results"]
                    label = f"#{run_id} · {run['model']} · {pd.Timestamp(run['created_at']):%b %d %H:%M}"
                    fig.add_scatter(x=pd.to_datetime(res["index"]), y=res["mean"], name=label,
                                    mode="lines+markers", line=dict(color=colors[i % len(colors)], width=2, dash="dash"),
                                    marker=dict(size=5))
                charts.style(fig, height=340, legend=True, y_format="~s", x_format="%b %Y")
                charts.show(fig, key="runs-compare")
                if len({db.get_run(i)["metric"] for i in picked}) > 1:
                    st.caption("These runs forecast different metrics, so their scales differ.")

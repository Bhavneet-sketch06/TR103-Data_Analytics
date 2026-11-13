"""Plain-language insights: the verdict logic and each page's takeaways."""

import pandas as pd
import pytest

from core import filters, forecasting, ingest, insights
from core.analytics import customers


@pytest.fixture(scope="module")
def sample():
    df = ingest.load_sample().df
    w = filters.compute_window("Last 12 months", "Same period last year", df["order_date"].min(), df["order_date"].max())
    return df, w, filters.slice_window(df, w.start, w.end), filters.slice_window(df, w.prev_start, w.prev_end)


def frame(revenue, profit=None, start="2024-01-01"):
    data = {"order_date": pd.date_range(start, periods=len(revenue), freq="D"), "revenue": revenue,
            "order_id": range(len(revenue))}
    if profit is not None:
        data["profit"] = profit
    return pd.DataFrame(data)


# ----------------------------------------------------------
# Verdict
# ----------------------------------------------------------

def test_verdict_growing_and_profitable(sample):
    _, _, cur, prev = sample
    v = insights.overview_verdict(cur, prev, "vs last year")
    assert v["tone"] == "good" and v["headline"] == "Growing and profitable"
    assert "$733.2K" in v["body"] and "$93.4K" in v["body"] and "up 20.5%" in v["body"]


@pytest.mark.parametrize("cur_profit, prev_profit, cur_rev, headline, tone", [
    ([-50, -50], [10, 10], [100, 100], "Losing money", "bad"),
    ([-50, -50], [10, 10], [300, 300], "Losing money, even though sales are up", "bad"),
    ([5, 5], [40, 40], [300, 300], "Sales are up, but profit is down", "warn"),
    ([20, 20], [20, 20], [50, 50], "Still profitable, but sales are falling", "warn"),
    ([20, 20], [20, 20], [100, 100], "Profitable", "good"),
])
def test_verdict_cases(cur_profit, prev_profit, cur_rev, headline, tone):
    cur = frame(cur_rev, cur_profit, "2024-02-01")
    prev = frame([100, 100], prev_profit, "2023-02-01")
    v = insights.overview_verdict(cur, prev, "vs last year")
    assert (v["headline"], v["tone"]) == (headline, tone)


def test_verdict_without_profit_talks_about_sales_only():
    v = insights.overview_verdict(frame([300, 300]), frame([100, 100], start="2023-01-01"), "vs last year")
    assert v["headline"] == "Sales are growing" and "profit or cost column" in v["body"]


# ----------------------------------------------------------
# Page takeaways say what the data shows
# ----------------------------------------------------------

def test_sales_takeaways(sample):
    df, w, cur, _ = sample
    items = insights.sales_takeaways(cur, df[df["order_date"] <= w.end])
    titles = " | ".join(i["title"] for i in items)
    assert "Technology brings in the most money" in titles
    assert "products lost money" in titles
    assert "Sales peak in November" in titles


def test_region_takeaways(sample):
    _, _, cur, prev = sample
    titles = [i["title"] for i in insights.region_takeaways(cur, prev, "vs last year")]
    assert titles[0] == "West is the biggest region"
    assert "Central keeps the least profit" in titles
    assert "9 states lose money" in titles
    assert not any("Central sales fell" in t for t in titles)     # a 0.2% dip isn't news


def test_operations_takeaways(sample):
    _, _, cur, _ = sample
    items = insights.operations_takeaways(cur)
    assert items[0]["tone"] == "bad" and "21–30%" in items[0]["title"]
    assert any("ship in 3.9 days" in i["title"] for i in items)


def test_customer_takeaways(sample):
    df, w, cur, prev = sample
    hist = df[df["order_date"] <= w.end]
    now = customers.summary(cur, hist, w.start)
    before = customers.summary(prev, hist[hist["order_date"] <= w.prev_end], w.prev_start)
    segments = customers.segment_summary(customers.rfm(hist, as_of=w.end))
    items = insights.customer_takeaways(now, before, segments, 0.12)
    assert items[0]["title"] == "693 customers bought in this period"
    assert any(i["title"] == "Customers come back" for i in items)
    assert any("gone quiet" in i["title"] for i in items)


def test_forecast_takeaways(sample):
    df = sample[0]
    items = insights.forecast_takeaways(forecasting.run(df, "revenue", "Month", 6))
    assert items[0]["title"].startswith("Expect about $347.1K of sales in the next 6 months")
    assert any("Past forecasts were off by about 23%" in i["title"] for i in items)


def test_breakdown_and_trend_lines(sample):
    from core import metrics
    _, w, cur, prev = sample
    assert insights.breakdown_summary(metrics.breakdown(cur, "category")) == (
        "Technology sells the most (37% of sales). Furniture keeps the least profit (1.4% margin).")
    current = metrics.series(cur, "revenue")
    line = insights.trend_summary(current, metrics.comparison_series(prev, current, w))
    assert line.startswith("Best month: November 2017") and "of 12 months" in line

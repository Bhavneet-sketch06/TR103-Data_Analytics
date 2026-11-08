"""Phase 2 tests: customer and product analytics, shipping and geography helpers."""

import pandas as pd
import pytest

from core import filters, ingest, metrics
from core.analytics import customers, operations, products


@pytest.fixture(scope="module")
def sample():
    return ingest.load_sample().df


# ----------------------------------------------------------
# Customers
# ----------------------------------------------------------

def test_rfm_has_one_row_per_customer_and_valid_scores(sample):
    table = customers.rfm(sample)
    assert len(table) == sample["customer_id"].nunique()
    for col in ("r", "f", "m"):
        assert table[col].between(1, 5).all()
    assert set(table["segment"]) <= set(customers.SEGMENTS)
    assert (table["recency"] >= 0).all()


def test_rfm_segment_rules():
    assert customers._segment(5, 5) == "Champions"
    assert customers._segment(3, 4) == "Loyal"
    assert customers._segment(5, 1) == "New"
    assert customers._segment(1, 5) == "Can't lose"
    assert customers._segment(2, 3) == "At risk"
    assert customers._segment(1, 1) == "Hibernating"
    assert customers._segment(3, 2) == "Need attention"


def test_segment_summary_shares_sum_to_one(sample):
    summary = customers.segment_summary(customers.rfm(sample))
    assert summary["customer_share"].sum() == pytest.approx(1.0)
    assert summary["revenue"].sum() == pytest.approx(sample["revenue"].sum())


def test_cohort_month_zero_is_full_and_future_cells_are_empty(sample):
    matrix = customers.cohorts(sample, "M", n_cohorts=12, max_age=12, min_size=1)
    assert len(matrix) == 12
    assert (matrix[0] == 1.0).all()
    # The newest cohort can't have been observed 12 months later.
    assert pd.isna(matrix.iloc[-1][12])
    ages = [c for c in matrix.columns if c != "size"]
    assert matrix[ages].stack().dropna().between(0, 1).all()


def test_small_cohorts_switch_to_quarters_and_are_hidden(sample):
    # Superstore acquires almost every customer in 2014-15, so recent monthly cohorts are tiny.
    assert customers.cohort_grain(sample) == "Q"
    matrix = customers.cohorts(sample, "Q", min_size=10)
    assert (matrix["size"] >= 10).all()
    assert (matrix[0] == 1.0).all()


def test_new_vs_returning_reconciles_with_window_revenue(sample):
    start, end = pd.Timestamp("2017-01-01"), sample["order_date"].max()
    table = customers.new_vs_returning(sample, start, end, "Month")
    window = sample[(sample["order_date"] >= start) & (sample["order_date"] <= end)]
    assert table["revenue"].sum() == pytest.approx(window["revenue"].sum())
    assert set(table["kind"]) <= {"New", "Returning"}


def test_customer_summary_new_plus_returning(sample):
    start = pd.Timestamp("2017-01-01")
    cur = sample[sample["order_date"] >= start]
    s = customers.summary(cur, sample, start)
    assert s["new"] + s["returning"] == s["customers"]
    assert 0 <= s["repeat_rate"] <= 1


# ----------------------------------------------------------
# Products
# ----------------------------------------------------------

def test_pareto_shares_and_abc(sample):
    table = products.pareto(sample, "product")
    assert table["share"].sum() == pytest.approx(1.0)
    assert table["cum_share"].iloc[-1] == pytest.approx(1.0)
    assert table["revenue"].is_monotonic_decreasing
    assert list(dict.fromkeys(table["abc"])) == ["A", "B", "C"]   # classes appear in order
    summary = products.abc_summary(table)
    assert summary["revenue_share"].sum() == pytest.approx(1.0)
    a_share = summary.set_index("abc").loc["A", "revenue_share"]
    assert 0.80 <= a_share < 0.80 + table["share"].max() + 1e-9


def test_top_share_is_monotonic(sample):
    table = products.pareto(sample, "product")
    assert products.top_share(table, 0.1) < products.top_share(table, 0.2) <= 1


def test_discount_bands_cover_every_line(sample):
    bands = products.discount_bands(sample)
    assert bands["lines"].sum() == sample["discount"].notna().sum()
    assert bands["revenue_share"].sum() == pytest.approx(1.0)
    assert bands["loss_share"].between(0, 1).all()


def test_discount_band_edges():
    s = pd.Series([0.0, 0.05, 0.10, 0.2, 0.25, 0.5, 0.8])
    assert list(products.discount_band(s)) == [
        "No discount", "1–10%", "1–10%", "11–20%", "21–30%", "31–50%", "Over 50%"]


def test_loss_makers_are_negative_and_sorted(sample):
    table = products.loss_makers(sample, "product", n=10)
    assert (table["profit"] < 0).all()
    assert table["profit"].is_monotonic_increasing


def test_seasonality_totals(sample):
    table = products.seasonality(sample)
    assert table.shape == (12, 4)
    assert table.sum().sum() == pytest.approx(sample["revenue"].sum())


# ----------------------------------------------------------
# Operations + geography
# ----------------------------------------------------------

def test_shipping_summary(sample):
    table = operations.shipping_summary(sample)
    assert table["order_share"].sum() == pytest.approx(1.0)
    assert table["avg_days"].is_monotonic_increasing


def test_us_state_detection():
    assert operations.looks_like_us_states(["California", "texas", "NY", "Ohio"])
    assert not operations.looks_like_us_states(["North", "South", "East", "West"])
    assert operations.state_code("district of columbia") == "DC"


# ----------------------------------------------------------
# Comparison series alignment
# ----------------------------------------------------------

def test_comparison_series_is_aligned_to_current_months(sample):
    w = filters.compute_window("Last 12 months", "Same period last year",
                               sample["order_date"].min(), sample["order_date"].max())
    cur = filters.slice_window(sample, w.start, w.end)
    prev = filters.slice_window(sample, w.prev_start, w.prev_end)
    current = metrics.series(cur, "revenue", "Month")
    compared = metrics.comparison_series(prev, current, w, "revenue", "Month")
    assert list(compared.index) == list(current.index)
    assert compared.sum() == pytest.approx(prev["revenue"].sum())

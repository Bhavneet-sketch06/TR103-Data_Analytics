"""Phase 1 tests: schema mapping, ingest pipeline, date windows, KPIs, storage."""

from pathlib import Path

import pandas as pd
import pytest

from core import db, filters, ingest, metrics
from core.cleaning import clean_dataset
from core.schema import suggest_mapping, validate_mapping

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    data = (FIXTURES / name).read_bytes()
    cleaned, _ = ingest.read_and_clean(data, name)
    mapping = suggest_mapping(cleaned.columns)
    return ingest.load_dataset(data, name, mapping, is_sample=False), cleaned, mapping


# ----------------------------------------------------------
# Mapping
# ----------------------------------------------------------

def test_superstore_mapping_is_complete():
    _, cleaned, mapping = load("superstore_slice.csv")
    assert mapping["order_date"] == "Order Date"
    assert mapping["revenue"] == "Sales"
    assert mapping["product"] == "Product Name"
    assert mapping["sub_category"] == "Sub-Category"
    assert mapping["cost"] is None
    assert validate_mapping(mapping, cleaned) == []


def test_renamed_schema_is_recognised():
    _, _, mapping = load("renamed_schema.csv")
    assert mapping["order_date"] == "Invoice Date"
    assert mapping["revenue"] == "Net Sales"
    assert mapping["order_id"] == "Invoice No"
    assert mapping["customer_id"] == "Client ID"
    assert mapping["product"] == "Item"
    assert mapping["category"] == "Department"
    assert mapping["region"] == "Territory"
    assert mapping["quantity"] == "Qty"
    assert mapping["profit"] == "Gross Profit"
    assert mapping["ship_date"] == "Delivery Date"


def test_a_column_is_never_mapped_twice():
    mapping = suggest_mapping(["Date", "Total", "Sales"])
    used = [v for v in mapping.values() if v]
    assert len(used) == len(set(used))


def test_validation_flags_missing_required_and_bad_types():
    df = pd.DataFrame({"when": ["x", "y"], "amount": ["a", "b"]})
    problems = validate_mapping({"order_date": "when", "revenue": "amount"}, df)
    assert any("date" in p for p in problems)
    assert any("numeric" in p for p in problems)
    assert any("required" in p for p in validate_mapping({}, df))


# ----------------------------------------------------------
# Ingest
# ----------------------------------------------------------

def test_renamed_schema_values_are_typed_and_normalised():
    ds, _, _ = load("renamed_schema.csv")
    df = ds.df
    assert pd.api.types.is_datetime64_any_dtype(df["order_date"])
    assert pd.api.types.is_float_dtype(df["revenue"])          # "$1,234.50" parsed
    assert df["discount"].max() <= 1                             # 20 -> 0.20
    assert (df["ship_days"].dropna() >= 0).all()


def test_sample_dates_parse_to_real_years():
    """Regression: the old Year filter showed '1/1/', '11/8' ... on the sample."""
    ds = ingest.load_sample()
    years = sorted(ds.df["order_date"].dt.year.unique())
    assert years == [2014, 2015, 2016, 2017]


def test_minimal_file_works_and_derives_order_ids():
    ds, _, mapping = load("minimal.csv")
    assert mapping["order_date"] == "date" and mapping["revenue"] == "amount"
    assert ds.report["synthetic_order_id"] is True
    assert ds.df["order_id"].nunique() == len(ds.df)


def test_profit_is_derived_from_cost():
    df = pd.DataFrame({"order_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                       "revenue": [100.0, 50.0], "cost": [60.0, 70.0]})
    out, notes = ingest.derive(df)
    assert out["profit"].tolist() == [40.0, -20.0]
    assert "Profit = revenue − cost" in notes["derived"]


def test_rows_without_date_or_revenue_are_dropped_and_counted():
    df = pd.DataFrame({"order_date": ["2024-01-01", None, "2024-01-03"],
                       "revenue": [10.0, 20.0, None]})
    out, notes = ingest.derive(df)
    assert len(out) == 1
    assert notes["rows_dropped_no_date"] == 1 and notes["rows_dropped_no_revenue"] == 1


def test_cleaning_never_invents_numbers():
    raw = pd.DataFrame({
        "Sales": [10.0, None, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
        "Region": ["West", "East", "west", "West", None, "East", "West", "East"],
    })
    cleaned, report = clean_dataset(raw)
    assert cleaned["Sales"].isna().sum() == 1                 # left missing, not median-filled
    assert set(cleaned["Region"]) == {"West", "East", "Unknown"}  # case-normalised + bucketed
    assert report["final_missing_values"] == 1


def test_duplicates_are_removed_and_counted():
    raw = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    cleaned, report = clean_dataset(raw)
    assert len(cleaned) == 2 and report["duplicates_removed"] == 1


# ----------------------------------------------------------
# Windows
# ----------------------------------------------------------

LO, HI = pd.Timestamp("2014-01-03"), pd.Timestamp("2017-12-30")


def test_last_12_months_is_month_aligned_and_compares_to_last_year():
    w = filters.compute_window("Last 12 months", "Same period last year", LO, HI)
    assert w.start == pd.Timestamp("2017-01-01")
    assert w.end.date() == HI.date()
    assert w.prev_start == pd.Timestamp("2016-01-01")
    assert w.prev_end.date() == pd.Timestamp("2016-12-30").date()


def test_previous_period_has_equal_length_and_no_overlap():
    w = filters.compute_window("Last 90 days", "Previous period", LO, HI)
    assert w.prev_end < w.start
    assert (w.end - w.start) == (w.prev_end - w.prev_start)


def test_ytd_and_qtd():
    ytd = filters.compute_window("Year to date", "No comparison", LO, HI)
    qtd = filters.compute_window("Quarter to date", "No comparison", LO, HI)
    assert ytd.start == pd.Timestamp("2017-01-01") and ytd.prev_start is None
    assert qtd.start == pd.Timestamp("2017-10-01")


def test_all_time_has_no_previous_period_before_the_data():
    w = filters.compute_window("All time", "Same period last year", LO, HI)
    assert w.start == LO.normalize() and w.prev_start is None


def test_dimension_filters():
    df = pd.DataFrame({"region": ["West", "East", "West"], "revenue": [1, 2, 3]})
    out = filters.apply_dimension_filters(df, {"region": ["West"], "category": []})
    assert out["revenue"].sum() == 4


# ----------------------------------------------------------
# Metrics
# ----------------------------------------------------------

def test_kpis_match_direct_pandas():
    df = ingest.load_sample().df
    k = metrics.kpis(df)
    assert k["revenue"].value == pytest.approx(df["revenue"].sum())
    assert k["profit"].value == pytest.approx(df["profit"].sum())
    assert k["orders"].value == df["order_id"].nunique()
    assert k["margin"].value == pytest.approx(df["profit"].sum() / df["revenue"].sum())
    assert k["aov"].value == pytest.approx(df["revenue"].sum() / df["order_id"].nunique())


def test_change_uses_pp_for_ratios_and_pct_for_amounts():
    a = metrics.KPI("revenue", "Revenue", 120.0, "money")
    b = metrics.KPI("revenue", "Revenue", 100.0, "money")
    assert metrics.change(a, b) == pytest.approx(0.2)
    m1 = metrics.KPI("margin", "Margin", 0.12, "pct", kind="pp")
    m0 = metrics.KPI("margin", "Margin", 0.15, "pct", kind="pp")
    assert metrics.change(m1, m0) == pytest.approx(-0.03)


def test_monthly_series_sums_to_total_and_has_no_gaps():
    df = ingest.load_sample().df
    s = metrics.series(df, "revenue", "Month")
    assert s.sum() == pytest.approx(df["revenue"].sum())
    assert len(s) == 48


def test_breakdown_shares_sum_to_one():
    df = ingest.load_sample().df
    b = metrics.breakdown(df, "region")
    assert b["share"].sum() == pytest.approx(1.0)
    assert b["revenue"].is_monotonic_decreasing


# ----------------------------------------------------------
# Storage
# ----------------------------------------------------------

def test_targets_round_trip(tmp_path):
    path = tmp_path / "t.db"
    db.save_targets("abc", pd.DataFrame({"month": ["2017-01", "2017-02"], "revenue_target": [100.0, None]}), path)
    out = db.load_targets("abc", path)
    assert out.to_dict("records") == [{"month": "2017-01", "revenue_target": 100.0}]


def test_runs_are_listed_newest_first(tmp_path):
    path = tmp_path / "r.db"
    first = db.save_run(dataset_name="a", dataset_digest="d", metric="revenue", grain="Month",
                        horizon=6, model="ETS", mape=0.1, params={}, results={}, path=path)
    second = db.save_run(dataset_name="b", dataset_digest="d", metric="revenue", grain="Month",
                         horizon=6, model="ETS", mape=0.2, params={}, results={"x": 1}, path=path)
    runs = db.list_runs(path)
    assert runs["id"].tolist()[0] == second
    assert db.get_run(second, path)["results"] == {"x": 1}
    db.delete_runs([first], path)
    assert db.list_runs(path)["id"].tolist() == [second]


# ----------------------------------------------------------
# Messy files
# ----------------------------------------------------------

def test_day_first_dates_are_detected_from_the_whole_column():
    from core.cleaning import detect_dayfirst, parse_dates
    # The first value is ambiguous; a later one (28/11) settles it.
    s = pd.Series(["07/04/2023", "28/11/2023", "01/02/2024"])
    assert detect_dayfirst(s) is True
    assert parse_dates(s).dt.month.tolist() == [4, 11, 2]
    assert detect_dayfirst(pd.Series(["04/07/2023", "11/28/2023"])) is False
    assert detect_dayfirst(pd.Series(["2023-04-07"])) is None


def test_messy_export_is_read_cleanly():
    ds, _, mapping = load("messy.csv")
    df = ds.df
    assert mapping["order_date"] == "Date of Sale" and mapping["customer_id"] == "Cust"
    assert mapping["region"] == "Country"
    assert pd.api.types.is_float_dtype(df["revenue"])               # "€1,069.42" parsed
    assert df["order_date"].min() == pd.Timestamp("2023-01-01")     # day-first, nothing dropped by a bad guess
    assert ds.report["blank_rows_removed"] >= 1
    assert ds.report["duplicates_removed"] == 2                       # blank rows aren't counted here
    assert set(df["region"]) == {"Ireland", "Spain", "Portugal", "France"}   # "ireland " normalised

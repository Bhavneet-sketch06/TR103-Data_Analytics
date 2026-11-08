"""
Customer analytics: RFM segments, cohort retention, new vs returning, value.

All functions take canonical columns (order_date, order_id, customer_id,
revenue) and are pure pandas. "History" frames are every order up to the end
of the selected window, so a customer's first order is their real first order,
not the first one inside the window.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Period aliases matching metrics.GRAIN_FREQ (weeks start on Monday).
PERIOD_ALIAS = {"Day": "D", "Week": "W-SUN", "Month": "M", "Quarter": "Q"}

# Fixed order: best to worst. Used for sorting and chart order.
SEGMENTS = {
    "Champions": "Bought recently, buy often and spend the most.",
    "Loyal": "Buy regularly; responsive to loyalty offers.",
    "Potential loyalists": "Recent customers with a few orders; nurture them.",
    "New": "First order was recent; onboard them well.",
    "Need attention": "Middle of the pack on recency and frequency.",
    "At risk": "Used to buy often but haven't for a while.",
    "Can't lose": "Were among the best customers; now gone quiet.",
    "Hibernating": "Few orders, long ago; low priority.",
}


def _score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """1-5 score from the percentile rank (ties share a score)."""
    pct = values.rank(method="average", pct=True, ascending=higher_is_better)
    return np.ceil(pct * 5).clip(1, 5).astype(int)


def _segment(r: int, f: int) -> str:
    if r >= 4 and f >= 4:
        return "Champions"
    if f >= 4 and r >= 3:
        return "Loyal"
    if r >= 4 and f >= 2:
        return "Potential loyalists"
    if r >= 4:
        return "New"
    if r == 1 and f >= 4:
        return "Can't lose"
    if r <= 2 and f >= 3:
        return "At risk"
    if r <= 2:
        return "Hibernating"
    return "Need attention"


def rfm(history: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per customer: recency (days), frequency (orders), monetary, scores, segment."""
    as_of = as_of or history["order_date"].max()
    per = history.groupby("customer_id", observed=True).agg(
        last_order=("order_date", "max"),
        first_order=("order_date", "min"),
        frequency=("order_id", "nunique"),
        monetary=("revenue", "sum"),
    )
    per["recency"] = (as_of.normalize() - per["last_order"].dt.normalize()).dt.days
    per["r"] = _score(per["recency"], higher_is_better=False)
    per["f"] = _score(per["frequency"])
    per["m"] = _score(per["monetary"])
    per["segment"] = [_segment(r, f) for r, f in zip(per["r"], per["f"])]
    return per.reset_index()


def segment_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Customers, revenue and averages per RFM segment, in SEGMENTS order."""
    out = table.groupby("segment").agg(
        customers=("customer_id", "count"),
        revenue=("monetary", "sum"),
        avg_recency=("recency", "mean"),
        avg_orders=("frequency", "mean"),
    )
    out = out.reindex(list(SEGMENTS)).dropna(subset=["customers"])
    out["customers"] = out["customers"].astype(int)
    out["customer_share"] = out["customers"] / out["customers"].sum()
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    out["description"] = [SEGMENTS[s] for s in out.index]
    return out.reset_index()


def cohort_grain(history: pd.DataFrame, min_size: int = 20) -> str:
    """'M' when recent monthly cohorts are big enough to read, else 'Q'."""
    first = history.groupby("customer_id", observed=True)["order_date"].min().dt.to_period("M")
    recent = first.value_counts().sort_index().tail(12)
    return "M" if len(recent) and recent.median() >= min_size else "Q"


def cohorts(history: pd.DataFrame, grain: str = "M", n_cohorts: int = 12,
            max_age: int = 12, min_size: int = 10) -> pd.DataFrame:
    """
    Retention matrix: rows are the latest `n_cohorts` cohorts (the month or
    quarter of a customer's first order) with at least `min_size` customers;
    columns are periods since that first order (0 = the first period, always
    100%); values are the share of the cohort that ordered in that period.
    Cells that lie after the last order date are NaN.
    """
    period = history["order_date"].dt.to_period(grain)
    first = period.groupby(history["customer_id"], observed=True).min()
    active = pd.DataFrame({"customer_id": history["customer_id"], "period": period}).drop_duplicates()
    active["cohort"] = active["customer_id"].map(first)
    active["age"] = [(p - c).n for p, c in zip(active["period"], active["cohort"])]

    sizes = first.value_counts().sort_index()
    counts = active.pivot_table(index="cohort", columns="age", values="customer_id",
                                aggfunc="nunique", fill_value=0)
    matrix = counts.div(sizes, axis=0).reindex(columns=range(max_age + 1)).fillna(0.0)

    last = period.max()
    observed = np.array([(last - c).n for c in matrix.index])[:, None]
    matrix = matrix.mask(np.arange(max_age + 1)[None, :] > observed)

    keep = sizes.reindex(matrix.index) >= min_size
    matrix = matrix[keep.to_numpy()].tail(n_cohorts)
    matrix.insert(0, "size", sizes.reindex(matrix.index).astype(int))
    matrix.index = matrix.index.to_timestamp()
    return matrix


def new_vs_returning(history: pd.DataFrame, start, end, grain: str = "Month") -> pd.DataFrame:
    """
    Revenue and customers per period, split by whether the order came from a
    customer's first period ever (new) or a later one (returning).
    """
    first = history.groupby("customer_id", observed=True)["order_date"].min()
    rows = history[(history["order_date"] >= start) & (history["order_date"] <= end)]
    alias = PERIOD_ALIAS[grain]
    period = rows["order_date"].dt.to_period(alias)
    first_period = rows["customer_id"].map(first).dt.to_period(alias)
    kind = np.where(period == first_period, "New", "Returning")
    frame = rows.assign(kind=kind, period=period.dt.start_time)
    out = frame.groupby(["period", "kind"]).agg(
        revenue=("revenue", "sum"), customers=("customer_id", "nunique"),
    ).reset_index()
    return out


def summary(cur: pd.DataFrame, history: pd.DataFrame, start) -> dict:
    """Headline customer numbers for the window."""
    first = history.groupby("customer_id", observed=True)["order_date"].min()
    customers = cur["customer_id"].nunique()
    new = int((first[first.index.isin(cur["customer_id"].unique())] >= start).sum())
    orders_per = history.groupby("customer_id", observed=True)["order_id"].nunique()
    active = orders_per[orders_per.index.isin(cur["customer_id"].unique())]
    revenue = cur["revenue"].sum()
    return {
        "customers": customers,
        "new": new,
        "returning": customers - new,
        "repeat_rate": float((active > 1).mean()) if len(active) else None,
        "revenue_per_customer": revenue / customers if customers else None,
        "orders_per_customer": cur["order_id"].nunique() / customers if customers else None,
    }


def lifetime_value(history: pd.DataFrame) -> dict:
    """
    Simple historical customer value: average revenue per customer per active
    year, times the average observed lifespan in years. Descriptive, not a
    prediction.
    """
    per = history.groupby("customer_id", observed=True).agg(
        first=("order_date", "min"), last=("order_date", "max"), revenue=("revenue", "sum"),
    )
    span_years = (history["order_date"].max() - history["order_date"].min()).days / 365.25
    lifespan = ((per["last"] - per["first"]).dt.days / 365.25).clip(lower=1 / 12)
    yearly = (per["revenue"] / max(span_years, 1 / 12)).mean()
    return {
        "avg_revenue": float(per["revenue"].mean()),
        "avg_lifespan_years": float(lifespan.mean()),
        "yearly_value": float(yearly),
    }


def top_customers(cur: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    agg = {"revenue": ("revenue", "sum"), "orders": ("order_id", "nunique"),
           "last_order": ("order_date", "max")}
    if "profit" in cur:
        agg["profit"] = ("profit", "sum")
    keys = ["customer_id"] + (["customer_name"] if "customer_name" in cur else [])
    out = cur.groupby(keys, observed=True).agg(**agg).reset_index()
    return out.sort_values("revenue", ascending=False).head(n).reset_index(drop=True)

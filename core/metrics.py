"""
Metrics layer: pure pandas functions over canonical columns.

Every number on every page (and every number the AI assistant quotes) comes
from here, so it's tested once and consistent everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

GRAIN_FREQ = {"Day": "D", "Week": "W-MON", "Month": "MS", "Quarter": "QS"}


@dataclass(frozen=True)
class KPI:
    key: str
    label: str
    value: float | None
    fmt: str                    # "money" | "count" | "pct" | "days" | "number"
    higher_is_better: bool = True
    kind: str = "pct"           # how to express change: relative "pct" or "pp" for ratios


def _safe_div(a, b):
    return a / b if b else None


def kpis(df: pd.DataFrame) -> dict[str, KPI]:
    """Headline KPIs for a slice. Fields that aren't mapped are skipped."""
    revenue = float(df["revenue"].sum())
    orders = df["order_id"].nunique() if "order_id" in df else len(df)
    out = {
        "revenue": KPI("revenue", "Revenue", revenue, "money"),
        "orders": KPI("orders", "Orders", float(orders), "count"),
        "aov": KPI("aov", "Avg order value", _safe_div(revenue, orders), "money"),
    }
    if "profit" in df:
        profit = float(df["profit"].sum())
        out["profit"] = KPI("profit", "Profit", profit, "money")
        out["margin"] = KPI("margin", "Profit margin", _safe_div(profit, revenue), "pct", kind="pp")
    if "customer_id" in df:
        out["customers"] = KPI("customers", "Customers", float(df["customer_id"].nunique()), "count")
    if "quantity" in df:
        out["units"] = KPI("units", "Units sold", float(df["quantity"].sum()), "count")
    if "discount" in df:
        avg_discount = df["discount"].mean()
        out["discount"] = KPI("discount", "Avg discount",
                              None if pd.isna(avg_discount) else float(avg_discount),
                              "pct", higher_is_better=False, kind="pp")
    if "ship_days" in df:
        days = df["ship_days"].mean()
        out["ship_days"] = KPI("ship_days", "Avg ship time", None if pd.isna(days) else float(days),
                               "days", higher_is_better=False)
    return out


def change(current: KPI, previous: KPI | None) -> float | None:
    """Relative change for 'pct' KPIs, absolute difference for 'pp' (ratio) KPIs."""
    if previous is None or current.value is None or previous.value is None:
        return None
    if current.kind == "pp":
        return current.value - previous.value
    if previous.value == 0:
        return None
    return (current.value - previous.value) / abs(previous.value)


def series(df: pd.DataFrame, metric: str = "revenue", grain: str = "Month") -> pd.Series:
    """
    Time series of a metric at a grain. Resampling yields every period between
    the first and last order, so empty periods are real zeros, not gaps.
    """
    freq = GRAIN_FREQ[grain]
    frame = df.set_index("order_date")
    if metric == "orders":
        return frame["order_id"].resample(freq).nunique()
    if metric == "customers":
        return frame["customer_id"].resample(freq).nunique()
    if metric == "margin":
        rev = frame["revenue"].resample(freq).sum()
        return frame["profit"].resample(freq).sum() / rev.where(rev != 0)
    return frame[metric].resample(freq).sum()


def kpi_series(df: pd.DataFrame, key: str, grain: str = "Month") -> pd.Series:
    """Time series for any key returned by kpis() (used for sparklines)."""
    freq = GRAIN_FREQ[grain]
    frame = df.set_index("order_date")
    if key in ("revenue", "profit", "orders", "customers", "margin"):
        return series(df, key, grain)
    if key == "units":
        return frame["quantity"].resample(freq).sum()
    if key == "aov":
        orders = frame["order_id"].resample(freq).nunique()
        return frame["revenue"].resample(freq).sum() / orders.where(orders != 0)
    if key in ("discount", "ship_days"):
        return frame[key].resample(freq).mean()
    raise KeyError(key)


def comparison_series(prev: pd.DataFrame, current: pd.Series, window, metric: str = "revenue",
                      grain: str = "Month") -> pd.Series:
    """
    The comparison period's series moved onto the current period's dates, so
    both lines share one x-axis. Same-period-last-year shifts by one calendar
    year (months stay aligned); previous-period shifts by the window length.
    """
    if window.compare == "Same period last year":
        offset = pd.DateOffset(years=1)
    else:
        offset = window.start - window.prev_start
    shifted = prev.assign(order_date=prev["order_date"] + offset)
    return series(shifted, metric, grain).reindex(current.index)


def auto_grain(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """A sensible default grain for a window length."""
    days = (end - start).days
    if days <= 45:
        return "Day"
    if days <= 200:
        return "Week"
    return "Month"


def breakdown(df: pd.DataFrame, dim: str, metric: str = "revenue") -> pd.DataFrame:
    """Revenue/profit/orders by a dimension, sorted by the chosen metric."""
    agg = {"revenue": ("revenue", "sum"), "orders": ("order_id", "nunique")}
    if "profit" in df:
        agg["profit"] = ("profit", "sum")
    out = df.groupby(dim, observed=True).agg(**agg).reset_index()
    if "profit" in out:
        out["margin"] = out["profit"] / out["revenue"].where(out["revenue"] != 0)
    total = out["revenue"].sum()
    out["share"] = out["revenue"] / total if total else 0.0
    return out.sort_values(metric, ascending=False).reset_index(drop=True)


def top_movers(cur: pd.DataFrame, prev: pd.DataFrame | None, dim: str,
               metric: str = "revenue", n: int = 5) -> pd.DataFrame:
    """Biggest absolute changes in a metric by dimension value between periods."""
    if prev is None:
        return pd.DataFrame(columns=[dim, "current", "previous", "change", "change_pct"])
    a = cur.groupby(dim, observed=True)[metric].sum().rename("current")
    b = prev.groupby(dim, observed=True)[metric].sum().rename("previous")
    out = pd.concat([a, b], axis=1).fillna(0.0)
    out["change"] = out["current"] - out["previous"]
    out["change_pct"] = out["change"] / out["previous"].where(out["previous"] != 0)
    out = out.reindex(out["change"].abs().sort_values(ascending=False).index).head(n)
    return out.reset_index().rename(columns={"index": dim})

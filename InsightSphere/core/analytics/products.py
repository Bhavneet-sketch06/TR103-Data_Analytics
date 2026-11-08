"""
Product analytics: Pareto / ABC classes, loss-makers, discount bands and
seasonality. Pure pandas over canonical columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ABC thresholds on cumulative revenue share.
A_CUTOFF, B_CUTOFF = 0.80, 0.95

DISCOUNT_BANDS = [
    (0.0, 0.0, "No discount"),
    (0.0, 0.10, "1–10%"),
    (0.10, 0.20, "11–20%"),
    (0.20, 0.30, "21–30%"),
    (0.30, 0.50, "31–50%"),
    (0.50, 1.0, "Over 50%"),
]
BAND_ORDER = [label for *_, label in DISCOUNT_BANDS]


def pareto(df: pd.DataFrame, dim: str = "product") -> pd.DataFrame:
    """
    Items ranked by revenue with cumulative share and an ABC class.
    A = items making up the first 80% of revenue, B = the next 15%, C = the rest.
    An item is classed by where its revenue *starts*, so the item that crosses
    80% is still an A.
    """
    agg = {"revenue": ("revenue", "sum")}
    if "profit" in df:
        agg["profit"] = ("profit", "sum")
    if "quantity" in df:
        agg["units"] = ("quantity", "sum")
    out = df.groupby(dim, observed=True).agg(**agg).sort_values("revenue", ascending=False)
    total = out["revenue"].sum()
    out["share"] = out["revenue"] / total if total else 0.0
    out["cum_share"] = out["share"].cumsum()
    start = out["cum_share"] - out["share"]
    out["abc"] = np.select([start < A_CUTOFF, start < B_CUTOFF], ["A", "B"], default="C")
    out["rank_share"] = np.arange(1, len(out) + 1) / max(len(out), 1)
    return out.reset_index()


def abc_summary(table: pd.DataFrame) -> pd.DataFrame:
    out = table.groupby("abc").agg(items=("revenue", "size"), revenue=("revenue", "sum"))
    out = out.reindex(["A", "B", "C"]).fillna(0)
    out["item_share"] = out["items"] / out["items"].sum()
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    return out.reset_index()


def top_share(table: pd.DataFrame, item_share: float = 0.2) -> float:
    """Share of revenue made by the top `item_share` of items (e.g. top 20%)."""
    if table.empty:
        return 0.0
    n = max(1, int(round(len(table) * item_share)))
    return float(table["share"].head(n).sum())


def loss_makers(df: pd.DataFrame, dim: str = "product", n: int = 10) -> pd.DataFrame:
    """Items with the most negative total profit."""
    keys = [dim] + (["category"] if "category" in df and dim != "category" else [])
    out = df.groupby(keys, observed=True).agg(
        revenue=("revenue", "sum"), profit=("profit", "sum"),
        **({"avg_discount": ("discount", "mean")} if "discount" in df else {}),
    ).reset_index()
    out["margin"] = out["profit"] / out["revenue"].where(out["revenue"] != 0)
    return out[out["profit"] < 0].sort_values("profit").head(n).reset_index(drop=True)


def discount_band(discount: pd.Series) -> pd.Series:
    """Buckets a 0–1 discount into the labelled bands (missing stays missing)."""
    labels = pd.Series(pd.NA, index=discount.index, dtype="object")
    labels[discount == 0] = "No discount"
    for lo, hi, label in DISCOUNT_BANDS[1:]:
        labels[(discount > lo) & (discount <= hi)] = label
    return pd.Categorical(labels, categories=BAND_ORDER, ordered=True)


def discount_bands(df: pd.DataFrame) -> pd.DataFrame:
    """
    Revenue, profit, margin and share of loss-making lines per discount band.
    Describes the observed relationship only; it doesn't prove discounts
    cause the margin change.
    """
    frame = df.assign(band=discount_band(df["discount"]))
    agg = {"lines": ("revenue", "size"), "revenue": ("revenue", "sum")}
    if "profit" in df:
        agg["profit"] = ("profit", "sum")
        agg["loss_lines"] = ("profit", lambda s: int((s < 0).sum()))
    out = frame.groupby("band", observed=False).agg(**agg)
    out = out[out["lines"] > 0]
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    if "profit" in out:
        out["margin"] = out["profit"] / out["revenue"].where(out["revenue"] != 0)
        out["loss_share"] = out["loss_lines"] / out["lines"]
    return out.reset_index()


def seasonality(df: pd.DataFrame, metric: str = "revenue") -> pd.DataFrame:
    """Month (rows, Jan..Dec) x year (columns) totals. Months with no data are NaN."""
    frame = df.assign(year=df["order_date"].dt.year, month=df["order_date"].dt.month)
    table = frame.pivot_table(index="month", columns="year", values=metric, aggfunc="sum")
    return table.reindex(range(1, 13))


def product_table(cur: pd.DataFrame, history: pd.DataFrame | None = None, months: int = 12) -> pd.DataFrame:
    """Per-product totals plus a monthly revenue trend list for in-table sparklines."""
    table = pareto(cur, "product")
    first_cols = [c for c in ("category", "sub_category") if c in cur]
    if first_cols:
        info = cur.groupby("product", observed=True)[first_cols].first()
        table = table.merge(info, left_on="product", right_index=True, how="left")
    if "profit" in table:
        table["margin"] = table["profit"] / table["revenue"].where(table["revenue"] != 0)
    if history is not None and not history.empty:
        end = history["order_date"].max().to_period("M")
        idx = pd.period_range(end - (months - 1), end, freq="M")
        recent = history[history["order_date"].dt.to_period("M") >= idx[0]]
        monthly = (recent.groupby(["product", recent["order_date"].dt.to_period("M")], observed=True)
                   ["revenue"].sum().unstack(fill_value=0).reindex(columns=idx, fill_value=0))
        table["trend"] = table["product"].map(lambda p: monthly.loc[p].tolist() if p in monthly.index else [])
    return table

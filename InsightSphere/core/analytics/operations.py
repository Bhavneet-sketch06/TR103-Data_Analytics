"""
Operations analytics: shipping performance and geography helpers.
"""

from __future__ import annotations

import pandas as pd

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
_CODES = set(US_STATES.values())
_BY_LOWER = {name.lower(): code for name, code in US_STATES.items()}


def state_code(value) -> str | None:
    text = str(value).strip()
    if text.upper() in _CODES:
        return text.upper()
    return _BY_LOWER.get(text.lower())


def looks_like_us_states(values, threshold: float = 0.8) -> bool:
    """True when most distinct values are US state names or codes."""
    distinct = pd.Series(pd.unique(pd.Series(values).dropna().astype(str)))
    if distinct.empty:
        return False
    return distinct.map(state_code).notna().mean() >= threshold


def shipping_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Orders, share, ship time and margin per ship mode."""
    agg = {"orders": ("order_id", "nunique"), "revenue": ("revenue", "sum")}
    if "ship_days" in df:
        agg["avg_days"] = ("ship_days", "mean")
        agg["p90_days"] = ("ship_days", lambda s: s.quantile(0.9))
    if "profit" in df:
        agg["profit"] = ("profit", "sum")
    out = df.groupby("ship_mode", observed=True).agg(**agg)
    out["order_share"] = out["orders"] / out["orders"].sum()
    if "profit" in out:
        out["margin"] = out["profit"] / out["revenue"].where(out["revenue"] != 0)
    sort_by = "avg_days" if "avg_days" in out else "orders"
    return out.sort_values(sort_by).reset_index()


def ship_days_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Order count per whole number of ship days (one row per order)."""
    per_order = df.groupby("order_id", observed=True)["ship_days"].max().dropna()
    counts = per_order.round().astype(int).value_counts().sort_index()
    return counts.rename_axis("days").reset_index(name="orders")

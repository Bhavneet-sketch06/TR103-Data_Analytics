"""
Anomaly detection on monthly series: the total and each category, region
and segment, for revenue and profit margin.

Each month is compared with what was expected *from the months before it*:
  * revenue: the same month last year, scaled by the trailing 12-month growth
    (the year-over-year ratio of the last 12 months to the 12 before them),
    checked from the 25th month on; with under three years of history (too
    few such months to judge what's typical), the median of the previous
    6 months instead
  * margin: the median margin of the previous 12 months
The miss is measured as a log ratio for revenue (a 30% miss counts the same
for a small or large slice) and as a difference for margin. A month is
unusual when its miss is more than `threshold` robust z-scores from the
typical miss across the whole history (median and MAD, so a few big misses
can't hide themselves by inflating the spread). Only complete months are
checked.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import metrics

DIMS = ("category", "region", "segment")
THRESHOLD = 3.5
MIN_MONTHS = 12
MIN_SHARE = 0.05          # skip slices too small for a stable monthly series
MIN_MONTHLY_ORDERS = 15   # ...or with so few orders a month that one big order looks "unusual"


def complete_months(df: pd.DataFrame) -> pd.DataFrame:
    """Drops the last month if the data stops more than three days before it ends."""
    last = df["order_date"].max().normalize()
    month_end = last + pd.offsets.MonthEnd(0)
    if (month_end - last).days > 3:
        return df[df["order_date"] < last.replace(day=1)]
    return df


def expected_values(y: pd.Series, metric: str) -> pd.Series:
    """Out-of-sample expectation for each month (NaN until there's enough history)."""
    values = y.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    # One method per series, so the typical miss (the z-score scale) isn't a mix of two methods.
    seasonal = metric != "margin" and len(values) >= 36
    for t in range(len(values)):
        if metric == "margin":
            if t >= 6:
                out[t] = np.nanmedian(values[max(0, t - 12):t])
        elif seasonal:
            if t >= 24:
                recent, before = values[t - 12:t].sum(), values[t - 24:t - 12].sum()
                if before > 0 and recent > 0:
                    out[t] = values[t - 12] * recent / before
        elif t >= 6:
            out[t] = np.median(values[t - 6:t])
    return pd.Series(out, index=y.index)


def misses(y: pd.Series, expected: pd.Series, metric: str) -> pd.Series:
    if metric == "margin":
        return y - expected
    ok = (y > 0) & (expected > 0)
    return np.log(y.where(ok) / expected.where(ok))


def robust_z(residual: pd.Series) -> pd.Series:
    r = residual.dropna()
    if len(r) < 6:
        return pd.Series(0.0, index=residual.index)
    median = r.median()
    mad = (r - median).abs().median()
    if not mad:
        return pd.Series(0.0, index=residual.index)
    return (0.6745 * (residual - median) / mad).fillna(0.0)


def _monthly(df: pd.DataFrame, metric: str) -> pd.Series:
    y = metrics.series(df, "margin" if metric == "margin" else metric, "Month")
    return y.astype(float)


def detect(history: pd.DataFrame, start, end, dims=DIMS, metrics_=("revenue", "margin"),
           threshold: float = THRESHOLD) -> pd.DataFrame:
    """
    Unusual months between start and end. One row per finding:
    scope ("Total" or a dimension value), dim, metric, month, actual, expected, z.
    """
    data = complete_months(history)
    if data.empty:
        return _empty()
    total_revenue = data["revenue"].sum()
    slices = [("Total", None, data)]
    for dim in dims:
        if dim not in data:
            continue
        for value, part in data.groupby(dim, observed=True):
            if part["revenue"].sum() >= MIN_SHARE * total_revenue:
                slices.append((str(value), dim, part))

    rows = []
    for scope, dim, part in slices:
        for metric in metrics_:
            if metric == "margin" and "profit" not in part:
                continue
            y = _monthly(part, metric).dropna()
            if len(y) < MIN_MONTHS:
                continue
            orders = part.groupby(part["order_date"].dt.to_period("M"))["order_id"].nunique()
            if orders.median() < MIN_MONTHLY_ORDERS:
                continue
            expected = expected_values(y, metric)
            z = robust_z(misses(y, expected, metric))
            window = (y.index >= pd.Timestamp(start).normalize().replace(day=1)) & (y.index <= pd.Timestamp(end))
            for month in y.index[window & (z.abs() >= threshold).to_numpy()]:
                rows.append({"scope": scope, "dim": dim, "metric": metric, "month": month,
                             "actual": float(y[month]), "expected": float(expected[month]), "z": float(z[month])})
    if not rows:
        return _empty()
    out = pd.DataFrame(rows)
    return out.reindex(out["z"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["scope", "dim", "metric", "month", "actual", "expected", "z"])


def _money(v: float) -> str:
    for threshold, suffix in ((1e6, "M"), (1e3, "K")):
        if abs(v) >= threshold:
            return f"${v / threshold:.1f}{suffix}"
    return f"${v:,.0f}"


def as_items(found: pd.DataFrame, limit: int = 3) -> list[dict]:
    """Plain-language alerts for the Overview card. Numbers are in the text."""
    items = []
    for _, a in found.head(limit).iterrows():
        high = a["z"] > 0
        who = "Total" if a["scope"] == "Total" else a["scope"]
        when = f"{a['month']:%b %Y}"
        if a["metric"] == "revenue":
            title = f"{who} revenue unusually {'high' if high else 'low'} in {when}"
            diff = (a["actual"] - a["expected"]) / a["expected"] if a["expected"] else None
            body = f"{_money(a['actual'])} vs about {_money(a['expected'])} expected" + \
                   (f" ({diff * 100:+.0f}%)." if diff is not None else ".")
        else:
            title = f"{who} margin unusually {'high' if high else 'low'} in {when}"
            body = f"{a['actual'] * 100:.1f}% vs about {a['expected'] * 100:.1f}% expected."
        items.append({"tone": "good" if high else "bad", "title": title, "body": body,
                      "icon": "alert"})
    return items

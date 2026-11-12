"""
What-if simulator: discount, price and volume levers on a baseline.

The discount lever is the data-driven part. For each category, a
revenue-weighted regression of line margin on line discount gives how much
margin moves per point of discount in *this* data. That's an observed
association across order lines, not proof that changing discounts causes the
change, and the page says so. Its standard error gives the low/high range.

Price and volume are plain arithmetic:
  * price +p% at the same volume: revenue x (1+p), costs unchanged
  * volume +v%: revenue, costs and profit all x (1+v)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Levers:
    discount_pp: float = 0.0     # change in average discount, 0.05 = +5 points
    price_pct: float = 0.0       # 0.03 = prices +3%
    volume_pct: float = 0.0      # 0.10 = volume +10%


def discount_response(history: pd.DataFrame, group: str = "category") -> pd.DataFrame:
    """
    Per group: revenue share, current margin and discount, and the margin
    change per 1.00 of discount (slope) with its standard error.
    """
    rows = []
    frame = history[(history["revenue"] > 0) & history["discount"].notna() & history["profit"].notna()]
    groups = frame.groupby(group, observed=True) if group in frame else [("All", frame)]
    total = frame["revenue"].sum()
    for name, part in groups:
        w = part["revenue"].to_numpy()
        x = part["discount"].to_numpy()
        y = (part["profit"] / part["revenue"]).to_numpy()
        slope, se = _weighted_slope(x, y, w)
        rows.append({
            group: str(name),
            "revenue_share": w.sum() / total if total else 0.0,
            "margin": part["profit"].sum() / w.sum(),
            "discount": float(np.average(x, weights=w)),
            "slope": slope,
            "slope_se": se,
        })
    return pd.DataFrame(rows)


def _weighted_slope(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    if len(x) < 3 or np.allclose(x, x[0]):
        return 0.0, 0.0
    w = w / w.sum()
    xm, ym = np.sum(w * x), np.sum(w * y)
    sxx = np.sum(w * (x - xm) ** 2)
    slope = np.sum(w * (x - xm) * (y - ym)) / sxx
    resid = y - (ym + slope * (x - xm))
    # Kish effective sample size; with normalized weights var(slope) = sum(w r^2) / ((n_eff - 2) * sxx).
    n_eff = 1.0 / np.sum(w ** 2)
    var = np.sum(w * resid ** 2) / (max(n_eff - 2, 1) * sxx)
    return float(slope), float(np.sqrt(max(var, 0.0)))


def simulate(baseline_revenue: float, response: pd.DataFrame, levers: Levers) -> dict:
    """
    Applies the levers to a baseline revenue split by the response table's
    revenue shares (each group keeps its current margin as the baseline).
    Returns totals for baseline and scenario, a low/high profit range, the
    waterfall steps, and the per-group table.
    """
    rows = []
    for _, g in response.iterrows():
        rev0 = baseline_revenue * g["revenue_share"]
        m0 = g["margin"]
        d0 = g["discount"]
        dd = levers.discount_pp
        # More discount at the same volume lowers revenue; margin follows the observed slope.
        rev_d = rev0 * (1 - dd / (1 - d0)) if d0 < 1 else rev0
        m_d = m0 + g["slope"] * dd
        span = 1.96 * g["slope_se"] * abs(dd)
        rev_p = rev_d * (1 + levers.price_pct)
        rev_v = rev_p * (1 + levers.volume_pct)

        def profit(margin):
            # price: costs stay put, so the extra revenue is all profit
            return rev_d * (margin + levers.price_pct) * (1 + levers.volume_pct)

        rows.append({
            "group": g.iloc[0],
            "baseline_revenue": rev0, "baseline_profit": rev0 * m0,
            "after_discount_profit": rev_d * m_d,
            "after_price_profit": rev_d * (m_d + levers.price_pct),
            "revenue": rev_v, "profit": profit(m_d),
            "profit_low": profit(m_d - span), "profit_high": profit(m_d + span),
        })
    table = pd.DataFrame(rows)
    totals = table.drop(columns="group").sum()
    base_profit, profit_total = totals["baseline_profit"], totals["profit"]
    steps = [
        ("Baseline", base_profit),
        ("Discount", totals["after_discount_profit"] - base_profit),
        ("Price", totals["after_price_profit"] - totals["after_discount_profit"]),
        ("Volume", profit_total - totals["after_price_profit"]),
    ]
    table["margin"] = table["profit"] / table["revenue"].where(table["revenue"] != 0)
    return {
        "baseline_revenue": totals["baseline_revenue"],
        "baseline_profit": base_profit,
        "baseline_margin": base_profit / totals["baseline_revenue"] if totals["baseline_revenue"] else None,
        "revenue": totals["revenue"],
        "profit": profit_total,
        "profit_low": totals["profit_low"],
        "profit_high": totals["profit_high"],
        "margin": profit_total / totals["revenue"] if totals["revenue"] else None,
        "steps": steps,
        "table": table,
    }

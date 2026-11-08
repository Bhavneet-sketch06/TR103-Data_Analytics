"""
Plain-language highlights for the Overview, built from the metrics layer.

Each item is {tone, title, body}: tone is good / bad / warn / info, and the
numbers are in the text so the meaning never depends on color alone.
"""

from __future__ import annotations

import pandas as pd

from core import metrics


def _money(v: float) -> str:
    sign = "-" if v < 0 else "+"
    v = abs(v)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}${v / threshold:.1f}{suffix}"
    return f"{sign}${v:,.0f}"


def _pct(v: float | None) -> str:
    return "" if v is None or pd.isna(v) else f" ({v * 100:+.1f}%)"


def highlights(cur: pd.DataFrame, prev: pd.DataFrame | None, period: str, limit: int = 5) -> list[dict]:
    """Headline changes and the biggest movers versus the comparison period."""
    if prev is None or prev.empty or cur.empty:
        return []
    items = []
    now, before = metrics.kpis(cur), metrics.kpis(prev)

    rev = metrics.change(now["revenue"], before["revenue"])
    if rev is not None:
        items.append({
            "tone": "good" if rev >= 0 else "bad",
            "title": f"Revenue {'up' if rev >= 0 else 'down'} {abs(rev) * 100:.1f}% {period}",
            "body": f"{_money(now['revenue'].value - before['revenue'].value)[1:]} "
                    f"{'more' if rev >= 0 else 'less'} than the comparison period.",
        })
    if "margin" in now:
        pp = metrics.change(now["margin"], before["margin"])
        if pp is not None and abs(pp) >= 0.005:
            items.append({
                "tone": "good" if pp > 0 else "warn",
                "title": f"Profit margin {'up' if pp > 0 else 'down'} {abs(pp) * 100:.1f}pp",
                "body": f"Now {now['margin'].value * 100:.1f}%, from {before['margin'].value * 100:.1f}%.",
            })

    for dim, label in (("category", "Category"), ("sub_category", "Sub-category"), ("region", "Region")):
        if dim not in cur:
            continue
        movers = metrics.top_movers(cur, prev, dim, "revenue", n=50)
        if movers.empty:
            continue
        up, down = movers.sort_values("change").iloc[-1], movers.sort_values("change").iloc[0]
        if up["change"] > 0:
            items.append({
                "tone": "good",
                "title": f"{up[dim]} led growth",
                "body": f"{label}: {_money(up['change'])}{_pct(up['change_pct'])} revenue {period}.",
            })
        if down["change"] < 0:
            items.append({
                "tone": "bad",
                "title": f"{down[dim]} declined",
                "body": f"{label}: {_money(down['change'])}{_pct(down['change_pct'])} revenue {period}.",
            })
    return items[:limit]

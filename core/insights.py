"""
Plain-language insights: what each page's numbers mean, in sentences.

Each item is {tone, title, body}: tone is good / bad / warn / info, and the
numbers are in the text so the meaning never depends on color alone. The
page functions (overview_verdict, sales_takeaways, ...) say what a reader
should conclude from that page; they only state what the data shows.
"""

from __future__ import annotations

import calendar

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
                "title": f"Profit margin {'up' if pp > 0 else 'down'} {abs(pp) * 100:.1f} points",
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


# ----------------------------------------------------------
# Small formatting helpers for sentences
# ----------------------------------------------------------

def money(v: float) -> str:
    """$733.2K, -$12.4K, $950 (no plus sign)."""
    sign = "-" if v < 0 else ""
    v = abs(v)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}${v / threshold:.1f}{suffix}"
    return f"{sign}${v:,.0f}"


def share(v: float) -> str:
    return f"{v * 100:.0f}%"


def pct1(v: float) -> str:
    return f"{v * 100:.1f}%"


def _change_words(change: float | None) -> str:
    """'up 20.5%', 'down 3.1%', 'about the same'."""
    if change is None or pd.isna(change):
        return ""
    if abs(change) < 0.005:
        return "about the same"
    return f"{'up' if change > 0 else 'down'} {abs(change) * 100:.1f}%"


def _names(values, limit: int = 3) -> str:
    values = [str(v) for v in values][:limit]
    if len(values) <= 1:
        return "".join(values)
    return ", ".join(values[:-1]) + " and " + values[-1]


# ----------------------------------------------------------
# Overview
# ----------------------------------------------------------

def overview_verdict(cur: pd.DataFrame, prev: pd.DataFrame | None, period: str) -> dict:
    """
    The one-glance answer: is the business making money, and is it getting
    better? Returns {tone, headline, body}.
    """
    now = metrics.kpis(cur)
    before = metrics.kpis(prev) if prev is not None and not prev.empty else {}
    revenue = now["revenue"].value
    rev_change = metrics.change(now["revenue"], before.get("revenue"))
    growing = rev_change is not None and rev_change > 0.02
    shrinking = rev_change is not None and rev_change < -0.02
    when = period.replace("vs ", "") if period else ""

    if "profit" not in now:
        headline = ("Sales are growing" if growing else "Sales are falling" if shrinking
                    else "Sales are steady" if rev_change is not None else "Sales summary")
        tone = "good" if growing else "bad" if shrinking else "info"
        body = f"You sold {money(revenue)} across {now['orders'].value:,.0f} orders."
        if rev_change is not None and when:
            body += f" That's {_change_words(rev_change)} on {when}."
        body += " Add a profit or cost column to see whether you're making money."
        return {"tone": tone, "headline": headline, "body": body}

    profit, margin = now["profit"].value, now["margin"].value
    profit_change = metrics.change(now["profit"], before.get("profit"))
    profit_falling = profit_change is not None and profit_change < -0.02
    if profit <= 0:
        tone, headline = "bad", "Losing money" + (", even though sales are up" if growing else "")
    elif growing and not profit_falling:
        tone, headline = "good", "Growing and profitable"
    elif growing and profit_falling:
        tone, headline = "warn", "Sales are up, but profit is down"
    elif shrinking:
        tone, headline = "warn", "Still profitable, but sales are falling"
    else:
        tone, headline = "good", "Profitable"

    if profit > 0:
        body = (f"You sold {money(revenue)} and kept {money(profit)} as profit, "
                f"about {margin * 100:.0f} cents of every dollar.")
    else:
        body = f"You sold {money(revenue)} but lost {money(-profit)} after costs."
    if rev_change is not None and when:
        body += f" Compared with {when}, sales are {_change_words(rev_change)}"
        body += f" and profit is {_change_words(profit_change)}." if profit_change is not None else "."
    return {"tone": tone, "headline": headline, "body": body}


def trend_summary(current: pd.Series, compared: pd.Series | None, grain: str = "Month",
                  as_money: bool = True) -> str:
    """One line under the trend chart: best period, and how often it beat the comparison."""
    current = current.dropna()
    if current.empty:
        return ""
    best = current.idxmax()
    labels = {"Day": f"{best:%b %d, %Y}", "Week": f"week of {best:%b %d, %Y}", "Month": f"{best:%B %Y}",
              "Quarter": f"Q{best.quarter} {best.year}"}
    value = money(current.max()) if as_money else f"{current.max():,.0f}"
    text = f"Best {grain.lower()}: {labels.get(grain, f'{best:%b %Y}')} ({value})."
    if compared is not None and compared.notna().any():
        both = pd.concat([current, compared], axis=1).dropna()
        above = int((both.iloc[:, 0] > both.iloc[:, 1]).sum())
        text += f" Ahead of the comparison period in {above} of {len(both)} {grain.lower()}s."
    return text


def breakdown_summary(table: pd.DataFrame) -> str:
    """'Technology sells the most (37% of sales). Furniture keeps the least profit (1.4% margin).'"""
    if table.empty:
        return ""
    lead = table.sort_values("revenue", ascending=False).iloc[0]
    text = f"{lead.iloc[0]} sells the most ({share(lead['share'])} of sales)."
    if "margin" in table and len(table) > 1:
        worst = table.sort_values("margin").iloc[0]
        if worst["margin"] < 0:
            text += f" {worst.iloc[0]} loses money ({pct1(worst['margin'])} margin)."
        else:
            text += f" {worst.iloc[0]} keeps the least profit ({pct1(worst['margin'])} margin)."
    return text


# ----------------------------------------------------------
# Sales
# ----------------------------------------------------------

def sales_takeaways(cur: pd.DataFrame, history: pd.DataFrame) -> list[dict]:
    from core.analytics import products

    items = []
    if "category" in cur:
        table = metrics.breakdown(cur, "category")
        lead = table.iloc[0]
        items.append({"tone": "info", "title": f"{lead['category']} brings in the most money",
                      "body": f"{money(lead['revenue'])}, {share(lead['share'])} of all sales in this period."})
    if "product" in cur:
        ranked = products.pareto(cur, "product")
        if len(ranked) >= 10:
            items.append({"tone": "info", "title": "A few products drive most sales",
                          "body": f"The top 20% of products bring in {share(products.top_share(ranked, 0.2))} of "
                                  "revenue. Keep these in stock and priced carefully."})
        if "profit" in cur:
            per = cur.groupby("product", observed=True)["profit"].sum()
            losing = per[per < 0].sort_values()
            if len(losing):
                items.append({"tone": "bad", "title": f"{len(losing):,} products lost money",
                              "body": f"{money(-losing.sum())} lost in total. Worst: {losing.index[0]} "
                                      f"({money(losing.iloc[0])}). Check their prices and discounts."})
            else:
                items.append({"tone": "good", "title": "Every product made a profit",
                              "body": "No product lost money in this period."})
    season = products.seasonality(history)
    if season.shape[1] >= 2:
        avg = season.mean(axis=1).dropna()
        if len(avg) >= 6 and avg.min() > 0:
            hi, lo = avg.idxmax(), avg.idxmin()
            items.append({"tone": "info",
                          "title": f"Sales peak in {calendar.month_name[hi]} and dip in {calendar.month_name[lo]}",
                          "body": f"On average {calendar.month_name[hi]} sells {avg[hi] / avg[lo]:.1f}× as much as "
                                  f"{calendar.month_name[lo]}. Plan stock and promotions around it."})
    return items


# ----------------------------------------------------------
# Customers
# ----------------------------------------------------------

def customer_takeaways(now: dict, before: dict | None, segments: pd.DataFrame,
                       top10_share: float | None) -> list[dict]:
    """now/before: customers.summary(); segments: customers.segment_summary()."""
    items = []
    change = None
    if before and before.get("customers"):
        change = (now["customers"] - before["customers"]) / before["customers"]
    items.append({"tone": "good" if (change or 0) > 0.02 else "bad" if (change or 0) < -0.02 else "info",
                  "title": f"{now['customers']:,} customers bought in this period",
                  "body": (f"That's {_change_words(change)} on the comparison period. " if change is not None else "")
                          + f"{now['new']:,} of them were buying for the first time."})
    rate = now.get("repeat_rate")
    if rate is not None:
        if rate >= 0.6:
            items.append({"tone": "good", "title": "Customers come back",
                          "body": f"{share(rate)} of them have ordered more than once. Loyalty is strong."})
        elif rate < 0.3:
            items.append({"tone": "warn", "title": "Most customers buy only once",
                          "body": f"Only {share(rate)} have ordered more than once. A follow-up offer after the "
                                  "first order could help."})
        else:
            items.append({"tone": "info", "title": f"{share(rate)} of customers buy again",
                          "body": "The rest have ordered once so far."})
    quiet = segments[segments["segment"].isin(["At risk", "Can't lose"])]
    if len(quiet) and quiet["customers"].sum() > 0:
        items.append({"tone": "warn", "title": f"{int(quiet['customers'].sum()):,} good customers have gone quiet",
                      "body": f"They used to buy often but haven't ordered for a while. Together they brought "
                              f"{share(quiet['revenue_share'].sum())} of all revenue: worth a win-back offer."})
    if top10_share is not None:
        if top10_share > 0.3:
            items.append({"tone": "warn", "title": "Sales depend on a few customers",
                          "body": f"The top 10 customers make {share(top10_share)} of revenue. Losing one would hurt."})
        else:
            items.append({"tone": "good", "title": "Sales are spread across many customers",
                          "body": f"The top 10 customers make only {share(top10_share)} of revenue."})
    return items


# ----------------------------------------------------------
# Regions
# ----------------------------------------------------------

def region_takeaways(cur: pd.DataFrame, prev: pd.DataFrame | None, period: str) -> list[dict]:
    items = []
    has_prev = prev is not None and not prev.empty
    if "region" in cur:
        table = metrics.breakdown(cur, "region")
        lead = table.iloc[0]
        body = f"{money(lead['revenue'])}, {share(lead['share'])} of all sales."
        if has_prev:
            before = prev.groupby("region", observed=True)["revenue"].sum()
            if before.get(lead["region"]):
                change = (lead["revenue"] - before[lead["region"]]) / before[lead["region"]]
                body += f" Sales {_change_words(change)} {period}."
        items.append({"tone": "info", "title": f"{lead['region']} is the biggest region", "body": body})
        if "margin" in table and len(table) > 1:
            worst = table.sort_values("margin").iloc[0]
            items.append({"tone": "bad" if worst["margin"] < 0 else "warn",
                          "title": f"{worst['region']} " + ("loses money" if worst["margin"] < 0
                                                             else "keeps the least profit"),
                          "body": f"Only {pct1(worst['margin'])} of its sales is profit, against "
                                  f"{pct1(table['profit'].sum() / table['revenue'].sum())} overall."})
        if has_prev and len(table) > 1:
            movers = metrics.top_movers(cur, prev, "region", "revenue", n=50)
            falling = movers[(movers["change"] < 0) & (movers["change_pct"] < -0.02)].sort_values("change")
            if len(falling):
                f = falling.iloc[0]
                pct_text = f" ({f['change_pct'] * 100:+.1f}%)" if pd.notna(f["change_pct"]) else ""
                items.append({"tone": "bad", "title": f"{f['region']} sales fell",
                              "body": f"{money(f['change'])}{pct_text} {period}."})
    if {"state", "profit"} <= set(cur.columns):
        per = cur.groupby("state", observed=True)["profit"].sum()
        losing = per[per < 0].sort_values()
        if len(losing):
            names = _names([f"{n} ({money(v)})" for n, v in losing.items()], 3)
            items.append({"tone": "bad",
                          "title": f"{len(losing)} state{'s' if len(losing) != 1 else ''} "
                                   f"lose{'' if len(losing) != 1 else 's'} money",
                          "body": f"{money(-losing.sum())} lost in total. Biggest: {names}."})
        else:
            items.append({"tone": "good", "title": "Every state is profitable",
                          "body": "No state lost money in this period."})
    return items


# ----------------------------------------------------------
# Operations
# ----------------------------------------------------------

def operations_takeaways(cur: pd.DataFrame) -> list[dict]:
    from core.analytics import operations, products

    items = []
    if {"discount", "profit"} <= set(cur.columns):
        bands = products.discount_bands(cur)
        losing = bands[bands["margin"] < 0]
        if len(losing):
            first = losing.iloc[0]
            items.append({"tone": "bad", "title": f"Discounts of {first['band']} and deeper lose money",
                          "body": f"Orders at {first['band']} off have a {pct1(first['margin'])} margin; the "
                                  f"worst level reaches {pct1(losing['margin'].min())}. "
                                  f"{share(losing['revenue_share'].sum())} of sales were made at these discounts."})
        elif len(bands):
            items.append({"tone": "good", "title": "Every discount level is still profitable",
                          "body": f"Even the deepest discounts kept a {pct1(bands['margin'].min())} margin."})
        dim = "sub_category" if "sub_category" in cur else ("category" if "category" in cur else None)
        if dim:
            agg = cur.groupby(dim, observed=True).agg(discount=("discount", "mean"), revenue=("revenue", "sum"),
                                                       profit=("profit", "sum"))
            agg["margin"] = agg["profit"] / agg["revenue"].where(agg["revenue"] != 0)
            worst = agg.sort_values("margin").iloc[0]
            if worst["margin"] < 0:
                items.append({"tone": "bad", "title": f"{worst.name} is the biggest drag",
                              "body": f"Discounted {share(worst['discount'])} on average and losing "
                                      f"{money(-worst['profit'])} ({pct1(worst['margin'])} margin)."})
    if {"ship_days", "order_id"} <= set(cur.columns):
        per_order = cur.groupby("order_id", observed=True)["ship_days"].max().dropna()
        if len(per_order):
            slow = (per_order > 5).mean()
            body = f"{share(slow)} of orders take more than 5 days."
            if "ship_mode" in cur:
                modes = operations.shipping_summary(cur)
                fast, slowest = modes.iloc[0], modes.iloc[-1]
                body += (f" {fast['ship_mode']} is fastest ({fast['avg_days']:.1f} days); "
                         f"{slowest['ship_mode']} is slowest ({slowest['avg_days']:.1f} days) and carries "
                         f"{share(slowest['order_share'])} of orders.")
            items.append({"tone": "warn" if slow > 0.25 else "info",
                          "title": f"Orders ship in {per_order.mean():.1f} days on average", "body": body})
    return items


# ----------------------------------------------------------
# Forecast
# ----------------------------------------------------------

def forecast_takeaways(result) -> list[dict]:
    f, y = result.forecast, result.series
    unit = "month" if result.grain == "Month" else "week"
    fmt = money if result.metric in ("revenue", "profit") else (lambda v: f"{v:,.0f}")
    name = {"revenue": "sales", "profit": "profit", "orders": "orders", "units": "units sold"}.get(result.metric, "")
    items = [{"tone": "info",
              "title": f"Expect about {fmt(f.mean.sum())} of {name} in the next {result.horizon} {unit}s",
              "body": f"Most likely between {fmt(f.lo80.sum())} and {fmt(f.hi80.sum())}."}]
    year_ago = f.index - (pd.DateOffset(years=1) if result.grain == "Month" else pd.Timedelta(weeks=52))
    last = y.reindex(year_ago)
    if last.notna().all() and last.sum():
        change = (f.mean.sum() - last.sum()) / abs(last.sum())
        items.append({"tone": "good" if change > 0.02 else "bad" if change < -0.02 else "info",
                      "title": f"That's {_change_words(change)} on the same {unit}s last year",
                      "body": f"Last year those {unit}s brought {fmt(last.sum())}."})
    if len(f.mean) >= 3:
        hi, lo = int(f.mean.argmax()), int(f.mean.argmin())
        label = (lambda d: f"{d:%B %Y}") if result.grain == "Month" else (lambda d: f"week of {d:%b %d}")
        items.append({"tone": "info", "title": f"Busiest {unit} ahead: {label(f.index[hi])}",
                      "body": f"About {fmt(f.mean[hi])}. Quietest: {label(f.index[lo])} (about {fmt(f.mean[lo])})."})
    chosen = result.comparison.set_index("model").loc[result.chosen]
    mape = chosen["mape"]
    if mape is not None and pd.notna(mape):
        items.append({"tone": "warn" if mape > 0.3 else "info",
                      "title": f"Past forecasts were off by about {share(mape)} on average",
                      "body": "Use this as a guide, not a promise: real months land above or below it."
                              if mape > 0.15 else "That's reliable enough for planning."})
    return items

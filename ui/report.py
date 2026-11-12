"""
One-click report: a self-contained HTML snapshot of the Overview.

No external files or scripts: charts are inline SVG, styles are inline, so the
file opens offline in any browser, can be emailed, and prints cleanly to PDF
(A4, light colors, cards never split across pages). Every piece of text that
comes from the uploaded file is escaped.

    html = report.build(ctx, filters.selections(), forecast=result, alerts=found)
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from core import anomalies, forecasting, insights, metrics
from core.schema import FIELD_BY_KEY
from ui.charts import money, pct
from ui.tokens import LIGHT, SERIES

T = LIGHT
BLUE = SERIES["light"][0]
LOGO = (Path(__file__).resolve().parent / "assets" / "logo.svg").read_text(encoding="utf-8")


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def _fmt(value, kind: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    return {"money": money(value), "count": f"{value:,.0f}", "pct": pct(value),
            "days": f"{value:.1f} days"}.get(kind, f"{value:,.2f}")


def _delta(change, higher_is_better=True, kind="pct") -> str:
    if change is None or pd.isna(change):
        return ""
    if abs(change) * 100 < 0.05:
        return '<span class="d flat">→ 0.0</span>'
    up = change > 0
    cls = "good" if up == higher_is_better else "bad"
    unit = "pp" if kind == "pp" else "%"
    return f'<span class="d {cls}">{"▲" if up else "▼"} {abs(change) * 100:.1f}{unit}</span>'


# ----------------------------------------------------------
# SVG charts
# ----------------------------------------------------------

def _axis_value(v: float) -> str:
    for threshold, suffix in ((1e6, "M"), (1e3, "K")):
        if abs(v) >= threshold:
            return f"${v / threshold:.0f}{suffix}"
    return f"${v:,.0f}"


def line_chart(current: pd.Series, previous: pd.Series | None, width=760, height=240) -> str:
    """Monthly revenue (solid) against the comparison period (dashed) with a light grid."""
    left, right, top, bottom = 56, 26, 12, 28
    values = list(current.dropna().values) + (list(previous.dropna().values) if previous is not None else [])
    hi = max(values) if values else 1.0
    hi = hi * 1.08 or 1.0
    w, h = width - left - right, height - top - bottom

    def xy(i, v, n):
        return left + (w * i / max(n - 1, 1)), top + h - (v / hi) * h

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Revenue trend">']
    for k in range(5):
        y = top + h - h * k / 4
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{T["grid"]}"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">{_axis_value(hi * k / 4)}</text>')
    n = len(current)
    for i, d in enumerate(current.index):
        if n <= 13 or i % max(n // 8, 1) == 0 or i == n - 1:
            x, _ = xy(i, 0, n)
            parts.append(f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" class="ax">{d:%b %y}</text>')
    if previous is not None and previous.notna().sum() > 1:
        pts = " ".join("{:.1f},{:.1f}".format(*xy(i, v, n)) for i, v in enumerate(previous.fillna(0).values))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{T["text_3"]}" stroke-width="1.6" '
                     'stroke-dasharray="4 4"/>')
    pts = " ".join("{:.1f},{:.1f}".format(*xy(i, v, n)) for i, v in enumerate(current.fillna(0).values))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{T["accent"]}" stroke-width="2.4" '
                 'stroke-linejoin="round"/>')
    for i, v in enumerate(current.fillna(0).values):
        x, y = xy(i, v, n)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{T["accent"]}"/>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(labels, values, notes=None, width=360) -> str:
    """Horizontal bars, largest first, value (and note) after each bar."""
    row, label_w, value_w = 28, 112, 120
    height = row * len(labels) + 6
    hi = max(values) if len(values) and max(values) > 0 else 1.0
    bar_w = width - label_w - value_w
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Bar chart">']
    for i, (label, v) in enumerate(zip(labels, values)):
        y = i * row + 4
        length = max(bar_w * max(v, 0) / hi, 1)
        text = money(v) + (f" · {notes[i]}" if notes else "")
        name = str(label) if len(str(label)) <= 16 else str(label)[:15] + "…"
        parts.append(f'<text x="{label_w - 8}" y="{y + 15}" text-anchor="end" class="lb">{esc(name)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 3}" width="{length:.1f}" height="16" rx="4" fill="{BLUE}"/>')
        parts.append(f'<text x="{label_w + length + 6:.1f}" y="{y + 15}" class="vl">{esc(text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ----------------------------------------------------------
# Sections
# ----------------------------------------------------------

def _table(frame: pd.DataFrame, columns: list[tuple[str, str, str]]) -> str:
    """columns: (key, header, kind) where kind is text / money / pct / count / change."""
    head = "".join(f'<th class="{"l" if kind == "text" else ""}">{esc(h)}</th>' for _, h, kind in columns)
    rows = []
    for _, r in frame.iterrows():
        cells = []
        for key, _, kind in columns:
            v = r.get(key)
            if kind == "text":
                cells.append(f'<td class="l">{esc(v)}</td>')
            elif kind == "change":
                cells.append(f'<td class="{"good" if (v or 0) > 0 else "bad" if (v or 0) < 0 else ""}">'
                             + ("—" if v is None or pd.isna(v) else f"{v * 100:+.1f}%") + "</td>")
            else:
                cells.append(f"<td>{_fmt(v, kind)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _kpis(cur, prev, period) -> str:
    now = metrics.kpis(cur)
    before = metrics.kpis(prev) if prev is not None and not prev.empty else {}
    keys = [k for k in ("revenue", "profit", "margin", "orders", "aov", "customers", "units", "discount") if k in now]
    tiles = []
    for key in keys:
        k = now[key]
        tiles.append(
            f'<div class="kpi"><div class="kl">{esc(k.label)}</div><div class="kv">{_fmt(k.value, k.fmt)}</div>'
            f'<div class="kf">{_delta(metrics.change(k, before.get(key)), k.higher_is_better, k.kind)}'
            f'<span class="p">{esc(period) if before else ""}</span></div></div>'
        )
    return f'<div class="kpis">{"".join(tiles)}</div>'


def _items(items) -> str:
    marks = {"good": "▲", "bad": "▼", "warn": "!", "info": "•"}
    return "<ul class='items'>" + "".join(
        f'<li><span class="mk {i.get("tone", "info")}">{marks.get(i.get("tone"), "•")}</span>'
        f'<div><b>{esc(i["title"])}</b>' + (f'<div class="sub">{esc(i["body"])}</div>' if i.get("body") else "")
        + "</div></li>" for i in items) + "</ul>"


def _breakdown(cur, dim) -> str:
    table = metrics.breakdown(cur, dim).head(8)
    label = FIELD_BY_KEY[dim].label
    notes = [pct(m) + " margin" for m in table["margin"]] if "margin" in table else None
    cols = [(dim, label, "text"), ("revenue", "Revenue", "money")]
    if "profit" in table:
        cols += [("profit", "Profit", "money"), ("margin", "Margin", "pct")]
    cols += [("share", "Share", "pct")]
    return (f'<section class="card half"><h3>Revenue by {esc(label.lower())}</h3>'
            + bar_chart(table[dim].tolist(), table["revenue"].tolist(), notes) + _table(table, cols) + "</section>")


def _forecast(result: forecasting.Result) -> str:
    f = result.forecast
    frame = f.frame().reset_index(names="period")
    chosen = result.comparison.set_index("model").loc[result.chosen]
    error = (f"{chosen['mape']:.1%} average error in back-tests" if chosen["mape"] is not None and pd.notna(chosen["mape"])
             else f"MASE {chosen['mase']:.2f} in back-tests")
    rows = "".join(f"<tr><td class='l'>{r.period:%b %Y}</td><td>{money(r.forecast)}</td>"
                   f"<td>{money(r.lo80)} – {money(r.hi80)}</td></tr>" for r in frame.itertuples())
    return (f'<section class="card"><h3>Revenue forecast, next {result.horizon} months</h3>'
            f'<div class="sub">{money(f.mean.sum())} in total (likely {money(f.lo80.sum())} – {money(f.hi80.sum())}). '
            f'Model: {esc(result.chosen)}, picked by back-testing; {esc(error)}.</div>'
            f'<table><thead><tr><th class="l">Month</th><th>Forecast</th><th>80% range</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></section>')


# ----------------------------------------------------------
# Whole document
# ----------------------------------------------------------

CSS = f"""
*{{box-sizing:border-box}} body{{margin:0;background:{T['canvas']};color:{T['text']};
font:14px/1.5 Inter,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.page{{max-width:980px;margin:0 auto;padding:32px 28px 48px}}
header{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:22px}}
.brand{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px}} .logo svg{{width:28px;height:28px;display:block}}
h1{{font-size:26px;letter-spacing:-.02em;margin:14px 0 4px}} h3{{font-size:15px;margin:0 0 10px}}
.meta{{color:{T['text_2']};font-size:13px}} .meta b{{color:{T['text']}}}
.print{{border:1px solid {T['border_strong']};background:{T['surface']};border-radius:8px;padding:8px 14px;
font:600 13px Inter,Arial,sans-serif;cursor:pointer;color:{T['text']}}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}}
.kpi,.card{{background:{T['surface']};border:1px solid {T['border']};border-radius:12px;padding:14px 16px;break-inside:avoid}}
.kl{{color:{T['text_2']};font-size:12.5px}} .kv{{font-size:24px;font-weight:700;letter-spacing:-.02em;margin:2px 0 4px}}
.kf{{display:flex;gap:8px;align-items:center;font-size:12px}} .p{{color:{T['text_3']}}}
.d{{font-weight:600;font-size:12px}} .good{{color:{T['good']}}} .bad{{color:{T['bad']}}} .flat{{color:{T['text_3']}}}
.card{{margin-bottom:14px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .grid .card{{margin-bottom:0}}
.sub{{color:{T['text_2']};font-size:12.5px;margin-bottom:8px}}
.ax{{font-size:10.5px;fill:{T['text_3']}}} .lb{{font-size:11.5px;fill:{T['text_2']}}} .vl{{font-size:11px;fill:{T['text_2']}}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px;font-variant-numeric:tabular-nums}}
th{{text-align:right;color:{T['text_3']};font-weight:600;border-bottom:1px solid {T['border']};padding:6px 8px}}
td{{text-align:right;border-bottom:1px solid {T['grid']};padding:6px 8px}} .l{{text-align:left}}
.items{{list-style:none;margin:0;padding:0}} .items li{{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid {T['grid']}}}
.items li:last-child{{border-bottom:0}} .mk{{width:20px;text-align:center;font-weight:700}}
.mk.good{{color:{T['good']}}} .mk.bad{{color:{T['bad']}}} .mk.warn{{color:{T['warn']}}} .mk.info{{color:{T['text_3']}}}
.legend{{display:flex;gap:16px;font-size:12px;color:{T['text_2']};margin-bottom:6px}}
.legend i{{display:inline-block;width:16px;height:0;vertical-align:middle;margin-right:6px}}
footer{{margin-top:22px;color:{T['text_3']};font-size:11.5px}}
@media (max-width:720px){{.kpis{{grid-template-columns:repeat(2,1fr)}} .grid{{grid-template-columns:1fr}}}}
@page{{size:A4;margin:12mm}}
@media print{{body{{background:#fff}} .page{{padding:0 3px;max-width:none}} .print{{display:none}}}}
"""


def build(ctx, selections: dict, forecast: forecasting.Result | None = None,
          alerts: pd.DataFrame | None = None) -> str:
    """The report for a page context and the dimension filters it was made with."""
    cur, prev, window, dataset = ctx.cur, ctx.prev, ctx.window, ctx.dataset
    period = window.compare_short or ""
    chosen = {k: v for k, v in selections.items() if v}
    filters_text = "; ".join(f"{FIELD_BY_KEY[k].label}: {', '.join(map(str, v))}" for k, v in chosen.items()) or "None"

    current = metrics.series(cur, "revenue", "Month")
    compared = (metrics.comparison_series(prev, current, window, "revenue", "Month")
                if prev is not None and not prev.empty else None)
    legend = (f'<div class="legend"><span><i style="border-top:2.5px solid {T["accent"]}"></i>Revenue</span>'
              + (f'<span><i style="border-top:2px dashed {T["text_3"]}"></i>Comparison period</span>'
                 if compared is not None else "") + "</div>")

    items = anomalies.as_items(alerts, limit=3) if alerts is not None and not alerts.empty else []
    items += insights.highlights(cur, prev, period, limit=6 - len(items))

    breakdowns = [d for d in ("category", "region", "segment") if d in cur][:2]
    sections = [
        _kpis(cur, prev, period),
        f'<section class="card"><h3>Revenue trend</h3>{legend}{line_chart(current, compared)}</section>',
    ]
    if items:
        sections.append(f'<section class="card"><h3>Alerts and changes</h3>{_items(items)}</section>')
    if breakdowns:
        sections.append('<div class="grid">' + "".join(_breakdown(cur, d) for d in breakdowns) + "</div><br>")
    mover_dim = next((d for d in ("sub_category", "category", "region", "product") if d in cur), None)
    if mover_dim and prev is not None and not prev.empty:
        movers = metrics.top_movers(cur, prev, mover_dim, "revenue", n=10)
        sections.append(
            f'<section class="card"><h3>Top movers by {esc(FIELD_BY_KEY[mover_dim].label.lower())}</h3>'
            + _table(movers, [(mover_dim, FIELD_BY_KEY[mover_dim].label, "text"), ("current", "Revenue", "money"),
                              ("previous", "Comparison", "money"), ("change", "Change", "money"),
                              ("change_pct", "Change %", "change")]) + "</section>")
    if forecast is not None:
        sections.append(_forecast(forecast))

    generated = datetime.now()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>InsightSphere report · {esc(dataset.name)}</title><style>{CSS}</style></head>
<body><div class="page">
<header><div><div class="brand"><span class="logo">{LOGO}</span>InsightSphere</div>
<h1>Sales report</h1>
<div class="meta"><b>{esc(dataset.name)}</b> · {esc(window.label)}{" · " + esc(period) if period else ""}<br>
Filters: {esc(filters_text)} · Generated {generated:%b %d, %Y %H:%M}</div></div>
<button class="print" onclick="window.print()">Print or save as PDF</button></header>
{"".join(sections)}
<footer>Figures are computed from {esc(dataset.name)} ({len(dataset.df):,} rows after cleaning).
Changes compare the period above with {esc(window.compare.lower()) if window.prev_start is not None else "no earlier period"}.
Forecast ranges are 80% prediction intervals. Generated by InsightSphere.</footer>
</div></body></html>"""


def file_name(dataset_name: str) -> str:
    stem = "".join(c if c.isalnum() or c in "-_ " else "_" for c in dataset_name.rsplit(".", 1)[0]).strip()
    return f"InsightSphere report - {stem or 'data'} - {datetime.now():%Y-%m-%d}.html"

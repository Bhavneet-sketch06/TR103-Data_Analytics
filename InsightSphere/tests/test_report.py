"""The downloadable report: complete, self-contained, and safe with any data."""

import pandas as pd

from core import anomalies, filters, forecasting, ingest
from ui import report
from ui.shell import PageContext


def context(df: pd.DataFrame, dataset) -> PageContext:
    w = filters.compute_window("Last 12 months", "Same period last year", df["order_date"].min(), df["order_date"].max())
    cur = filters.slice_window(df, w.start, w.end)
    prev = filters.slice_window(df, w.prev_start, w.prev_end) if w.prev_start is not None else None
    return PageContext(dataset=dataset, df=df, cur=cur, prev=prev, hist=df[df["order_date"] <= w.end], window=w)


def test_report_has_every_section_and_no_external_files():
    ds = ingest.load_sample()
    ctx = context(ds.df, ds)
    html = report.build(ctx, {"region": []}, forecast=forecasting.run(ds.df, "revenue", "Month", 6),
                        alerts=anomalies.detect(ctx.hist, ctx.window.start, ctx.window.end))
    for text in ("Sales report", "$733.2K", "Revenue trend", "Alerts and changes", "Revenue by category",
                 "Revenue by region", "Top movers", "Revenue forecast, next 6 months", "Technology margin"):
        assert text in html, text
    # Self-contained: nothing is fetched from anywhere when the file is opened.
    assert "<script src" not in html and "<link" not in html
    assert 'src="http' not in html and "url(http" not in html


def test_text_from_the_file_is_escaped():
    ds = ingest.load_sample()
    df = ds.df.copy()
    df["category"] = df["category"].replace({"Furniture": "<script>alert(1)</script>"})
    html = report.build(context(df, ds), {"category": ["<script>alert(1)</script>"]})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_minimal_data_still_makes_a_report():
    from pathlib import Path
    from core.schema import suggest_mapping
    data = (Path(__file__).parent / "fixtures" / "minimal.csv").read_bytes()
    cleaned, _ = ingest.read_and_clean(data, "minimal.csv")
    ds = ingest.load_dataset(data, "minimal.csv", suggest_mapping(cleaned.columns), is_sample=False)
    html = report.build(context(ds.df, ds), {})
    assert "Revenue trend" in html and "Revenue by category" not in html


def test_file_name_is_safe():
    assert report.file_name("Q3/sales: final?.csv") == f"InsightSphere report - Q3_sales_ final_ - {pd.Timestamp.now():%Y-%m-%d}.html"

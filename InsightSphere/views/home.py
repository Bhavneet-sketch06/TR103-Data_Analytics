"""Home: the landing page. What InsightSphere is, a live preview, and where to start."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import filters, metrics, state
from ui import charts, shell, upload
from ui import components as ui

dataset = state.get_dataset()
df = dataset.df

# A landing page reads as a website: no app sidebar, a narrower column.
st.html("""<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none !important; }
[data-testid="stMainBlockContainer"] { max-width: 1220px; padding-top: 1.25rem; }
</style>""")


def _scroll_to_upload() -> None:
    st.session_state["_home-scroll"] = True


# ----------------------------------------------------------
# Top bar
# ----------------------------------------------------------

logo_svg = shell.LOGO.read_text(encoding="utf-8")
left, right = st.columns([1, 1], vertical_alignment="center")
with left:
    ui.render(f'<div class="is-brand"><span class="is-brand-logo">{logo_svg}</span>InsightSphere</div>')
with right:
    with st.container(horizontal=True, horizontal_alignment="right", gap="small", vertical_alignment="center"):
        if st.button("Open dashboard", icon=":material/space_dashboard:", type="tertiary", key="nav-open"):
            st.switch_page("views/overview.py")
        shell.theme_toggle()

# ----------------------------------------------------------
# Hero
# ----------------------------------------------------------

st.space("large")
text_col, preview_col = st.columns([1.05, 1], gap="large", vertical_alignment="center")

with text_col:
    ui.render(
        '<div class="is-hero">'
        f'<span class="is-hero-pill">{ui.icon("sparkles", 13)}Sales analytics from any CSV</span>'
        '<div class="is-hero-title" role="heading" aria-level="1">Your sales,<br>'
        '<span class="is-hero-accent">decoded.</span></div>'
        '<div class="is-hero-sub">Drop in a sales file and get a full dashboard in seconds: '
        'trends, products, customers and regions, with every number explained.</div>'
        "</div>"
    )
    with st.container(key="hero-cta", horizontal=True, gap="small"):
        if dataset.is_sample:
            st.button("Upload your data", type="primary", icon=":material/upload:", on_click=_scroll_to_upload,
                      key="cta-upload")
            if st.button("Explore sample data", icon=":material/arrow_forward:", key="cta-sample"):
                st.switch_page("views/overview.py")
        else:
            if st.button(f"Continue with {dataset.name}", type="primary", icon=":material/arrow_forward:",
                         key="cta-continue"):
                st.switch_page("views/overview.py")
            st.button("Upload a new file", icon=":material/upload:", on_click=_scroll_to_upload, key="cta-new")
    ui.render(f'<div class="is-hero-note">{ui.icon("lock", 13)}Your file is processed on this machine. '
              "Nothing is sent anywhere.</div>")


def _trend_svg(current: pd.Series, previous: pd.Series | None, width: int = 520, height: int = 150) -> str:
    """Current period as a solid accent line with a soft area, the comparison dotted."""
    values = list(current.values) + (list(previous.dropna().values) if previous is not None else [])
    lo, hi = 0.0, max(values) if values else 1.0
    pad = 6

    def points(series):
        step = (width - 2 * pad) / max(len(series) - 1, 1)
        return [(pad + i * step, height - pad - (v - lo) / ((hi - lo) or 1) * (height - 2 * pad))
                for i, v in enumerate(series)]

    cur = points(list(current.values))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in cur)
    area = f"{cur[0][0]:.1f},{height} {line} {cur[-1][0]:.1f},{height}"
    svg = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none" '
           'aria-hidden="true">']
    for frac in (0.25, 0.5, 0.75):
        y = pad + frac * (height - 2 * pad)
        svg.append(f'<line x1="0" x2="{width}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:var(--is-grid)" '
                   'stroke-width="1"/>')
    svg.append(f'<polygon points="{area}" style="fill:var(--is-accent-soft)"/>')
    if previous is not None and previous.notna().sum() > 1:
        prev_line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points(list(previous.fillna(0).values)))
        svg.append(f'<polyline points="{prev_line}" style="fill:none;stroke:var(--is-text-3)" stroke-width="1.6" '
                   'stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>')
    svg.append(f'<polyline points="{line}" style="fill:none;stroke:var(--is-accent)" stroke-width="2.4" '
               'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>')
    svg.append("</svg>")
    return "".join(svg)


with preview_col:
    window = filters.compute_window("Last 12 months", "Same period last year",
                                    df["order_date"].min(), df["order_date"].max())
    cur = filters.slice_window(df, window.start, window.end)
    prev = filters.slice_window(df, window.prev_start, window.prev_end) if window.prev_start is not None else None
    now = metrics.kpis(cur)
    before = metrics.kpis(prev) if prev is not None and not prev.empty else {}
    tiles = []
    for key in [k for k in ("revenue", "profit", "orders", "customers") if k in now][:3]:
        k = now[key]
        value = charts.money(k.value) if k.fmt == "money" else f"{k.value:,.0f}"
        badge = ui.delta_badge(metrics.change(k, before.get(key)), higher_is_better=k.higher_is_better) \
            if key in before else ""
        tiles.append(f'<div class="is-preview-tile"><div class="is-preview-label">{ui.esc(k.label)}</div>'
                     f'<div class="is-preview-value">{ui.esc(value)}</div>{badge}</div>')
    current = metrics.series(cur, "revenue")
    compared = metrics.comparison_series(prev, current, window) if prev is not None and not prev.empty else None
    first, last = current.index[0], current.index[-1]
    ui.render(
        '<div class="is-preview">'
        '<div class="is-preview-head"><span class="is-live-dot"></span>Live preview'
        f'<span class="is-preview-src">{ui.esc(dataset.name)}</span></div>'
        f'<div class="is-preview-tiles">{"".join(tiles)}</div>'
        '<div class="is-preview-chart-head"><span>Revenue, last 12 months</span>'
        '<span class="is-preview-legend"><i class="solid"></i>This year'
        + ('<i class="dotted"></i>Last year' if compared is not None else "") + "</span></div>"
        + _trend_svg(current, compared)
        + f'<div class="is-preview-axis"><span>{first:%b %Y}</span><span>{last:%b %Y}</span></div>'
        "</div>"
    )

# ----------------------------------------------------------
# Upload
# ----------------------------------------------------------

st.space(72)
ui.render('<div class="is-home-eyebrow">Get started</div>'
          '<div class="is-home-title">Bring your own data</div>'
          '<div class="is-home-sub">Any sales export works. Columns are matched for you, and you confirm '
          "the match before anything is analysed.</div>")
st.space("small")
with ui.card("home-upload"):
    uploaded = upload.file_picker("home")
    if uploaded is None:
        ui.render(
            '<div class="is-checks">'
            f'<span>{ui.icon("check", 14)}Only a date and a revenue column are required</span>'
            f'<span>{ui.icon("check", 14)}Columns like “Net Sales” or “Invoice Date” are recognised</span>'
            f'<span>{ui.icon("check", 14)}Missing values are never guessed</span>'
            "</div>"
        )
if uploaded is not None:
    st.space("small")
    upload.mapping_step(uploaded, "home", on_done=lambda _: st.switch_page("views/overview.py"))

if st.session_state.pop("_home-scroll", False):
    components.html(
        "<script>const el = window.parent.document.querySelector('.st-key-card-home-upload');"
        "if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'});</script>",
        height=0,
    )

# ----------------------------------------------------------
# What you get
# ----------------------------------------------------------

st.space(72)
ui.render('<div class="is-home-eyebrow">What you get</div>'
          '<div class="is-home-title">One file, six views of your business</div>')
st.space("small")

FEATURES = [
    ("layout", "Overview", "Headline KPIs, the trend against last year and what changed.", "views/overview.py", ""),
    ("tag", "Sales", "Product mix, revenue concentration, seasonality and loss-makers.", "views/sales.py", ""),
    ("users", "Customers", "Segments, retention by cohort, new vs returning revenue.", "views/customers.py", ""),
    ("globe", "Regions", "A US map, state rankings and a drill-down to every city.", "views/regions.py", ""),
    ("truck", "Operations", "How discounts hit margin, and how fast orders ship.", "views/operations.py", ""),
    ("sparkles", "Forecast and AI", "Forecasts, anomaly alerts and an assistant that answers questions.",
     None, "Coming soon"),
]
for row in (FEATURES[:3], FEATURES[3:]):
    for col, (icon_name, title, body, page, tag) in zip(st.columns(3, gap="medium"), row):
        with col:
            with st.container(key=f"card-feature-{title.split()[0].lower()}"):
                ui.render(
                    f'<div class="is-feature"><div class="is-feature-icon">{ui.icon(icon_name, 18)}</div>'
                    f'<div class="is-feature-title">{ui.esc(title)}'
                    + (f' {ui.pill(tag, "neutral")}' if tag else "")
                    + f'</div><div class="is-feature-body">{ui.esc(body)}</div></div>'
                )
                if page:
                    st.page_link(page, label=f"Open {title}", icon=":material/arrow_forward:")

# ----------------------------------------------------------
# Footer
# ----------------------------------------------------------

st.space("large")
ui.render(
    '<div class="is-footer"><span>InsightSphere · built with Streamlit, pandas and Plotly</span>'
    '<a href="https://github.com/Bhavneet-sketch06/TR103-Data_Analytics" target="_blank" rel="noopener">'
    "View on GitHub</a></div>"
)

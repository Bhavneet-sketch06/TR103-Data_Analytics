"""Home: the landing page. What InsightSphere is, what it looks like, and where to start."""

from __future__ import annotations

import streamlit as st

from core import state
from ui import charts, shell, upload
from ui import components as ui

dataset = state.get_dataset()        # None until a file is uploaded (or the sample is chosen)

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
        if dataset is None:
            st.button("Upload your data", type="primary", icon=":material/upload:", on_click=_scroll_to_upload,
                      key="cta-upload")
            if st.button("Try sample data", icon=":material/arrow_forward:", key="cta-sample"):
                state.use_sample()
                st.switch_page("views/overview.py")
        else:
            if st.button(f"Continue with {dataset.name}", type="primary", icon=":material/arrow_forward:",
                         key="cta-continue"):
                st.switch_page("views/overview.py")
            st.button("Upload a new file", icon=":material/upload:", on_click=_scroll_to_upload, key="cta-new")
    ui.render(f'<div class="is-hero-note">{ui.icon("lock", 13)}Your file is processed on this machine. '
              "Nothing is sent anywhere.</div>")


# The hero image is fixed: a real screenshot of the Overview with the bundled
# sample dataset (static/hero-*.png), shown whatever data is loaded. It follows
# the theme switch, which reruns the page with the new mode.
with preview_col:
    mode = charts.current_mode()
    ui.render(
        '<figure class="is-hero-shot">'
        '<div class="is-hero-chrome"><span></span><span></span><span></span>'
        '<div class="is-hero-url">insightsphere · Overview</div></div>'
        f'<img src="app/static/hero-{mode}.png" alt="InsightSphere Overview page: KPI tiles for revenue, profit, '
        'margin, orders and order value, and a monthly revenue trend against last year." width="1280" height="800">'
        "</figure>"
        '<div class="is-hero-caption">Example: the Overview with the bundled sample dataset</div>'
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
    with st.container(key="hidden-home-scroll"):
        # Smooth scroll, with an instant fallback for tabs that skip the animation.
        st.html("""<script>
(() => {
  const el = document.querySelector('.st-key-card-home-upload');
  if (!el) return;
  const start = el.getBoundingClientRect().top;
  el.scrollIntoView({behavior: 'smooth', block: 'center'});
  setTimeout(() => {
    if (Math.abs(el.getBoundingClientRect().top - start) < 2) el.scrollIntoView({block: 'center'});
  }, 600);
})();
</script>""", unsafe_allow_javascript=True)

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
    ("sparkles", "Forecast", "Back-tested forecasts with ranges, a what-if simulator and saved runs.",
     "views/forecast.py", ""),
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

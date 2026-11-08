import streamlit as st
import pandas as pd
import plotly.express as px

from pathlib import Path
from utils.dashboard_components import (
    load_css,
    dashboard_header,
    metric_card,
    section_title
)


# ----------------------------------------
# Page Configuration  (unchanged)
# ----------------------------------------

st.set_page_config(
    page_title="Business Insights Dashboard",
    page_icon="📊",
    layout="wide"
)

# ----------------------------------------
# Load ACTIVE DATASET (uploaded dataset if present, else sample)
# ----------------------------------------

from utils.data_loader import get_active_dataset, has_columns

df, is_uploaded_dataset, active_label = get_active_dataset()

_REQUIRED_DASHBOARD_COLUMNS = [
    "Region", "Category", "Segment", "Order Date",
    "Sales", "Profit", "Order ID", "Customer ID", "Product Name",
]

_missing_dashboard_cols = [c for c in _REQUIRED_DASHBOARD_COLUMNS if c not in df.columns]

if _missing_dashboard_cols:
    st.warning(
        f"The Dashboard is unavailable for **{active_label}** because it does not contain "
        f"the following required column(s): {', '.join(_missing_dashboard_cols)}. "
        f"Upload a dataset with a Superstore-style sales schema, or return to Home to "
        f"switch datasets."
    )
    st.stop()
css_path = Path(__file__).parent.parent / "assets" / "style.css"
load_css(css_path)

# NEW: dashboard-only stylesheet, additive to your existing style.css.
dashboard_css_path = Path(__file__).parent / "dashboard.css"
if dashboard_css_path.exists():
    st.markdown(f"<style>{dashboard_css_path.read_text()}</style>", unsafe_allow_html=True)
else:
    st.warning(f"Stylesheet not found at: {dashboard_css_path}")


# ==========================================================
# DASHBOARD HEADER
# ==========================================================
# Title/subtitle updated for the executive-overview redesign.
# Profile / notification / date-range chips are purely decorative —
# no functionality was attached to them before, so none is added now.

header_left, header_right = st.columns([3, 1.3])

with header_left:
    st.markdown(
        f"""
        <p class="db-header-title">InsightSphere Dashboard</p>
        <p class="db-header-subtitle">Executive Overview • Real-Time Business Performance — {active_label}</p>
        """,
        unsafe_allow_html=True
    )

# with header_right:
#     # st.markdown(
#     #     """
#     #     <div class="db-header-actions">
#     #         <span class="db-header-icon-chip">👤</span>
#     #         <span class="db-header-icon-chip">🔔</span>
#     #         <span class="db-header-chip">📅 Date range</span>
#     #     </div>
#     #     """,
#     #     unsafe_allow_html=True
#     # )

st.markdown('<div class="db-section-spacer"></div>', unsafe_allow_html=True)


# ==========================================================
# FILTER BAR  (existing filter logic — unchanged)
# ==========================================================
# Wrapped in a real bordered container purely for presentation,
# so it reads as one floating filter card. The widgets, variable
# names, and filtering logic below are identical to the original.

filter_card = st.container(border=True)

with filter_card:
    # Hidden marker so dashboard.css can target this exact container.
    st.markdown('<span class="db-filter-marker"></span>', unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns([2, 2, 2, 2, 1])

    with filter_col1:
        region = st.selectbox(
            "🌍 Region",
            ["All"] + sorted(df["Region"].unique().tolist())
        )

    with filter_col2:
        category = st.selectbox(
            "📦 Category",
            ["All"] + sorted(df["Category"].unique().tolist())
        )

    with filter_col3:
        segment = st.selectbox(
            "👤 Segment",
            ["All"] + sorted(df["Segment"].unique().tolist())
        )

    with filter_col4:
        year = st.selectbox(
            "📅 Year",
            ["All"] + sorted(df["Order Date"].astype(str).str[:4].unique().tolist())
        )

    with filter_col5:

        st.write("")
        st.write("")

        reset = st.button("🔄 Reset")

st.markdown('<div class="db-section-spacer"></div>', unsafe_allow_html=True)

# ==========================================================
# APPLY FILTERS  (unchanged)
# ==========================================================

filtered_df = df.copy()

if region != "All":
    filtered_df = filtered_df[filtered_df["Region"] == region]

if category != "All":
    filtered_df = filtered_df[filtered_df["Category"] == category]

if segment != "All":
    filtered_df = filtered_df[filtered_df["Segment"] == segment]

if year != "All":
    filtered_df = filtered_df[
        filtered_df["Order Date"].astype(str).str[:4] == year
    ]


# ==========================================================
# PREPARE MONTHLY DATA
# ==========================================================
# NOTE: This block is moved earlier than in the original file
# (it used to run after the KPI cards). The computation itself —
# Order Date conversion, Month-Year extraction, and monthly Sales
# grouping — is byte-for-byte identical, just relocated so the KPI
# cards below can use it for sparklines/growth indicators.

filtered_df["Order Date"] = pd.to_datetime(filtered_df["Order Date"])

filtered_df["Month-Year"] = filtered_df["Order Date"].dt.to_period("M").astype(str)

monthly_sales = (
    filtered_df
    .groupby("Month-Year")["Sales"]
    .sum()
    .reset_index()
)

# NEW (additive): equivalent monthly groupings for Profit / Orders / Customers,
# used only to power the KPI growth % and sparklines. Same aggregation
# pattern as monthly_sales above — no change to any existing dataframe.
monthly_profit = (
    filtered_df
    .groupby("Month-Year")["Profit"]
    .sum()
    .reset_index()
)

monthly_orders = (
    filtered_df
    .groupby("Month-Year")["Order ID"]
    .nunique()
    .reset_index()
)

monthly_customers = (
    filtered_df
    .groupby("Month-Year")["Customer ID"]
    .nunique()
    .reset_index()
)


# ==========================================================
# KPI CALCULATIONS  (unchanged)
# ==========================================================

sales = filtered_df["Sales"].sum()

profit = filtered_df["Profit"].sum()

orders = filtered_df["Order ID"].nunique()

customers = filtered_df["Customer ID"].nunique()


# ----------------------------------------
# NEW: small helpers for the KPI cards
# (growth %, sparkline SVG) — presentation only.
# ----------------------------------------

def month_over_month_growth(monthly_df: pd.DataFrame, value_col: str) -> float:
    """Percent change between the last two months in a monthly series."""
    values = monthly_df[value_col].tolist()
    if len(values) < 2 or values[-2] == 0:
        return 0.0
    return ((values[-1] - values[-2]) / values[-2]) * 100


def sparkline_svg(values, width: int = 92, height: int = 30, color: str = "#2F6FED") -> str:
    """Builds a tiny inline SVG line sparkline from a list of numeric values."""
    if not values or len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'

    min_v, max_v = min(values), max(values)
    span = (max_v - min_v) or 1
    step = width / (len(values) - 1)

    points = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - min_v) / span) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")

    points_str = " ".join(points)

    return f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        <polyline fill="none" stroke="{color}" stroke-width="2.4"
                  stroke-linecap="round" stroke-linejoin="round"
                  points="{points_str}" />
    </svg>
    """


def growth_badge(growth_pct: float) -> str:
    if growth_pct > 0.05:
        return f'<span class="db-kpi-growth db-kpi-growth-up">▲ {growth_pct:.1f}%</span>'
    elif growth_pct < -0.05:
        return f'<span class="db-kpi-growth db-kpi-growth-down">▼ {abs(growth_pct):.1f}%</span>'
    else:
        return '<span class="db-kpi-growth db-kpi-growth-flat">— 0.0%</span>'


def kpi_card_html(icon: str, label: str, value: str, growth_pct: float, spark_values) -> str:
    return f"""
    <div class="db-kpi-card">
        <div class="db-kpi-top-row">
            <span class="db-kpi-label">{icon} {label}</span>
            {growth_badge(growth_pct)}
        </div>
        <div class="db-kpi-value">{value}</div>
        <div class="db-kpi-spark">{sparkline_svg(spark_values)}</div>
    </div>
    """


sales_growth = month_over_month_growth(monthly_sales, "Sales")
profit_growth = month_over_month_growth(monthly_profit, "Profit")
orders_growth = month_over_month_growth(monthly_orders, "Order ID")
customers_growth = month_over_month_growth(monthly_customers, "Customer ID")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(
        kpi_card_html("💰", "Total Revenue", f"${sales:,.0f}", sales_growth, monthly_sales["Sales"].tolist()),
        unsafe_allow_html=True
    )

with kpi2:
    st.markdown(
        kpi_card_html("📈", "Total Profit", f"${profit:,.0f}", profit_growth, monthly_profit["Profit"].tolist()),
        unsafe_allow_html=True
    )

with kpi3:
    st.markdown(
        kpi_card_html("📦", "Orders", f"{orders:,}", orders_growth, monthly_orders["Order ID"].tolist()),
        unsafe_allow_html=True
    )

with kpi4:
    st.markdown(
        kpi_card_html("👥", "Customers", f"{customers:,}", customers_growth, monthly_customers["Customer ID"].tolist()),
        unsafe_allow_html=True
    )

st.markdown('<div class="db-section-spacer"></div>', unsafe_allow_html=True)


# ==========================================================
# PREPARE DATA FOR CHARTS / SUMMARY  (unchanged)
# ==========================================================

category_sales = (
    filtered_df
    .groupby("Category")["Sales"]
    .sum()
    .reset_index()
)

region_sales = (
    filtered_df
    .groupby("Region")["Sales"]
    .sum()
    .reset_index()
)

top_products = (
    filtered_df
    .groupby("Product Name")["Sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

top_products["Product Name"] = top_products["Product Name"].apply(
    lambda x: x[:28] + "..." if len(x) > 28 else x
)

# NEW (additive): one small grouping not present before, needed only
# for the "largest segment share" Business Highlight below.
segment_sales = (
    filtered_df
    .groupby("Segment")["Sales"]
    .sum()
    .reset_index()
)

profit_margin = (profit / sales * 100) if sales else 0.0


# ==========================================================
# BUSINESS HIGHLIGHTS  (dynamically generated from the data above)
# ==========================================================

highlights = []

if not region_sales.empty:
    top_region_row = region_sales.sort_values("Sales", ascending=False).iloc[0]
    highlights.append(
        f"Revenue is strongest in the <strong>{top_region_row['Region']}</strong> region, "
        f"contributing ${top_region_row['Sales']:,.0f} in sales."
    )

if not category_sales.empty:
    top_category_row = category_sales.sort_values("Sales", ascending=False).iloc[0]
    highlights.append(
        f"<strong>{top_category_row['Category']}</strong> remains the highest-performing category."
    )

if not segment_sales.empty:
    top_segment_row = segment_sales.sort_values("Sales", ascending=False).iloc[0]
    total_segment_sales = segment_sales["Sales"].sum()
    segment_share = (top_segment_row["Sales"] / total_segment_sales * 100) if total_segment_sales else 0
    highlights.append(
        f"The <strong>{top_segment_row['Segment']}</strong> segment contributes the largest "
        f"share of sales at {segment_share:.0f}%."
    )

if profit_margin >= 15:
    highlights.append(f"Profit margin remains healthy at <strong>{profit_margin:.1f}%</strong>.")
else:
    highlights.append(
        f"Profit margin is currently <strong>{profit_margin:.1f}%</strong>, "
        f"below the 15% healthy benchmark."
    )

if not top_products.empty:
    top_product_name = top_products.iloc[0]["Product Name"]
    highlights.append(f"<strong>{top_product_name}</strong> continues to be the top-selling product.")

# Keep the list focused (spec calls for 4-5 highlights)
highlights = highlights[:5]

highlight_items_html = "".join(
    f'<li><span class="db-highlight-dot"></span><span>{item}</span></li>' for item in highlights
)


# ==========================================================
# BUSINESS HIGHLIGHTS + BUSINESS SNAPSHOT ROW
# ==========================================================

highlights_col, snapshot_col = st.columns([1, 1.6])

with highlights_col:
    st.markdown(
        f"""
        <div class="db-card">
            <p class="db-card-title">Business Highlights</p>
            <ul class="db-highlight-list">{highlight_items_html}</ul>
        </div>
        """,
        unsafe_allow_html=True
    )

with snapshot_col:
    snapshot_card = st.container(border=True)
    with snapshot_card:
        st.markdown('<p class="db-card-title">Business Snapshot</p>', unsafe_allow_html=True)

        chart1, chart2 = st.columns(2)

        with chart1:
            st.markdown('<p class="db-chart-subtitle">Monthly Revenue Trend</p>', unsafe_allow_html=True)

            fig_sales = px.line(
                monthly_sales,
                x="Month-Year",
                y="Sales",
                markers=True,
                title=""
            )

            fig_sales.update_traces(
                mode="lines",
                line=dict(
                    width=4,
                    shape="spline",
                    smoothing=0.5
                )
            )

            fig_sales.update_layout(
                template="plotly_white",
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="",
                yaxis_title="Sales ($)"
            )

            st.plotly_chart(
                fig_sales,
                use_container_width=True
            )

        with chart2:
            st.markdown('<p class="db-chart-subtitle">Revenue by Category</p>', unsafe_allow_html=True)

            fig_category = px.bar(
                category_sales,
                x="Category",
                y="Sales",
                text_auto="$,.2s",
                color="Category"
            )

            fig_category.update_layout(
                template="plotly_white",
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                xaxis_title="",
                yaxis_title="Sales ($)"
            )

            st.plotly_chart(
                fig_category,
                use_container_width=True
            )

st.markdown('<div class="db-section-spacer"></div>', unsafe_allow_html=True)


# ==========================================================
# QUICK PERFORMANCE SUMMARY
# ==========================================================
# All values reuse the dataframes already computed above —
# no new dataset loads, no duplicate calculations.

top_region_name = (
    region_sales.sort_values("Sales", ascending=False).iloc[0]["Region"]
    if not region_sales.empty else "-"
)

best_category_name = (
    category_sales.sort_values("Sales", ascending=False).iloc[0]["Category"]
    if not category_sales.empty else "-"
)

best_product_name = (
    top_products.iloc[0]["Product Name"] if not top_products.empty else "-"
)

st.markdown('<p class="db-card-title">Quick Performance Summary</p>', unsafe_allow_html=True)

summary_specs = [
    ("Top Region", top_region_name),
    ("Best Category", best_category_name),
    ("Best Product", best_product_name),
    ("Profit Margin", f"{profit_margin:.1f}%"),
]

summary_cols = st.columns(4)
for col, (label, value) in zip(summary_cols, summary_specs):
    with col:
        st.markdown(
            f"""
            <div class="db-summary-card">
                <div class="db-summary-label">{label}</div>
                <div class="db-summary-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
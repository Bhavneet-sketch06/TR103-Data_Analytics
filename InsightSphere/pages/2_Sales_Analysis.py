import streamlit as st
import pandas as pd
import plotly.express as px
from utils.analysis_components import (
    section_header,
    insight_card
)

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Sales Analysis",
    page_icon="📈",
    layout="wide"
)

# ==========================================================
# LOAD ACTIVE DATASET
# ==========================================================

from utils.data_loader import get_active_dataset

_REQUIRED_ANALYSIS_COLUMNS = [
    "Category", "Sub-Category", "Ship Mode", "Region", "State", "Segment",
    "Discount", "Profit", "Sales", "Order Date", "Ship Date",
    "Order ID", "Customer ID",
]

df, is_uploaded_dataset, active_label = get_active_dataset()

_missing_analysis_cols = [c for c in _REQUIRED_ANALYSIS_COLUMNS if c not in df.columns]

if _missing_analysis_cols:
    st.title("📈 Sales Analysis")
    st.warning(
        f"Sales Analysis is unavailable for **{active_label}** because it does not contain "
        f"the following column(s): {', '.join(_missing_analysis_cols)}. "
        f"This page requires a Superstore-style sales schema (Category, Sub-Category, "
        f"Region, State, Segment, Ship Mode, Order Date, Ship Date, Discount, Profit, Sales, "
        f"Order ID, Customer ID). General dataset info is still available from the Home page."
    )
    st.stop()

# Convert dates (safe -- both columns are confirmed present above)
df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
df["Ship Date"] = pd.to_datetime(df["Ship Date"], errors="coerce")

# Create Shipping Days column
df["Shipping_Days"] = (df["Ship Date"] - df["Order Date"]).dt.days

# ==========================================================
# PAGE TITLE
# ==========================================================

st.title("📈 Sales Analysis")

st.caption(
    "Dive deeper into profitability, customer behaviour and business performance through interactive analytics."
)

st.divider()

# ==========================================================
# BUSINESS ANALYTICS WORKSPACE
# ==========================================================

st.markdown("## Business Analytics Workspace")

st.caption(
    "Explore different aspects of business performance through dedicated analytical modules."
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Profitability",
        "Discount Analysis",
        "Customer Analysis",
        "Regional Analysis",
        "Shipping Analysis",
        "Business Summary"
    ]
)

with tab1:

    # ==========================================================
    # PROFITABILITY ANALYSIS
    # ==========================================================

    st.subheader("💰 Profitability Analysis")

    st.caption(
        "Analyze which categories and sub-categories generate the highest profit."
    )

    # ==========================================================
    # INTERACTIVE CONTROLS
    # ==========================================================

    filter_col1, filter_col2 = st.columns([2, 1])

    with filter_col1:

        selected_category = st.selectbox(
            "Select Category",
            ["All"] + sorted(df["Category"].unique().tolist())
        )

    with filter_col2:

        top_n = st.slider(
            "Top Sub-Categories",
            min_value=5,
            max_value=15,
            value=10
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================================
    # APPLY FILTER
    # ==========================================================

    filtered_df = df.copy()

    if selected_category != "All":

        filtered_df = filtered_df[
            filtered_df["Category"] == selected_category
        ]

    # ==========================================================
    # DATA PREPARATION
    # ==========================================================

    profit_category = (
        filtered_df
        .groupby("Category")["Profit"]
        .sum()
        .reset_index()
        .sort_values("Profit", ascending=False)
    )

    profit_subcategory = (
        filtered_df
        .groupby("Sub-Category")["Profit"]
        .sum()
        .reset_index()
        .sort_values("Profit", ascending=False)
        .head(top_n)
    )

    # ==========================================================
    # CHARTS
    # ==========================================================

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("#### Profit by Category")

        fig_category = px.bar(
            profit_category,
            x="Category",
            y="Profit",
            color="Category",
            text_auto="$,.2s",
            template="plotly_white"
        )

        fig_category.update_layout(
            height=420,
            showlegend=False,
            xaxis_title="",
            yaxis_title="Profit ($)"
        )

        fig_category.update_traces(
            textposition="outside"
        )

        st.plotly_chart(
            fig_category,
            use_container_width=True
        )

    with col2:

        st.markdown("#### Top Profitable Sub-Categories")

        fig_subcategory = px.bar(
            profit_subcategory,
            x="Profit",
            y="Sub-Category",
            orientation="h",
            color="Profit",
            text_auto="$,.2s",
            template="plotly_white"
        )

        fig_subcategory.update_layout(
            height=420,
            yaxis=dict(categoryorder="total ascending"),
            xaxis_title="Profit ($)",
            yaxis_title=""
        )

        fig_subcategory.update_traces(
            textposition="outside"
        )

        st.plotly_chart(
            fig_subcategory,
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================================
    # KPI HIGHLIGHTS
    # ==========================================================

    st.markdown("### 📊 Profitability Highlights")

    highest_category = profit_category.iloc[0]
    lowest_category = profit_category.iloc[-1]
    highest_subcategory = profit_subcategory.iloc[0]

    share = (
        highest_category["Profit"]
        /
        profit_category["Profit"].sum()
    ) * 100

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "🏆 Highest Category",
        highest_category["Category"],
        f"${highest_category['Profit']:,.0f}"
    )

    m2.metric(
        "⭐ Best Sub-Category",
        highest_subcategory["Sub-Category"],
        f"${highest_subcategory['Profit']:,.0f}"
    )

    m3.metric(
        "📉 Lowest Category",
        lowest_category["Category"],
        f"${lowest_category['Profit']:,.0f}"
    )

    m4.metric(
        "📌 Profit Concentration",
        f"{share:.1f}%",
        "Top Category"
    )

    with st.container(border=True):

        st.markdown("## 💡 Executive Takeaway")

        st.write(
            f"""
**{highest_category['Category']}** is currently the most profitable category,
contributing **{share:.1f}%** of the total category profit.

The strongest performing sub-category is **{highest_subcategory['Sub-Category']}**,
making it a suitable candidate for additional marketing and inventory investment.

On the other hand, **{lowest_category['Category']}** contributes the least profit.
Management should review pricing strategy, discount policies and operating costs
for this category to improve profitability.
"""
        )

with tab2:

    # ==========================================================
    # DISCOUNT ANALYSIS
    # ==========================================================

    st.subheader("🎯 Discount Impact Analysis")

    with st.expander("❓ What business question does this analysis answer?"):

        st.write("""
This analysis helps answer:

• Are higher discounts reducing our profits?

• Which discount levels are still profitable?

• Should the company continue offering large discounts?

Use the charts below to identify discount ranges that maximize profit while remaining attractive to customers.
""")

    st.caption(
        """
Understand how different discount percentages affect your company's profit.

This section helps managers identify whether giving larger discounts is increasing sales profitably or reducing overall earnings.
"""
    )

    # ==========================================================
    # DISCOUNT FILTER
    # ==========================================================

    st.info(
        """
### 💡 How to use this filter

Move the slider to analyze orders that fall within a specific discount percentage.

**Examples**

• **0%** → Customer received **no discount**

• **20%** → Customer received **20% discount**

• **50%** → Customer paid only half the original price

This helps you understand whether higher discounts are helping or hurting profits.
"""
    )

    discount_range = st.slider(
        "Choose Discount Percentage to Analyze",
        min_value=float(df["Discount"].min()),
        max_value=float(df["Discount"].max()),
        value=(
            float(df["Discount"].min()),
            float(df["Discount"].max())
        ),
        format="%.2f"
    )

    st.success(
        f"""
### Currently Analyzing

Orders with discounts between

**{discount_range[0]:.0%}** and **{discount_range[1]:.0%}**
"""
    )

    discount_df = df[
        (df["Discount"] >= discount_range[0]) &
        (df["Discount"] <= discount_range[1])
    ]

    st.markdown("### 📊 Discount Performance Dashboard")

    col1, col2 = st.columns(2)

    # ==========================================================
    # SCATTER CHART
    # ==========================================================

    with col1:

        st.markdown("#### 📈 How Discounts Affect Profit")

        st.caption(
            """
Each bubble represents one customer order.

• 📍 Higher bubbles = More Profit

• 📍 Lower bubbles = Lower Profit or Loss

• 🔵 Bubble Size = Sales Amount

• 🎨 Bubble Color = Product Category
"""
        )

        fig_discount = px.scatter(
            discount_df,
            x="Discount",
            y="Profit",
            color="Category",
            size="Sales",
            symbol="Segment",
            hover_data=[
                "Sub-Category",
                "Region"
            ],
            template="plotly_white"
        )

        fig_discount.update_layout(
            height=450,
            xaxis_title="Discount",
            yaxis_title="Profit ($)"
        )

        st.plotly_chart(
            fig_discount,
            use_container_width=True
        )

    # ==========================================================
    # LINE CHART
    # ==========================================================

    with col2:

        st.markdown("#### 📊 Average Profit at Different Discount Levels")

        st.caption(
            """
This chart shows how the average profit changes as the discount percentage increases.

It helps identify whether larger discounts are improving or reducing profitability.
"""
        )

        avg_profit = (
            discount_df
            .groupby("Discount")["Profit"]
            .mean()
            .reset_index()
        )

        fig_avg = px.line(
            avg_profit,
            x="Discount",
            y="Profit",
            markers=True,
            template="plotly_white"
        )

        fig_avg.update_traces(
            line=dict(width=4)
        )

        fig_avg.update_layout(
            height=450,
            xaxis_title="Discount",
            yaxis_title="Average Profit ($)"
        )

        st.plotly_chart(
            fig_avg,
            use_container_width=True
        )

    # ==========================================================
    # INSIGHTS
    # ==========================================================

    negative_orders = (discount_df["Profit"] < 0).sum()

    loss_percentage = (
        negative_orders /
        len(discount_df)
    ) * 100

    trend = (
        avg_profit["Profit"].iloc[-1]
        -
        avg_profit["Profit"].iloc[0]
    )

    st.info(
        f"""
📌 **Key Insight**

Approximately **{loss_percentage:.1f}%** of the selected orders resulted in a financial loss.

Orders receiving larger discounts are more frequently concentrated near or below the zero-profit line, indicating that excessive discounting may reduce profitability.
"""
    )

    if trend < 0:

        st.success(
            """
📌 **Trend Insight**

As discount percentage increases, the average profit generally declines.

This suggests that offering larger discounts does not necessarily improve business profitability.
"""
        )

    else:

        st.success(
            """
📌 **Trend Insight**

Average profit remains relatively stable across different discount levels, indicating that the current discount strategy is balanced.
"""
        )
        
    # ==========================================================
    # DISCOUNT HIGHLIGHTS
    # ==========================================================

    st.markdown("### 📊 Discount Highlights")

    highest_discount = discount_df["Discount"].max()
    average_discount = discount_df["Discount"].mean()
    loss_orders = (discount_df["Profit"] < 0).sum()
    profit_orders = (discount_df["Profit"] > 0).sum()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        with st.container(border=True):
            st.metric(
                "Maximum Discount",
                f"{highest_discount:.0%}"
            )

    with c2:
        with st.container(border=True):
            st.metric(
                "Average Discount",
                f"{average_discount:.1%}"
            )

    with c3:
        with st.container(border=True):
            st.metric(
                "Loss Making Orders",
                f"{loss_orders:,}"
            )

    with c4:
        with st.container(border=True):
            st.metric(
                "Profitable Orders",
                f"{profit_orders:,}"
            )

    # ==========================================================
    # EXECUTIVE TAKEAWAY
    # ==========================================================

    st.markdown("### 💡 Executive Takeaway")

    risk_level = (
        "High"
        if average_discount > 0.30
        else "Low"
    )

    profit_trend = (
        "Declining"
        if trend < 0
        else "Stable"
    )

    e1, e2, e3 = st.columns(3)

    with e1:
        with st.container(border=True):
            st.metric(
                "Average Discount",
                f"{average_discount:.1%}"
            )

    with e2:
        with st.container(border=True):
            st.metric(
                "Profit Trend",
                profit_trend
            )

    with e3:
        with st.container(border=True):
            st.metric(
                "Risk Level",
                risk_level
            )

    st.markdown("")

    with st.container(border=True):

        if trend < 0:

            st.error(
                """
### Key Finding

Higher discount levels are associated with lower average profits.

This indicates that aggressive discounting may negatively impact profitability. Consider reviewing discount policies for products that frequently receive high discounts.
"""
            )

        else:

            st.success(
                """
### Key Finding

The current discount strategy appears balanced.

Average profits remain stable across discount levels, suggesting that the existing pricing strategy is effectively maintaining profitability.
"""
            )
            

with tab3:

    # ==========================================================
    # CUSTOMER ANALYSIS
    # ==========================================================

    st.subheader("Customer Analysis")

    st.caption(
        """
Understand customer purchasing behaviour, identify high-value customer groups,
and discover product preferences that can help improve sales and profitability.
"""
    )

    with st.expander("What business questions does this analysis answer?"):

        st.write("""
This section helps answer:

• Which customer segment contributes the highest sales?

• Which customer segment generates the highest profit?

• Which products are preferred by different customer groups?

• Which customers deserve special attention?

• How can these insights improve future sales and marketing decisions?
""")

    # ==========================================================
    # CUSTOMER FILTERS
    # ==========================================================

    filter1, filter2 = st.columns(2)

    with filter1:

        selected_segment = st.selectbox(
            "Customer Segment",
            ["All"] + sorted(df["Segment"].unique().tolist()),
            key="customer_segment"
        )

    with filter2:

        selected_region = st.selectbox(
            "Region",
            ["All"] + sorted(df["Region"].unique().tolist()),
            key="customer_region"
        )

    # ==========================================================
    # APPLY FILTERS
    # ==========================================================

    customer_df = df.copy()

    if selected_segment != "All":

        customer_df = customer_df[
            customer_df["Segment"] == selected_segment
        ]

    if selected_region != "All":

        customer_df = customer_df[
            customer_df["Region"] == selected_region
        ]

    # ==========================================================
    # CUSTOMER PERFORMANCE
    # ==========================================================

    customer_summary = (

        customer_df

        .groupby("Segment")

        .agg(

            Total_Sales=("Sales", "sum"),

            Total_Profit=("Profit", "sum"),

            Orders=("Order ID", "nunique"),

            Customers=("Customer ID", "nunique")

        )

        .reset_index()

    )

    customer_summary["Average Order Value"] = (

        customer_summary["Total_Sales"]

        /

        customer_summary["Orders"]

    )

    st.markdown("### Customer Buying Behaviour")

    left, right = st.columns(2)

    with left:

        st.markdown("#### Sales Contribution by Customer Segment")

        fig_sales_segment = px.bar(

            customer_summary,

            x="Segment",

            y="Total_Sales",

            color="Segment",

            text_auto="$,.2s",

            template="plotly_white"

        )

        fig_sales_segment.update_layout(

            height=420,

            showlegend=False,

            xaxis_title="",

            yaxis_title="Sales ($)"

        )

        st.plotly_chart(

            fig_sales_segment,

            use_container_width=True

        )

    with right:

        st.markdown("#### Profit Contribution by Customer Segment")

        fig_profit_segment = px.pie(

            customer_summary,

            names="Segment",

            values="Total_Profit",

            hole=0.55

        )

        fig_profit_segment.update_layout(

            height=420

        )

        st.plotly_chart(

            fig_profit_segment,

            use_container_width=True

        )

    st.divider()

    # ==========================================================
    # PRODUCT PREFERENCE ANALYSIS
    # ==========================================================

    st.markdown("### Product Preference Analysis")

    st.caption(
        """
Discover which product categories are most preferred by different customer segments.
These insights help marketing teams personalize campaigns and improve inventory planning.
"""
    )

    # ==========================================================
    # DATA PREPARATION
    # ==========================================================

    segment_category = (

        customer_df

        .groupby(["Segment", "Category"])["Sales"]

        .sum()

        .reset_index()

    )

    segment_subcategory = (

        customer_df

        .groupby(["Segment", "Sub-Category"])["Sales"]

        .sum()

        .reset_index()

    )

    left, right = st.columns(2)

    with left:

        st.markdown("#### Sales Distribution Across Product Categories")

        st.caption(
            """
See how each customer segment contributes to different product categories.
Higher bars indicate stronger customer preference.
"""
        )

        fig_category = px.bar(

            segment_category,

            x="Category",

            y="Sales",

            color="Segment",

            barmode="group",

            text_auto=".2s",

            template="plotly_white"

        )

        fig_category.update_layout(

            height=450,

            xaxis_title="",

            yaxis_title="Sales ($)"

        )

        st.plotly_chart(

            fig_category,

            use_container_width=True

        )

    with right:

        st.markdown("#### Category Preference by Customer Segment")

        st.caption(
            """
Each color represents total sales generated by a customer segment for a product category.
Darker colors indicate stronger purchasing preference.
"""
        )

        heatmap = (

            segment_category

            .pivot(

                index="Segment",

                columns="Category",

                values="Sales"

            )

        )

        fig_heat = px.imshow(

            heatmap,

            text_auto=".2s",

            aspect="auto",

            color_continuous_scale="Blues"

        )

        fig_heat.update_layout(

            height=450,

            coloraxis_colorbar_title="Sales"

        )

        st.plotly_chart(

            fig_heat,

            use_container_width=True

        )

    st.markdown("### Customer Preference Insights")

    top_preferences = (

        segment_category

        .sort_values("Sales", ascending=False)

        .groupby("Segment")

        .first()

        .reset_index()

    )

    cols = st.columns(len(top_preferences))

    for col, (_, row) in zip(cols, top_preferences.iterrows()):

        with col:

            with st.container(border=True):

                st.metric(

                    row["Segment"],

                    row["Category"]

                )

                st.caption(

                    f"Sales: ${row['Sales']:,.0f}"

                )

    st.divider()

    # ==========================================================
    # PRODUCT OPPORTUNITY ANALYSIS
    # ==========================================================

    st.markdown("### Product Opportunity Analysis")

    st.caption(
        """
Identify the best-selling products within each customer segment.

These insights help sales teams prioritize inventory, personalize promotions,
and identify products that deserve higher marketing investment.
"""
    )

    # ==========================================================
    # DATA PREPARATION
    # ==========================================================

    segment_products = (

        customer_df

        .groupby(
            ["Segment", "Sub-Category"]
        )["Sales"]

        .sum()

        .reset_index()

    )

    top_products = (

        segment_products

        .sort_values(
            "Sales",
            ascending=False
        )

        .groupby("Segment")

        .head(5)

    )

    # ==========================================================
    # SEGMENT SELECTOR
    # ==========================================================

    selected_segment_products = st.selectbox(

        "Select Customer Segment",

        sorted(customer_df["Segment"].unique()),

        key="segment_products"

    )

    display_products = top_products[

        top_products["Segment"]

        ==

        selected_segment_products

    ]

    # ==========================================================
    # CHART
    # ==========================================================

    fig = px.bar(

        display_products,

        x="Sales",

        y="Sub-Category",

        orientation="h",

        text_auto=".2s",

        color="Sales",

        color_continuous_scale="Blues",

        template="plotly_white"

    )

    fig.update_layout(

        height=430,

        yaxis=dict(

            categoryorder="total ascending"

        ),

        xaxis_title="Sales ($)",

        yaxis_title=""

    )

    st.plotly_chart(

        fig,

        use_container_width=True

    )

    # ==========================================================
    # KPI CARDS
    # ==========================================================

    best_product = display_products.iloc[-1]

    lowest_product = display_products.iloc[0]

    sales_gap = (

        best_product["Sales"]

        -

        lowest_product["Sales"]

    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(

            "Most Popular Product",

            best_product["Sub-Category"]

        )

    with col2:

        st.metric(

            "Sales",

            f"${best_product['Sales']:,.0f}"

        )

    with col3:

        st.metric(

            "Sales Gap",

            f"${sales_gap:,.0f}"

        )

    st.divider()

    # ==========================================================
    # CUSTOMER OPPORTUNITY MATRIX
    # ==========================================================

    st.markdown("### Customer Opportunity Matrix")

    st.caption(
        """
Evaluate the performance of each customer segment based on
its sales and profitability to identify future business opportunities.
"""
    )

    # ==========================================================
    # DATA PREPARATION
    # ==========================================================

    customer_matrix = (

        customer_df

        .groupby("Segment")

        .agg(

            Sales=("Sales", "sum"),

            Profit=("Profit", "sum"),

            Orders=("Order ID", "nunique"),

            Customers=("Customer ID", "nunique")

        )

        .reset_index()

    )

    customer_matrix["Profit Margin"] = (

        customer_matrix["Profit"]

        /

        customer_matrix["Sales"]

    ) * 100

        # ==========================================================
    # BUSINESS CLASSIFICATION
    # ==========================================================

    overall_sales = customer_matrix["Sales"].mean()

    overall_profit = customer_matrix["Profit"].mean()

    status = []

    for _, row in customer_matrix.iterrows():

        if row["Sales"] >= overall_sales and row["Profit"] >= overall_profit:

            status.append("Growth Driver")

        elif row["Sales"] >= overall_sales:

            status.append("Revenue Focus")

        elif row["Profit"] >= overall_profit:

            status.append("High Margin Opportunity")

        else:

            status.append("Growth Potential")

    status_colors = {
        "Growth Driver": "🟢 Growth Driver",
        "Revenue Focus": "🟡 Revenue Focus",
        "High Margin Opportunity": "🔵 High Margin Opportunity",
        "Growth Potential": "🟠 Growth Potential"
    }

    customer_matrix["Business Status"] = [
        status_colors[s] for s in status
    ]

    # ==========================================================
    # FIND TOP SEGMENTS
    # ==========================================================

    highest_sales = customer_matrix.loc[
        customer_matrix["Sales"].idxmax()
    ]

    highest_profit = customer_matrix.loc[
        customer_matrix["Profit"].idxmax()
    ]

    highest_margin = customer_matrix.loc[
        customer_matrix["Profit Margin"].idxmax()
    ]

    # ==========================================================
    # DISPLAY TABLE
    # ==========================================================

    display_matrix = customer_matrix.copy()

    display_matrix["Sales"] = display_matrix["Sales"].map(
        lambda x: f"${x:,.0f}"
    )

    display_matrix["Profit"] = display_matrix["Profit"].map(
        lambda x: f"${x:,.0f}"
    )

    display_matrix["Profit Margin"] = (
        display_matrix["Profit Margin"]
        .round(1)
        .astype(str)
        + "%"
    )

    display_matrix.rename(
        columns={
            "Segment": "Customer Segment",
            "Sales": "Total Sales",
            "Profit": "Total Profit",
            "Orders": "Orders",
            "Customers": "Customers",
            "Profit Margin": "Profit Margin",
            "Business Status": "Business Status"
        },
        inplace=True
    )

    # ==========================================================
    # QUICK KPI SUMMARY
    # ==========================================================

    k1, k2, k3 = st.columns(3)

    with k1:
        st.metric(
            "Top Revenue Segment",
            highest_sales["Segment"]
        )

    with k2:
        st.metric(
            "Top Profit Segment",
            highest_profit["Segment"]
        )

    with k3:
        st.metric(
            "Highest Margin Segment",
            highest_margin["Segment"]
        )

    # ==========================================================
    # CUSTOMER OPPORTUNITY MATRIX
    # ==========================================================

    st.dataframe(
        display_matrix,
        use_container_width=True,
        hide_index=True
    )

        # ==========================================================
    # KEY BUSINESS INSIGHTS
    # ==========================================================

    st.markdown("### Key Business Insights")

    c1, c2 = st.columns(2)

    with c1:

        with st.container(border=True):

            st.markdown("#### 📈 Top Revenue Contributor")

            st.write(
                f"""
**{highest_sales['Segment']}**

Generates the highest sales revenue among all customer segments.
"""
            )

    with c2:

        with st.container(border=True):

            st.markdown("#### 💰 Highest Profit Generator")

            st.write(
                f"""
**{highest_profit['Segment']}**

Contributes the greatest overall profit to the business.
"""
            )

    c3, c4 = st.columns(2)

    with c3:

        with st.container(border=True):

            st.markdown("#### 📊 Best Profit Margin")

            st.write(
                f"""
**{highest_margin['Segment']}**

Has the strongest profit margin and the most efficient revenue generation.
"""
            )

    with c4:

        with st.container(border=True):

            st.markdown("#### 🎯 Strategic Recommendation")

            st.write(
                """
Prioritize investment in **Growth Driver** segments while designing targeted campaigns for **Growth Potential** customers.
"""
            )

    st.divider()
    
with tab4:
    # ==========================================================
# REGIONAL ANALYSIS
# ==========================================================

    st.subheader("Regional Analysis")

    st.caption(
        """
Analyze business performance across different geographical regions,
identify high-performing markets, and discover growth opportunities.
"""
    )

    with st.expander("What business questions does this analysis answer?"):

        st.write(
            """
This section helps answer:

• Which region generates the highest sales?

• Which region earns the highest profit?

• Which states drive regional performance?

• Which product categories perform best in each region?

• Which regions require business attention?

• Where should future investments be focused?
"""
        )

    # ==========================================================
    # REGIONAL FILTERS
    # ==========================================================

    st.markdown("### Regional Filters")

    f1, f2, f3 = st.columns(3)

    with f1:

        selected_region = st.selectbox(
            "Region",
            ["All"] + sorted(df["Region"].unique()),
            key="regional_region"
        )

    with f2:

        selected_category = st.selectbox(
            "Category",
            ["All"] + sorted(df["Category"].unique()),
            key="regional_category"
        )

    with f3:

        selected_segment = st.selectbox(
            "Customer Segment",
            ["All"] + sorted(df["Segment"].unique()),
            key="regional_segment"
        )

    # ==========================================================
    # APPLY FILTERS
    # ==========================================================

    regional_df = df.copy()

    if selected_region != "All":

        regional_df = regional_df[
            regional_df["Region"] == selected_region
        ]

    if selected_category != "All":

        regional_df = regional_df[
            regional_df["Category"] == selected_category
        ]

    if selected_segment != "All":

        regional_df = regional_df[
            regional_df["Segment"] == selected_segment
        ]
    
        # ==========================================================
    # REGIONAL PERFORMANCE SNAPSHOT
    # ==========================================================

    regional_summary = (

        regional_df

        .groupby("Region")

        .agg(

            Total_Sales=("Sales", "sum"),

            Total_Profit=("Profit", "sum"),

            Orders=("Order ID", "nunique"),

            Customers=("Customer ID", "nunique")

        )

        .reset_index()

    )

    regional_summary["Profit Margin"] = (

        regional_summary["Total_Profit"]

        /

        regional_summary["Total_Sales"]

    ) * 100

    # ==========================================================
    # IDENTIFY TOP REGIONS
    # ==========================================================

    highest_sales_region = regional_summary.loc[
        regional_summary["Total_Sales"].idxmax()
    ]

    highest_profit_region = regional_summary.loc[
        regional_summary["Total_Profit"].idxmax()
    ]

    highest_margin_region = regional_summary.loc[
        regional_summary["Profit Margin"].idxmax()
    ]

    lowest_profit_region = regional_summary.loc[
        regional_summary["Total_Profit"].idxmin()
    ]

    # ==========================================================
    # SNAPSHOT CARDS
    # ==========================================================

    st.markdown("### Regional Performance Snapshot")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        with st.container(border=True):

            st.metric(

                "Highest Revenue Region",

                highest_sales_region["Region"],

                f"${highest_sales_region['Total_Sales']:,.0f}"

            )

    with c2:

        with st.container(border=True):

            st.metric(

                "Highest Profit Region",

                highest_profit_region["Region"],

                f"${highest_profit_region['Total_Profit']:,.0f}"

            )

    with c3:

        with st.container(border=True):

            st.metric(

                "Best Profit Margin",

                highest_margin_region["Region"],

                f"{highest_margin_region['Profit Margin']:.1f}%"

            )

    with c4:

        with st.container(border=True):

            st.metric(

                "Needs Attention",

                lowest_profit_region["Region"],

                f"${lowest_profit_region['Total_Profit']:,.0f}"

            )

    st.divider()
    
        # ==========================================================
    # REGIONAL PERFORMANCE MATRIX
    # ==========================================================

    st.markdown("### Regional Performance Matrix")

    st.caption(
        """
Compare the business performance of every region based on sales,
profitability, customer reach and operational efficiency.
"""
    )

    # ==========================================================
    # BUSINESS CLASSIFICATION
    # ==========================================================

    average_sales = regional_summary["Total_Sales"].mean()

    average_profit = regional_summary["Total_Profit"].mean()

    status = []

    for _, row in regional_summary.iterrows():

        if (
            row["Total_Sales"] >= average_sales
            and
            row["Total_Profit"] >= average_profit
        ):

            status.append("Growth Driver")

        elif row["Total_Sales"] >= average_sales:

            status.append("Revenue Opportunity")

        elif row["Total_Profit"] >= average_profit:

            status.append("High Margin")

        else:

            status.append("Needs Attention")

    status_colors = {

        "Growth Driver": "🟢 Growth Driver",

        "Revenue Opportunity": "🟡 Revenue Opportunity",

        "High Margin": "🔵 High Margin",

        "Needs Attention": "🟠 Needs Attention"

    }

    regional_summary["Business Status"] = [

        status_colors[s]

        for s in status

    ]

    # ==========================================================
    # FORMAT TABLE
    # ==========================================================

    display_table = regional_summary.copy()

    display_table["Total_Sales"] = display_table["Total_Sales"].map(
        lambda x: f"${x:,.0f}"
    )

    display_table["Total_Profit"] = display_table["Total_Profit"].map(
        lambda x: f"${x:,.0f}"
    )

    display_table["Profit Margin"] = (
        display_table["Profit Margin"]
        .round(1)
        .astype(str)
        + "%"
    )

    display_table.rename(
        columns={

            "Region":"Region",

            "Total_Sales":"Total Sales",

            "Total_Profit":"Total Profit",

            "Orders":"Orders",

            "Customers":"Customers",

            "Profit Margin":"Profit Margin",

            "Business Status":"Business Status"

        },
        inplace=True
    )

    st.dataframe(

        display_table,

        use_container_width=True,

        hide_index=True

    )

    st.divider()
    
        # ==========================================================
    # STATE PERFORMANCE EXPLORER
    # ==========================================================

    st.markdown("### State Performance Explorer")

    st.caption(
        """
Explore the performance of individual states within a selected region.
This helps identify which states contribute the most revenue,
generate the highest profit, and require additional business attention.
"""
    )

    # ==========================================================
    # REGION SELECTOR
    # ==========================================================

    selected_state_region = st.selectbox(

        "Select Region to Explore",

        sorted(regional_df["Region"].unique()),

        key="state_region"

    )

    state_df = regional_df[
        regional_df["Region"] == selected_state_region
    ]

    # ==========================================================
    # STATE SUMMARY
    # ==========================================================

    state_summary = (

        state_df

        .groupby("State")

        .agg(

            Total_Sales=("Sales", "sum"),

            Total_Profit=("Profit", "sum"),

            Orders=("Order ID", "nunique"),

            Customers=("Customer ID", "nunique")

        )

        .reset_index()

    )

    state_summary["Profit Margin"] = (

        state_summary["Total_Profit"]

        /

        state_summary["Total_Sales"]

    ) * 100

    state_summary = state_summary.sort_values(

        "Total_Sales",

        ascending=False

    )
    
        # ==========================================================
    # STATE SNAPSHOT
    # ==========================================================

    top_sales_state = state_summary.iloc[0]

    top_profit_state = state_summary.loc[
        state_summary["Total_Profit"].idxmax()
    ]

    best_margin_state = state_summary.loc[
        state_summary["Profit Margin"].idxmax()
    ]

    c1, c2, c3 = st.columns(3)

    with c1:

        with st.container(border=True):

            st.metric(

                "Highest Revenue State",

                top_sales_state["State"],

                f"${top_sales_state['Total_Sales']:,.0f}"

            )

    with c2:

        with st.container(border=True):

            st.metric(

                "Highest Profit State",

                top_profit_state["State"],

                f"${top_profit_state['Total_Profit']:,.0f}"

            )

    with c3:

        with st.container(border=True):

            st.metric(

                "Best Profit Margin",

                best_margin_state["State"],

                f"{best_margin_state['Profit Margin']:.1f}%"

            )
        
        # ==========================================================
    # STATE PERFORMANCE TABLE
    # ==========================================================

    display_state = state_summary.copy()

    display_state["Total_Sales"] = display_state["Total_Sales"].map(
        lambda x: f"${x:,.0f}"
    )

    display_state["Total_Profit"] = display_state["Total_Profit"].map(
        lambda x: f"${x:,.0f}"
    )

    display_state["Profit Margin"] = (
        display_state["Profit Margin"]
        .round(1)
        .astype(str)
        + "%"
    )

    display_state.rename(
        columns={
            "State": "State",
            "Total_Sales": "Total Sales",
            "Total_Profit": "Total Profit",
            "Orders": "Orders",
            "Customers": "Customers",
            "Profit Margin": "Profit Margin"
        },
        inplace=True
    )

    st.dataframe(

        display_state,

        use_container_width=True,

        hide_index=True

    )
    
with tab5:
        # ==========================================================
    # SHIPPING ANALYSIS
    # ==========================================================

    st.subheader("Shipping Analysis")

    st.caption(
        """
Evaluate shipping performance, delivery efficiency, and operational effectiveness
to identify opportunities for improving customer satisfaction and business profitability.
"""
    )

    with st.expander("What business questions does this analysis answer?"):

        st.write(
            """
This section helps answer:

• Which shipping mode is used the most?

• Which shipping mode generates the highest sales?

• Which shipping mode generates the highest profit?

• Which shipping method delivers products fastest?

• How does shipping performance vary across regions?

• Which shipping strategy should the business prioritize?
"""
        )

    # ==========================================================
    # SHIPPING FILTERS
    # ==========================================================

    st.markdown("### Shipping Filters")

    f1, f2, f3 = st.columns(3)

    with f1:

        selected_ship = st.selectbox(
            "Shipping Mode",
            ["All"] + sorted(df["Ship Mode"].unique()),
            key="shipping_mode"
        )

    with f2:

        selected_region = st.selectbox(
            "Region",
            ["All"] + sorted(df["Region"].unique()),
            key="shipping_region"
        )

    with f3:

        selected_category = st.selectbox(
            "Category",
            ["All"] + sorted(df["Category"].unique()),
            key="shipping_category"
        )

    # ==========================================================
    # APPLY FILTERS
    # ==========================================================

    shipping_df = df.copy()

    if selected_ship != "All":

        shipping_df = shipping_df[
            shipping_df["Ship Mode"] == selected_ship
        ]

    if selected_region != "All":

        shipping_df = shipping_df[
            shipping_df["Region"] == selected_region
        ]

    if selected_category != "All":

        shipping_df = shipping_df[
            shipping_df["Category"] == selected_category
        ]
        
            # ==========================================================
    # SHIPPING SUMMARY
    # ==========================================================

    shipping_summary = (

        shipping_df

        .groupby("Ship Mode")

        .agg(

            Total_Sales=("Sales", "sum"),

            Total_Profit=("Profit", "sum"),

            Orders=("Order ID", "nunique"),

            Average_Delivery=("Shipping_Days", "mean")

        )

        .reset_index()

    )

    # ==========================================================
    # IDENTIFY TOP SHIPPING MODES
    # ==========================================================

    highest_sales = shipping_summary.loc[
        shipping_summary["Total_Sales"].idxmax()
    ]

    highest_profit = shipping_summary.loc[
        shipping_summary["Total_Profit"].idxmax()
    ]

    fastest = shipping_summary.loc[
        shipping_summary["Average_Delivery"].idxmin()
    ]

    most_used = shipping_summary.loc[
        shipping_summary["Orders"].idxmax()
    ]

    # ==========================================================
    # SHIPPING PERFORMANCE SNAPSHOT
    # ==========================================================

    st.markdown("### Shipping Performance Snapshot")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        with st.container(border=True):

            st.metric(
                "Most Used Shipping Mode",
                most_used["Ship Mode"],
                f"{int(most_used['Orders'])} Orders"
            )

    with c2:

        with st.container(border=True):

            st.metric(
                "Highest Revenue Shipping",
                highest_sales["Ship Mode"],
                f"${highest_sales['Total_Sales']:,.0f}"
            )

    with c3:

        with st.container(border=True):

            st.metric(
                "Highest Profit Shipping",
                highest_profit["Ship Mode"],
                f"${highest_profit['Total_Profit']:,.0f}"
            )

    with c4:

        with st.container(border=True):

            st.metric(
                "Fastest Delivery",
                fastest["Ship Mode"],
                f"{fastest['Average_Delivery']:.1f} Days"
            )

    st.divider()
    
        # ==========================================================
    # SHIPPING PERFORMANCE MATRIX
    # ==========================================================

    st.markdown("### Shipping Performance Matrix")

    st.caption(
        """
Compare all shipping modes based on sales, profit, delivery speed
and order volume to identify the most effective shipping strategy.
"""
    )

    # ==========================================================
    # CALCULATE PROFIT MARGIN
    # ==========================================================

    shipping_summary["Profit Margin"] = (

        shipping_summary["Total_Profit"]

        /

        shipping_summary["Total_Sales"]

    ) * 100

    # ==========================================================
    # BUSINESS CLASSIFICATION
    # ==========================================================

    avg_profit = shipping_summary["Total_Profit"].mean()

    avg_delivery = shipping_summary["Average_Delivery"].mean()

    status = []

    for _, row in shipping_summary.iterrows():

        if (
            row["Total_Profit"] >= avg_profit
            and
            row["Average_Delivery"] <= avg_delivery
        ):

            status.append("Highly Efficient")

        elif row["Total_Profit"] >= avg_profit:

            status.append("Profitable")

        elif row["Average_Delivery"] <= avg_delivery:

            status.append("Fast Delivery")

        else:

            status.append("Needs Improvement")

    shipping_summary["Business Status"] = status

    status_colors = {

        "Highly Efficient": "🟢 Highly Efficient",

        "Profitable": "🔵 Profitable",

        "Fast Delivery": "🟡 Fast Delivery",

        "Needs Improvement": "🟠 Needs Improvement"

    }

    shipping_summary["Business Status"] = [

        status_colors[s]

        for s in shipping_summary["Business Status"]

    ]

    # ==========================================================
    # FORMAT TABLE
    # ==========================================================

    display_shipping = shipping_summary.copy()

    display_shipping["Total_Sales"] = display_shipping["Total_Sales"].map(
        lambda x: f"${x:,.0f}"
    )

    display_shipping["Total_Profit"] = display_shipping["Total_Profit"].map(
        lambda x: f"${x:,.0f}"
    )

    display_shipping["Profit Margin"] = (
        display_shipping["Profit Margin"]
        .round(1)
        .astype(str)
        + "%"
    )

    display_shipping["Average_Delivery"] = (
        display_shipping["Average_Delivery"]
        .round(1)
        .astype(str)
        + " Days"
    )

    display_shipping.rename(
        columns={
            "Ship Mode": "Shipping Mode",
            "Total_Sales": "Total Sales",
            "Total_Profit": "Total Profit",
            "Orders": "Orders",
            "Average_Delivery": "Average Delivery",
            "Profit Margin": "Profit Margin",
            "Business Status": "Business Status"
        },
        inplace=True
    )

    st.dataframe(

        display_shipping,

        use_container_width=True,

        hide_index=True

    )

    st.divider()
    
        # ==========================================================
    # DELIVERY TIME ANALYSIS
    # ==========================================================

    st.markdown("### Delivery Time Analysis")

    st.caption(
        """
Compare the average delivery time across different shipping modes.
Lower values indicate faster deliveries and improved customer experience.
"""
    )

    fig_delivery = px.bar(

        shipping_summary,

        x="Ship Mode",

        y="Average_Delivery",

        color="Ship Mode",

        text_auto=".1f",

        template="plotly_white"

    )

    fig_delivery.update_layout(

        height=430,

        showlegend=False,

        xaxis_title="",

        yaxis_title="Average Delivery Time (Days)"

    )

    fig_delivery.update_traces(

        textposition="outside"

    )

    st.plotly_chart(

        fig_delivery,

        use_container_width=True

    )

    fastest_mode = shipping_summary.loc[
        shipping_summary["Average_Delivery"].idxmin()
    ]

    slowest_mode = shipping_summary.loc[
        shipping_summary["Average_Delivery"].idxmax()
    ]

    c1, c2 = st.columns(2)

    with c1:

        with st.container(border=True):

            st.markdown("#### Fastest Shipping")

            st.write(
                f"""
**{fastest_mode['Ship Mode']}**

Average delivery time of **{fastest_mode['Average_Delivery']:.1f} days**,
making it the quickest shipping option.
"""
            )

    with c2:

        with st.container(border=True):

            st.markdown("#### Slowest Shipping")

            st.write(
                f"""
**{slowest_mode['Ship Mode']}**

Average delivery time of **{slowest_mode['Average_Delivery']:.1f} days**,
indicating potential opportunities for logistics improvement.
"""
            )

    st.divider()
    
        # ==========================================================
    # REGIONAL SHIPPING BEHAVIOUR
    # ==========================================================

    st.markdown("### Regional Shipping Behaviour")

    st.caption(
        """
Compare how different shipping modes perform across regions to identify
regional logistics strengths and opportunities for improvement.
"""
    )

    selected_region_shipping = st.selectbox(

        "Select Region",

        sorted(shipping_df["Region"].unique()),

        key="regional_shipping"

    )

    regional_shipping = shipping_df[

        shipping_df["Region"] == selected_region_shipping

    ]

    regional_summary = (

        regional_shipping

        .groupby("Ship Mode")

        .agg(

            Orders=("Order ID","nunique"),

            Sales=("Sales","sum"),

            Profit=("Profit","sum"),

            Average_Delivery=("Shipping_Days","mean")

        )

        .reset_index()

    )

    regional_summary["Profit Margin"] = (

        regional_summary["Profit"]

        /

        regional_summary["Sales"]

    ) * 100

    display = regional_summary.copy()

    display["Sales"] = display["Sales"].map(
        lambda x: f"${x:,.0f}"
    )

    display["Profit"] = display["Profit"].map(
        lambda x: f"${x:,.0f}"
    )

    display["Average_Delivery"] = (
        display["Average_Delivery"]
        .round(1)
        .astype(str)
        + " Days"
    )

    display["Profit Margin"] = (
        display["Profit Margin"]
        .round(1)
        .astype(str)
        + "%"
    )

    display.rename(
        columns={
            "Ship Mode":"Shipping Mode",
            "Orders":"Orders",
            "Sales":"Total Sales",
            "Profit":"Total Profit",
            "Average_Delivery":"Average Delivery",
            "Profit Margin":"Profit Margin"
        },
        inplace=True
    )

    st.dataframe(

        display,

        use_container_width=True,

        hide_index=True

    )

    st.divider()
    
        # ==========================================================
    # SHIPPING OPPORTUNITY ANALYSIS
    # ==========================================================

    st.markdown("### Shipping Opportunity Analysis")

    best_sales = regional_summary.loc[
        regional_summary["Sales"].idxmax()
    ]

    best_profit = regional_summary.loc[
        regional_summary["Profit"].idxmax()
    ]

    fastest = regional_summary.loc[
        regional_summary["Average_Delivery"].idxmin()
    ]

    highest_margin = regional_summary.loc[
        regional_summary["Profit Margin"].idxmax()
    ]

    c1, c2 = st.columns(2)

    with c1:

        with st.container(border=True):

            st.markdown("#### Revenue Leader")

            st.write(
                f"""
**{best_sales['Ship Mode']}**

Generates the highest sales within the **{selected_region_shipping}**
region, making it the dominant shipping option.
"""
            )

    with c2:

        with st.container(border=True):

            st.markdown("#### Profit Leader")

            st.write(
                f"""
**{best_profit['Ship Mode']}**

Produces the highest overall profit and should remain
the preferred shipping method wherever possible.
"""
            )

    c3, c4 = st.columns(2)

    with c3:

        with st.container(border=True):

            st.markdown("#### Fastest Delivery")

            st.write(
                f"""
**{fastest['Ship Mode']}**

Has the quickest average delivery time of
**{fastest['Average_Delivery']:.1f} days**.
"""
            )

    with c4:

        with st.container(border=True):

            st.markdown("#### Most Efficient")

            st.write(
                f"""
**{highest_margin['Ship Mode']}**

Achieves the highest profit margin,
making it the most operationally efficient
shipping option.
"""
            )

    st.divider()
    
with tab6:
        # ==========================================================
    # EXECUTIVE AI SUMMARY
    # ==========================================================

    st.subheader("Executive AI Summary")

    st.caption(
        """
This section automatically summarizes key business performance indicators
and highlights important opportunities, risks and strategic recommendations
based on the available sales data.
"""
    )

    with st.expander("What does this report provide?"):

        st.write(
            """
The Executive AI Summary combines insights from every analysis performed
within this dashboard.

It summarizes:

• Business Health

• Profitability

• Customer Behaviour

• Regional Performance

• Shipping Performance

• Discount Impact

• Strategic Business Recommendations

The objective is to provide decision-makers with a concise overview
without requiring them to review every chart individually.
"""
        )

    st.divider()
    
        # ==========================================================
    # BUSINESS HEALTH SCORE
    # ==========================================================

    total_sales = df["Sales"].sum()

    total_profit = df["Profit"].sum()

    avg_discount = df["Discount"].mean()

    profit_margin = (total_profit / total_sales) * 100

    if profit_margin >= 12:

        health_score = 95
        health_status = "Excellent"

    elif profit_margin >= 10:

        health_score = 88
        health_status = "Very Good"

    elif profit_margin >= 8:

        health_score = 78
        health_status = "Good"

    elif profit_margin >= 5:

        health_score = 65
        health_status = "Average"

    else:

        health_score = 50
        health_status = "Needs Improvement"

        st.markdown("### Business Health Overview")

        # ==========================================================
    # BUSINESS HEALTH OVERVIEW
    # ==========================================================

    st.markdown("### Business Health Overview")

    if health_score >= 95:

        status_color = "#16A34A"
        status_icon = "🟢"
        health_grade = "A+"

    elif health_score >= 90:

        status_color = "#22C55E"
        status_icon = "🟢"
        health_grade = "A"

    elif health_score >= 80:

        status_color = "#2563EB"
        status_icon = "🔵"
        health_grade = "B+"

    elif health_score >= 70:

        status_color = "#F59E0B"
        status_icon = "🟠"
        health_grade = "B"

    else:

        status_color = "#DC2626"
        status_icon = "🔴"
        health_grade = "C"

    st.markdown(
        f"""
<div style="
background:linear-gradient(135deg,#F8FAFC,#FFFFFF);
padding:30px;
border-radius:18px;
border-left:8px solid {status_color};
box-shadow:0px 8px 20px rgba(0,0,0,0.10);
">

<h2 style="margin-bottom:5px;color:{status_color};">
Business Health Score
</h2>

<p style="font-size:17px;color:#444;margin-top:0px;">
Overall business performance based on profitability,
discount strategy and operational efficiency.
</p>

<hr>

<div style="
display:flex;
justify-content:space-between;
align-items:center;
margin-top:15px;
">

<div>

<div style="
display:flex;
align-items:center;
gap:18px;
">

<h1 style="
font-size:54px;
margin:0;
color:{status_color};
">
{health_score}/100
</h1>

<div style="
padding:10px 18px;
background:{status_color};
color:white;
font-size:22px;
font-weight:bold;
border-radius:12px;
">
{health_grade}
</div>

</div>

<p style="
font-size:18px;
margin-top:8px;
color:#555;
">
Current Status :
<b style="color:{status_color};">
{status_icon} {health_status}
</b>
</p>

</div>

<div style="
width:55%;
">

<div style="
background:#E5E7EB;
height:18px;
border-radius:20px;
overflow:hidden;
">

<div style="
width:{health_score}%;
background:{status_color};
height:18px;
">
</div>

</div>

<p style="
text-align:right;
margin-top:8px;
color:#666;
font-size:14px;
">
Business Health Index
</p>

</div>

</div>

<hr style="margin-top:25px;margin-bottom:25px;">

<div style="
display:grid;
grid-template-columns:repeat(4,1fr);
gap:18px;
text-align:center;
">

<div style="
padding:18px;
background:#F3F4F6;
border-radius:12px;
">

<h4 style="margin:0;color:#444;">
Business Health
</h4>

<h2 style="margin-top:10px;color:{status_color};">
{health_score}/100
</h2>

</div>

<div style="
padding:18px;
background:#F3F4F6;
border-radius:12px;
">

<h4 style="margin:0;color:#444;">
Current Status
</h4>

<h2 style="margin-top:10px;color:{status_color};">
{health_status}
</h2>

</div>

<div style="
padding:18px;
background:#F3F4F6;
border-radius:12px;
">

<h4 style="margin:0;color:#444;">
Profit Margin
</h4>

<h2 style="margin-top:10px;color:#1E3A8A;">
{profit_margin:.2f}%
</h2>

</div>

<div style="
padding:18px;
background:#F3F4F6;
border-radius:12px;
">

<h4 style="margin:0;color:#444;">
Average Discount
</h4>

<h2 style="margin-top:10px;color:#B45309;">
{avg_discount:.1%}
</h2>

</div>

</div>

</div>
""",
        unsafe_allow_html=True
    )

    st.divider()
    
       # ==========================================================
    # KEY STRENGTHS
    # ==========================================================

    st.markdown("## Key Strengths")

    # ----------------------------------------------------------
    # Calculate Insights
    # ----------------------------------------------------------

    top_category = (
        df.groupby("Category")["Profit"]
        .sum()
        .idxmax()
    )

    top_segment = (
        df.groupby("Segment")["Sales"]
        .sum()
        .idxmax()
    )

    top_region = (
        df.groupby("Region")["Profit"]
        .sum()
        .idxmax()
    )

    profit_margin = (
        df["Profit"].sum()
        / df["Sales"].sum()
    ) * 100

    # ----------------------------------------------------------
    # Display Cards
    # ----------------------------------------------------------

    c1, c2 = st.columns(2)

    with c1:

        with st.container(border=True):

            st.markdown("### Highest Performing Category")

            st.write(
                f"""
**{top_category}**

Generated the highest overall profit among all product categories.
"""
            )

    with c2:

        with st.container(border=True):

            st.markdown("### Strongest Customer Segment")

            st.write(
                f"""
**{top_segment}**

Contributes the largest share of total sales revenue.
"""
            )

    c3, c4 = st.columns(2)

    with c3:

        with st.container(border=True):

            st.markdown("### Best Performing Region")

            st.write(
                f"""
**{top_region}**

Delivers the highest total profit across all regions.
"""
            )

    with c4:

        with st.container(border=True):

            st.markdown("### Healthy Profit Margin")

            st.write(
                f"""
Current profit margin stands at **{profit_margin:.2f}%**, indicating healthy overall business profitability.
"""
            )

    st.divider()
        # ==========================================================
    # EXECUTIVE RECOMMENDATIONS
    # ==========================================================

    st.markdown("## Executive Recommendations")

    # ----------------------------------------------------------
    # Calculate Key Insights
    # ----------------------------------------------------------

    best_region = (
        df.groupby("Region")["Profit"]
        .sum()
        .idxmax()
    )

    worst_region = (
        df.groupby("Region")["Profit"]
        .sum()
        .idxmin()
    )

    best_category = (
        df.groupby("Category")["Profit"]
        .sum()
        .idxmax()
    )

    worst_category = (
        df.groupby("Category")["Profit"]
        .sum()
        .idxmin()
    )

    best_segment = (
        df.groupby("Segment")["Sales"]
        .sum()
        .idxmax()
    )

    avg_discount = df["Discount"].mean()

    profit_margin = (
        df["Profit"].sum()
        /
        df["Sales"].sum()
    ) * 100

    # ----------------------------------------------------------
    # Recommendation Cards
    # ----------------------------------------------------------

    r1, r2 = st.columns(2)

    with r1:

        with st.container(border=True):

            st.markdown("### Pricing Strategy")

            if avg_discount > 0.20:

                st.warning(
                    f"""
The current average discount is **{avg_discount:.1%}**.

Review high-discount products to improve overall profitability while maintaining competitive pricing.
"""
                )

            else:

                st.success(
                    f"""
The average discount of **{avg_discount:.1%}** remains well controlled.

Continue monitoring promotional campaigns while maintaining pricing discipline.
"""
                )

    with r2:

        with st.container(border=True):

            st.markdown("### Regional Growth")

            st.info(
                f"""
**{best_region}** is currently the strongest performing region.

Consider applying successful sales and marketing strategies from this region to **{worst_region}** to improve overall business performance.
"""
            )

    r3, r4 = st.columns(2)

    with r3:

        with st.container(border=True):

            st.markdown("### Product Portfolio")

            st.info(
                f"""
Increase focus on **{best_category}**, which delivers the highest profitability.

Review pricing, promotions and inventory planning for **{worst_category}** to improve returns.
"""
            )

    with r4:

        with st.container(border=True):

            st.markdown("### Customer Strategy")

            st.info(
                f"""
The **{best_segment}** segment contributes the highest sales.

Strengthen customer loyalty through personalized offers and targeted retention campaigns.
"""
            )

    st.divider()

    # ==========================================================
    # KPI SUMMARY TABLE
    # ==========================================================

    st.markdown("## Executive Performance Scorecard")

    st.caption(
        """
A consolidated overview of the most important business performance indicators.
This summary enables executives to quickly assess overall business health.
"""
    )

    # ----------------------------------------------------------
    # KPI CALCULATIONS
    # ----------------------------------------------------------

    total_sales = df["Sales"].sum()

    total_profit = df["Profit"].sum()

    profit_margin = (total_profit / total_sales) * 100

    avg_discount = df["Discount"].mean()

    loss_percentage = (
        (df["Profit"] < 0).sum()
        / len(df)
    ) * 100

    best_region = (
        df.groupby("Region")["Profit"]
        .sum()
        .idxmax()
    )

    best_category = (
        df.groupby("Category")["Profit"]
        .sum()
        .idxmax()
    )

    # ----------------------------------------------------------
    # STATUS FUNCTIONS
    # ----------------------------------------------------------

    def margin_status(value):

        if value >= 12:
            return "🟢 Strong"

        elif value >= 8:
            return "🟡 Moderate"

        else:
            return "🔴 Needs Attention"


    def discount_status(value):

        if value <= 0.15:
            return "🟢 Controlled"

        elif value <= 0.25:
            return "🟡 Monitor"

        else:
            return "🔴 High"


    def loss_status(value):

        if value <= 15:
            return "🟢 Healthy"

        elif value <= 25:
            return "🟡 Moderate"

        else:
            return "🔴 High"

    # ----------------------------------------------------------
    # SUMMARY TABLE
    # ----------------------------------------------------------

    summary = pd.DataFrame({

        "Business KPI": [

            "Total Sales",

            "Total Profit",

            "Profit Margin",

            "Average Discount",

            "Loss Making Orders",

            "Best Performing Region",

            "Best Performing Category"

        ],

        "Current Value": [

            f"${total_sales:,.0f}",

            f"${total_profit:,.0f}",

            f"{profit_margin:.2f}%",

            f"{avg_discount:.1%}",

            f"{loss_percentage:.1f}%",

            best_region,

            best_category

        ],

        "Status": [

            "🟢 Excellent",

            "🟢 Healthy",

            margin_status(profit_margin),

            discount_status(avg_discount),

            loss_status(loss_percentage),

            "🟢 High Performer",

            "🟢 High Performer"

        ]

    })

    st.dataframe(

        summary,

        use_container_width=True,

        hide_index=True

    )


    
import streamlit as st
import pandas as pd
import joblib
import os

from utils.database import create_table, save_prediction
from utils.data_loader import get_prediction_ready_dataset, has_columns
from utils.data_cleaner import check_prediction_compatibility, PREDICTION_REQUIRED_FEATURES

create_table()

# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="AI Sales Prediction",
    page_icon="🤖",
    layout="wide"
)

# ==========================================================
# PAGE TITLE
# ==========================================================

st.title("AI Sales Prediction")

st.caption(
    """
Predict future sales using the trained Machine Learning model.
Provide business inputs below to estimate expected sales and receive intelligent business recommendations.
"""
)

st.divider()

# ==========================================================
# LOAD MODEL
# ==========================================================

MODEL_PATH = "models/sales_model.pkl"

try:
    model = joblib.load(MODEL_PATH)
except Exception:
    st.error("Unable to load the trained model.")
    st.stop()

# ==========================================================
# LOAD ACTIVE DATASET (with Year / Month / Shipping Days derived)
# ==========================================================

df, is_uploaded_dataset, active_label = get_prediction_ready_dataset()

compatibility = check_prediction_compatibility(df)

if not compatibility["compatible"]:
    st.info(
        f"🤖 AI Sales Prediction is unavailable for **{active_label}** because the uploaded "
        f"data does not contain the features required by the current prediction model."
    )
    st.caption(
        "Missing feature(s): " + ", ".join(compatibility["missing_features"])
    )
    st.caption(
        "General analytics for this dataset are still available on the Dashboard and "
        "Sales Analysis pages."
    )
    st.stop()

if is_uploaded_dataset:
    st.caption(f"Using uploaded dataset: **{active_label}**")

# Order Date is required for the Year selectbox below; guaranteed present
# because it's a prerequisite for Year/Month derivation, and Year is in
# PREDICTION_REQUIRED_FEATURES, so compatibility=True implies it exists.
df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")

# ==========================================================
# PREDICTION INPUTS
# ==========================================================

st.markdown("## Prediction Inputs")

st.caption(
    """
Provide business details below to estimate future sales using the trained
Machine Learning model.
"""
)

left, right = st.columns(2)

with left:

    category = st.selectbox("Category", sorted(df["Category"].dropna().unique()))
    sub_category = st.selectbox("Sub-Category", sorted(df["Sub-Category"].dropna().unique()))
    ship_mode = st.selectbox("Ship Mode", sorted(df["Ship Mode"].dropna().unique()))
    region = st.selectbox("Region", sorted(df["Region"].dropna().unique()))
    state = st.selectbox("State", sorted(df["State"].dropna().unique()))
    segment = st.selectbox("Customer Segment", sorted(df["Segment"].dropna().unique()))

with right:

    quantity = st.number_input("Quantity", min_value=1, max_value=20, value=3)
    discount = st.slider("Discount", min_value=0.0, max_value=0.80, value=0.20, step=0.01)
    profit = st.number_input("Expected Profit ($)", value=50.0, step=10.0)

    year_options = sorted(df["Order Date"].dropna().dt.year.unique())
    year = st.selectbox("Year", year_options if year_options else [pd.Timestamp.now().year])

    month = st.selectbox("Month", list(range(1, 13)))
    shipping_days = st.slider("Shipping Days", min_value=1, max_value=10, value=4)

st.markdown("")

predict = st.button("Predict Sales", use_container_width=True, type="primary")

st.divider()

# ==========================================================
# SALES PREDICTION
# ==========================================================

if predict:

    input_data = pd.DataFrame({
        "Category": [category],
        "Sub-Category": [sub_category],
        "Ship Mode": [ship_mode],
        "Region": [region],
        "State": [state],
        "Segment": [segment],
        "Quantity": [quantity],
        "Discount": [discount],
        "Profit": [profit],
        "Year": [year],
        "Month": [month],
        "Shipping Days": [shipping_days]
    })

    predicted_sales = model.predict(input_data)[0]

    # ==========================================================
    # SALES CLASSIFICATION
    # ==========================================================

    if predicted_sales >= 1000:
        revenue_level = "🟢 Premium Revenue Opportunity"
    elif predicted_sales >= 500:
        revenue_level = "🔵 High Revenue Opportunity"
    elif predicted_sales >= 200:
        revenue_level = "🟡 Medium Revenue Opportunity"
    else:
        revenue_level = "🔴 Low Revenue Opportunity"

    # ==========================================================
    # SAVE PREDICTION TO DATABASE
    # ==========================================================

    save_prediction(
        category=category,
        sub_category=sub_category,
        region=region,
        state=state,
        segment=segment,
        quantity=quantity,
        discount=discount,
        expected_profit=profit,
        predicted_sales=predicted_sales,
        revenue_level=revenue_level,
        dataset_filename=active_label,
    )

    st.success("Prediction saved successfully!")

    # ==========================================================
    # HERO RESULT CARD
    # ==========================================================

    st.markdown("## Prediction Result")
    st.markdown("## 📊 Business Impact Dashboard")

    # ----------------------------------------------------------
    # Historical Benchmarks (from the ACTIVE dataset)
    # ----------------------------------------------------------

    avg_sales = df["Sales"].mean()
    avg_profit = df["Profit"].mean()
    avg_discount = df["Discount"].mean()
    avg_quantity = df["Quantity"].mean()

    best_region = df.groupby("Region")["Sales"].sum().idxmax()

    segment_share = df.groupby("Segment")["Sales"].sum().loc[segment]
    total_segment_sales = df.groupby("Segment")["Sales"].sum().sum()
    segment_percentage = (segment_share / total_segment_sales) * 100 if total_segment_sales else 0

    revenue_status = "🟢 Above Average" if predicted_sales >= avg_sales else "🟡 Below Average"
    profit_status = "🟢 Strong" if profit >= avg_profit else "🟡 Moderate"
    discount_status = "🟢 Healthy" if discount <= avg_discount else "🟡 High"
    quantity_status = "🟢 Large Order" if quantity >= avg_quantity else "🟡 Small Order"
    region_status = "🟢 Best Performing" if region == best_region else "🟡 Average Region"
    segment_status = "🟢 High Value" if segment_percentage >= 30 else "🟡 Moderate Value"

    impact_df = pd.DataFrame({
        "Business Question": [
            "Expected Revenue", "Expected Profit", "Discount",
            "Quantity", "Target Region", "Customer Segment"
        ],
        "Current Value": [
            f"${predicted_sales:,.2f}", f"${profit:,.2f}", f"{discount:.1%}",
            quantity, region, segment
        ],
        "Historical Benchmark": [
            f"${avg_sales:,.2f}", f"${avg_profit:,.2f}", f"{avg_discount:.1%}",
            f"{avg_quantity:.1f}", best_region, f"{segment_percentage:.1f}% Sales Share"
        ],
        "Business Insight": [
            revenue_status, profit_status, discount_status,
            quantity_status, region_status, segment_status
        ]
    })

    st.dataframe(impact_df, use_container_width=True, hide_index=True)

    st.divider()

    # ==========================================================
    # PERFORMANCE COMPARISON
    # ==========================================================

    st.markdown("## 📈 Performance Comparison")

    revenue_change = ((predicted_sales - avg_sales) / avg_sales) * 100 if avg_sales else 0
    profit_change = ((profit - avg_profit) / avg_profit) * 100 if avg_profit else 0
    discount_change = ((discount - avg_discount) / avg_discount) * 100 if avg_discount else 0
    quantity_change = ((quantity - avg_quantity) / avg_quantity) * 100 if avg_quantity else 0

    row = st.columns(4)

    comparisons = [
        ("Revenue", f"${predicted_sales:,.0f}", f"${avg_sales:,.0f}", revenue_change, True),
        ("Profit", f"${profit:,.0f}", f"${avg_profit:,.0f}", profit_change, True),
        ("Discount", f"{discount:.1%}", f"{avg_discount:.1%}", discount_change, False),
        ("Quantity", f"{quantity}", f"{avg_quantity:.1f}", quantity_change, True)
    ]

    for col, item in zip(row, comparisons):
        title, current, average, change, higher_is_better = item

        if higher_is_better:
            indicator, color = ("▲", "green") if change >= 0 else ("▼", "red")
        else:
            indicator, color = ("▼", "green") if change <= 0 else ("▲", "red")

        with col:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.metric("Current", current)
                st.caption(f"Historical Avg: {average}")
                st.markdown(
                    f"<p style='color:{color};font-weight:bold;'>"
                    f"{indicator} {abs(change):.1f}% vs Average</p>",
                    unsafe_allow_html=True
                )

    # ==========================================================
    # FUTURE GROWTH OPPORTUNITIES
    # ==========================================================

    st.markdown("## 📈 Future Growth Opportunities")

    category_profit = df.groupby("Category")["Profit"].mean()
    best_category = category_profit.idxmax()

    region_profit = df.groupby("Region")["Profit"].mean()
    best_region = region_profit.idxmax()

    growth_df = df.groupby(["Category", "Region"])[["Sales", "Profit"]].mean().reset_index()
    best_growth = growth_df.loc[growth_df["Profit"].idxmax()]

    g1, g2 = st.columns(2)

    with g1:
        with st.container(border=True):
            st.markdown("### Highest Growth Category")
            st.metric("Category", best_category)
            st.caption("Historically generates the highest average profit.")

    with g2:
        with st.container(border=True):
            st.markdown("### Strongest Growth Region")
            st.metric("Region", best_region)
            st.caption("Consistently delivers the highest average profitability.")

    with st.container(border=True):
        st.markdown("### Best Expansion Opportunity")
        st.write(
            f"""
Historical analysis indicates that expanding **{best_growth['Category']}**
products in the **{best_growth['Region']}** region has the strongest
potential for increasing future profitability.

Average Sales

**${best_growth['Sales']:,.2f}**

Average Profit

**${best_growth['Profit']:,.2f}**
"""
        )

    st.divider()

    # ==========================================================
    # PROFIT RISK FORECAST
    # ==========================================================

    st.markdown("## 📉 Profit Risk Forecast")

    risky_orders = df[df["Profit"] < 0]

    if not risky_orders.empty:

        risky_category = risky_orders.groupby("Category")["Profit"].count().idxmax()
        risky_region = risky_orders.groupby("Region")["Profit"].count().idxmax()
        avg_loss_discount = risky_orders["Discount"].mean()

        r1, r2 = st.columns(2)

        with r1:
            with st.container(border=True):
                st.markdown("### Highest Risk Category")
                st.metric("Category", risky_category)
                st.caption("Historically records the largest number of loss-making orders.")

        with r2:
            with st.container(border=True):
                st.markdown("### Highest Risk Region")
                st.metric("Region", risky_region)
                st.caption("Requires closer monitoring due to frequent low-profit transactions.")

        with st.container(border=True):
            st.markdown("### Profit Risk Insight")
            st.warning(
                f"""
Historical data shows that orders with discounts around
**{avg_loss_discount:.1%}**
are more likely to generate losses.

Maintaining discount levels below this threshold may improve
overall profitability.
"""
            )
    else:
        st.success("No loss-making orders found in the active dataset's history.")

    st.divider()

    # ==========================================================
    # BUSINESS SCENARIO SIMULATOR
    # ==========================================================

    st.markdown("## 📊 Business Scenario Simulator")

    st.caption(
        """
The following projections estimate potential business impact using
historical average performance. These values are indicative and intended
to support business planning.
"""
    )

    projected_sales = predicted_sales * 1.10
    projected_profit = profit * 1.08
    projected_orders = quantity * 1.15

    additional_revenue = projected_sales - predicted_sales
    additional_profit = projected_profit - profit

    s1, s2, s3 = st.columns(3)

    with s1:
        with st.container(border=True):
            st.metric("Projected Revenue", f"${projected_sales:,.2f}", delta=f"+${additional_revenue:,.2f}")

    with s2:
        with st.container(border=True):
            st.metric("Projected Profit", f"${projected_profit:,.2f}", delta=f"+${additional_profit:,.2f}")

    with s3:
        with st.container(border=True):
            st.metric("Projected Order Size", f"{projected_orders:.0f}", delta=f"+{projected_orders-quantity:.0f}")

    with st.container(border=True):
        st.markdown("### Business Projection")
        st.info(
            f"""
Historical performance indicates that increasing focus on
**{best_growth['Category']}** within the **{best_growth['Region']}**
region could improve future business performance.

Estimated Revenue Opportunity

**+${additional_revenue:,.2f}**

Estimated Profit Opportunity

**+${additional_profit:,.2f}**

These estimates are based on historical averages and should
be interpreted as planning guidance rather than guaranteed outcomes.
"""
        )

    st.divider()
import streamlit as st


# ==========================================================
# LOAD CSS
# ==========================================================

def load_css(file_name):

    with open(file_name, encoding="utf-8") as f:

        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )


# ==========================================================
# DASHBOARD HEADER
# ==========================================================

def dashboard_header():

    st.title("📊 BusinessIQ Dashboard")

    st.caption(
        "Sales Intelligence Platform | Monitor business performance and generate AI-powered insights."
    )

    st.divider()


# ==========================================================
# KPI CARD
# ==========================================================

def metric_card(title, value, icon):

    st.markdown(
        f"""
<div class="metric-card">

    <div class="metric-icon">
        {icon}
    </div>

    <div class="metric-title">
        {title}
    </div>

    <div class="metric-value">
        {value}
    </div>

</div>
""",
        unsafe_allow_html=True,
    )


# ==========================================================
# SECTION TITLE
# ==========================================================

def section_title(title):

    st.markdown(
        f"""
<div class="section-title">

{title}

</div>
""",
        unsafe_allow_html=True,
    )
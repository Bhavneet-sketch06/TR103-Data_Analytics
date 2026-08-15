import streamlit as st
import pandas as pd
from pathlib import Path

from utils.data_cleaner import clean_dataset, check_prediction_compatibility
from utils.data_loader import (
    set_active_dataset,
    get_active_dataset,
    get_cleaning_report,
    get_prediction_compatibility,
    get_upload_time,
    derive_prediction_features,
)

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="InsightSphere",
    page_icon="🧭",
    layout="wide"
)


# ==========================================================
# LOAD CUSTOM CSS
# ==========================================================

def load_css(css_path: str) -> None:
    """Injects the external stylesheet into the page."""
    css_file = Path(css_path)
    if css_file.exists():
        st.markdown(f"<style>{css_file.read_text()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"Stylesheet not found at: {css_path}")


_CSS_PATH = Path(__file__).parent / "home.css"
load_css(str(_CSS_PATH))


# ==========================================================
# HELPERS
# ==========================================================

def format_bytes(num_bytes: float) -> str:
    """Human-readable memory size."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:,.2f} {unit}"
        size /= 1024
    return f"{size:,.2f} TB"


def compute_dataset_summary(df: pd.DataFrame, filename: str, upload_time: str) -> dict:
    """Derives the Dataset Summary KPI values from the active dataframe."""
    rows, cols = df.shape
    missing_values = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    memory_usage = df.memory_usage(deep=True).sum()

    return {
        "filename": filename,
        "rows": rows,
        "cols": cols,
        "missing_values": missing_values,
        "duplicate_rows": duplicate_rows,
        "memory_usage": format_bytes(memory_usage),
        "upload_time": upload_time,
    }


def badge_html(label: str, level: str) -> str:
    """Returns a colored pill badge. level: 'green' | 'yellow' | 'red'."""
    icons = {"green": "✔", "yellow": "⚠", "red": "✖"}
    return f'<span class="is-badge is-badge-{level}">{icons.get(level, "•")} {label}</span>'


def evaluate_dataset_health(df: pd.DataFrame) -> list:
    """
    Evaluates dataset health and returns a list of (label, level) badges.
    level: 'green' (good), 'yellow' (needs cleaning), 'red' (major issues).
    """
    rows, cols = df.shape
    total_cells = max(rows * cols, 1)

    missing_count = int(df.isna().sum().sum())
    missing_pct = missing_count / total_cells

    duplicate_count = int(df.duplicated().sum())
    duplicate_pct = (duplicate_count / rows) if rows > 0 else 0

    completeness_pct = 1 - missing_pct

    badges = []

    if missing_count == 0:
        badges.append(("No Missing Values", "green"))
    elif missing_pct <= 0.05:
        badges.append(("Some Missing Values", "yellow"))
    else:
        badges.append(("High Missing Values", "red"))

    if duplicate_count == 0:
        badges.append(("Zero Duplicates", "green"))
    elif duplicate_pct <= 0.05:
        badges.append(("Some Duplicates", "yellow"))
    else:
        badges.append(("High Duplicates", "red"))

    if completeness_pct >= 0.98:
        badges.append(("Excellent Completeness", "green"))
    elif completeness_pct >= 0.90:
        badges.append(("Good Completeness", "yellow"))
    else:
        badges.append(("Low Completeness", "red"))

    levels = [lvl for _, lvl in badges]
    if "red" in levels:
        overall = ("Major Issues", "red")
    elif "yellow" in levels:
        overall = ("Needs Cleaning", "yellow")
    else:
        overall = ("Ready for Analysis", "green")

    return [overall] + badges


# ==========================================================
# HERO SECTION
# ==========================================================

st.markdown(
    """
    <div class="is-hero">
        <p class="is-hero-title">InsightSphere</p>
        <p class="is-hero-tagline">
            "An AI-powered Business Intelligence platform for sales analytics and forecasting."
        </p>
        <p class="is-hero-intro">
            InsightSphere transforms raw sales datasets into meaningful business insights through
            interactive dashboards, advanced analytics, and machine-learning powered sales forecasting.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# DATASET UPLOAD
# ==========================================================

st.markdown('<p class="is-section-title">Upload Sales Dataset</p>', unsafe_allow_html=True)

upload_card = st.container(border=True)

with upload_card:

    st.markdown('<span class="is-upload-marker"></span>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload your sales CSV file below",
        type=["csv"],
        label_visibility="visible"
    )

    st.markdown(
        '<p class="is-upload-caption">'
        'Supported Format: CSV &nbsp;|&nbsp; '
        'Maximum recommended size: 200 MB'
        '</p>',
        unsafe_allow_html=True
    )

# ==========================================================
# PROCESS UPLOADED DATASET
# ==========================================================

if uploaded_file is not None:

    try:

        encodings = ["utf-8", "latin1", "cp1252", "ISO-8859-1"]
        new_df = None
        detected_encoding = None

        for encoding in encodings:
            try:
                uploaded_file.seek(0)
                new_df = pd.read_csv(uploaded_file, encoding=encoding)
                detected_encoding = encoding
                break
            except Exception:
                continue

        if new_df is None:
            raise ValueError(
                "Unable to read this file with any supported encoding "
                "(utf-8, latin1, cp1252, ISO-8859-1)."
            )

        if new_df.shape[1] == 0 or new_df.shape[0] == 0:
            raise ValueError("The uploaded CSV appears to be empty.")

        # ------------------------------------------------------
        # AUTOMATIC DATA CLEANING
        # ------------------------------------------------------

        cleaned_df, cleaning_report_result = clean_dataset(new_df)

        # ------------------------------------------------------
        # DERIVE PREDICTION-SUPPORT FEATURES (Year / Month / Shipping Days)
        # Same logic your other pages already use to derive these from
        # Order Date / Ship Date -- never fabricated, just date math.
        # ------------------------------------------------------

        enriched_df = derive_prediction_features(cleaned_df)

        # ------------------------------------------------------
        # CHECK PREDICTION MODEL COMPATIBILITY
        # ------------------------------------------------------

        prediction_compatibility_result = check_prediction_compatibility(enriched_df)

        # ------------------------------------------------------
        # SAVE AS THE ACTIVE DATASET (single centralized mechanism)
        # ------------------------------------------------------

        set_active_dataset(
            df=enriched_df,
            filename=uploaded_file.name,
            cleaning_report=cleaning_report_result,
            prediction_compatibility=prediction_compatibility_result,
        )

        st.markdown(
            f"""
            <div class="is-upload-success">
                ✅ <b>{uploaded_file.name}</b> uploaded and processed successfully.
                <br>
                Detected Encoding: <b>{detected_encoding}</b>
            </div>
            """,
            unsafe_allow_html=True
        )

    except Exception as e:
        st.error(f"Could not read this CSV file.\n\nDetails:\n{e}")


# ==========================================================
# DATASET PROCESSING SUMMARY
# ==========================================================

st.markdown('<p class="is-section-title">Dataset Processing</p>', unsafe_allow_html=True)

cleaning_report = get_cleaning_report()
prediction_compatibility = get_prediction_compatibility()

if cleaning_report is not None:

    st.caption("Your uploaded dataset has been automatically checked and cleaned for analysis.")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric(
            "Records",
            f"{cleaning_report['cleaned_rows']:,}",
            delta=f"-{cleaning_report['duplicates_removed']:,} duplicates"
        )

    with metric_col2:
        st.metric(
            "Missing Values",
            f"{cleaning_report['final_missing_values']:,}",
            delta=f"-{cleaning_report['missing_values_handled']:,} handled"
        )

    with metric_col3:
        st.metric("Columns", f"{cleaning_report['cleaned_cols']:,}")

    with metric_col4:
        st.metric(
            "Data Quality",
            "Ready" if cleaning_report["final_missing_values"] == 0 else "Review"
        )

    if cleaning_report["final_missing_values"] == 0:
        st.success("✓ Dataset cleaned successfully and is ready for analysis.")
    else:
        st.warning("⚠ Dataset was cleaned, but some missing values still require review.")

    if prediction_compatibility and prediction_compatibility.get("compatible"):
        st.info(
            "🤖 AI Sales Prediction: This dataset contains all features required by the "
            "current sales prediction model."
        )
    elif prediction_compatibility:
        st.info(
            "🤖 AI Sales Prediction: This uploaded dataset can be used for general analysis, "
            "but it does not match the feature structure of the current sales prediction model."
        )
        st.caption("The prediction model currently expects the feature structure used during its training.")

else:
    st.caption("No dataset uploaded yet — the default sample dataset is active across the platform.")
    st.markdown(
        """
        <div class="is-info-banner">
            ℹ️ Upload a CSV above to replace the sample dataset. Once uploaded, it automatically
            becomes the active dataset for the Dashboard, Sales Analysis, AI Sales Prediction,
            and Prediction History pages.
        </div>
        """,
        unsafe_allow_html=True
    )


# ==========================================================
# DATASET SUMMARY + HEALTH (only for an uploaded active dataset)
# ==========================================================

active_df, is_uploaded, active_label = get_active_dataset()

if is_uploaded:

    summary = compute_dataset_summary(active_df, active_label, get_upload_time())

    st.markdown('<div class="is-section-spacer"></div>', unsafe_allow_html=True)
    st.markdown('<p class="is-section-title">Dataset Summary</p>', unsafe_allow_html=True)

    kpi_specs = [
        ("📄", "File Name", summary["filename"]),
        ("📊", "Total Rows", f"{summary['rows']:,}"),
        ("📁", "Total Columns", f"{summary['cols']:,}"),
        ("⚠️", "Missing Values", f"{summary['missing_values']:,}"),
        ("🧬", "Duplicate Rows", f"{summary['duplicate_rows']:,}"),
        ("💾", "Memory Usage", summary["memory_usage"]),
        ("🕒", "Uploaded", summary["upload_time"]),
    ]

    kpi_cols = st.columns(len(kpi_specs))
    for col, (icon, label, value) in zip(kpi_cols, kpi_specs):
        with col:
            st.markdown(
                f"""
                <div class="is-kpi-card">
                    <div class="is-kpi-label-row">
                        <span class="is-kpi-icon">{icon}</span>
                        <span class="is-kpi-label">{label}</span>
                    </div>
                    <div class="is-kpi-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown('<div class="is-section-spacer"></div>', unsafe_allow_html=True)

    health_badges = evaluate_dataset_health(active_df)
    badges_html = "".join(badge_html(label, level) for label, level in health_badges)

    st.markdown(
        f"""
        <div class="is-health-card">
            <p class="is-section-title" style="margin-bottom:4px;">Dataset Health</p>
            <div class="is-badge-row">{badges_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

else:
    st.markdown(
        """
        <div class="is-info-banner">
            ℹ️ No dataset has been uploaded yet. Your existing sample/default dataset will
            continue to be used across the Dashboard, Sales Analysis, and AI Sales Prediction pages
            until a new file is uploaded here.
        </div>
        """,
        unsafe_allow_html=True
    )


# ==========================================================
# PLATFORM MODULES
# ==========================================================

st.markdown('<div class="is-section-spacer"></div>', unsafe_allow_html=True)
st.markdown('<p class="is-section-title">Platform Modules</p>', unsafe_allow_html=True)

modules = [
    {
        "icon": "📊",
        "title": "Dashboard",
        "desc": "Executive KPIs, revenue overview, and high-level performance indicators.",
        "page": "pages/1_Dashboard.py",
    },
    {
        "icon": "📈",
        "title": "Sales Analysis",
        "desc": "In-depth seasonal trends, category breakdown, and regional insights.",
        "page": "pages/2_Sales_Analysis.py",
    },
    {
        "icon": "🤖",
        "title": "AI Sales Prediction",
        "desc": "Machine learning models for demand forecasting and revenue estimation.",
        "page": "pages/3_AI_Sales_Prediction.py",
    },
    {
        "icon": "📜",
        "title": "Prediction History",
        "desc": "SQLite-backed historical log of previous forecasts and model runs.",
        "page": "pages/4_Prediction_History.py",
    },
]

module_cols = st.columns(4)
for col, module in zip(module_cols, modules):
    with col:
        module_card = st.container(border=True)
        with module_card:
            st.markdown(
                f"""
                <div class="is-module-icon">{module['icon']}</div>
                <p class="is-module-title">{module['title']}</p>
                <p class="is-module-desc">{module['desc']}</p>
                """,
                unsafe_allow_html=True
            )
            try:
                st.page_link(module["page"], label="Open →")
            except Exception:
                st.caption("Update page path in app.py")


# ==========================================================
# QUICK WORKFLOW
# ==========================================================

st.markdown('<div class="is-section-spacer"></div>', unsafe_allow_html=True)
st.markdown('<p class="is-section-title">Quick Workflow</p>', unsafe_allow_html=True)

workflow_steps = [
    ("⬆️", "Upload Dataset", "Bring in your raw sales CSV file."),
    ("📊", "Dashboard", "Review executive KPIs and trends."),
    ("📈", "Sales Analysis", "Explore category and regional insights."),
    ("🤖", "AI Sales Prediction", "Forecast future sales with ML."),
    ("📜", "Prediction History", "Track and audit past forecasts."),
]

workflow_cols = st.columns([2, 0.4, 2, 0.4, 2, 0.4, 2, 0.4, 2])
step_idx = 0
for i, col in enumerate(workflow_cols):
    with col:
        if i % 2 == 0:
            icon, title, desc = workflow_steps[step_idx]
            step_card = st.container(border=True)
            with step_card:
                st.markdown(
                    f"""
                    <div class="is-workflow-icon">{icon}</div>
                    <p class="is-workflow-title">{title}</p>
                    <p class="is-workflow-desc">{desc}</p>
                    """,
                    unsafe_allow_html=True
                )
            step_idx += 1
        else:
            st.markdown('<div class="is-workflow-arrow">→</div>', unsafe_allow_html=True)


# ==========================================================
# ABOUT INSIGHTSPHERE
# ==========================================================

st.markdown('<div class="is-section-spacer"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="is-about-card">
        <p class="is-about-title">About InsightSphere</p>
        <p class="is-about-text">
            InsightSphere is an AI-powered Business Intelligence platform built using Python,
            Streamlit, SQLite, Pandas, and Machine Learning. It enables organizations to:
        </p>
        <ul class="is-about-list">
            <li>Discover hidden sales trends</li>
            <li>Monitor business performance</li>
            <li>Forecast future sales</li>
            <li>Analyze categories and regions</li>
            <li>Store prediction history</li>
            <li>Support executive decision making</li>
        </ul>
    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# FOOTER
# ==========================================================

st.markdown(
    """
    <div class="is-footer">
        <p class="is-footer-title">InsightSphere &nbsp;•&nbsp; Version 1.0</p>
        <p class="is-footer-sub">Built with Python • Streamlit • Machine Learning • SQLite</p>
    </div>
    """,
    unsafe_allow_html=True
)
import streamlit as st
import pandas as pd
from pathlib import Path
import html as html_lib

from utils.database import load_history

# Optional: only used by the Clear History action below.
# If your utils/database.py does not yet have this function, add one that
# performs the DELETE / TRUNCATE against your predictions table.
# The import is wrapped so the page still runs even if it's missing.
try:
    from utils.database import clear_history
    _CLEAR_HISTORY_AVAILABLE = True
except ImportError:
    _CLEAR_HISTORY_AVAILABLE = False


# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Prediction History",
    page_icon="📜",
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


# Resolved relative to THIS script's folder, not the app's working directory,
# so it works no matter where `streamlit run` is launched from.
_CSS_PATH = Path(__file__).parent / "prediction_history_style.css"
load_css(str(_CSS_PATH))


# ==========================================================
# LOAD DATABASE  (unchanged)
# ==========================================================

history_df = load_history()


# ==========================================================
# PAGE HEADER
# ==========================================================

st.markdown(
    """
    <div class="ph-header-wrap">
        <div class="ph-header-icon">📄</div>
        <div>
            <p class="ph-header-title">Prediction History</p>
            <p class="ph-header-subtitle">
                Review and manage all AI-generated sales predictions in one centralized location.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="ph-section-spacer"></div>', unsafe_allow_html=True)


# ==========================================================
# EXECUTIVE KPI CARDS  (calculation logic unchanged)
# ==========================================================

if history_df.empty:

    total_predictions = 0
    avg_prediction = 0
    highest_prediction = 0
    latest_prediction = "-"

else:

    total_predictions = len(history_df)

    avg_prediction = history_df["predicted_sales"].mean()

    highest_prediction = history_df["predicted_sales"].max()

    latest_prediction = history_df.iloc[-1]["prediction_time"]


def kpi_card(icon: str, label: str, value: str) -> str:
    """Returns the HTML markup for a single KPI card."""
    return f"""
    <div class="ph-kpi-card">
        <div class="ph-kpi-label-row">
            <div class="ph-kpi-icon">{icon}</div>
            <div class="ph-kpi-label">{label}</div>
        </div>
        <div class="ph-kpi-value">{value}</div>
    </div>
    """


k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(
        kpi_card("👥", "Total Predictions", f"{total_predictions:,}"),
        unsafe_allow_html=True
    )

with k2:
    st.markdown(
        kpi_card("📈", "Average Predicted Sales", f"${avg_prediction:,.0f}"),
        unsafe_allow_html=True
    )

with k3:
    st.markdown(
        kpi_card("🏆", "Highest Prediction", f"${highest_prediction:,.0f}"),
        unsafe_allow_html=True
    )

with k4:
    st.markdown(
        kpi_card("🗓️", "Latest Prediction", f"{latest_prediction}"),
        unsafe_allow_html=True
    )

st.markdown('<div class="ph-section-spacer"></div>', unsafe_allow_html=True)


# ==========================================================
# PREDICTION RECORDS CARD (header + actions)
# ==========================================================
# Everything below lives inside ONE real Streamlit bordered container,
# so the title, action buttons, and table are genuinely nested together
# (rather than separate HTML divs that don't actually contain each other).

records_container = st.container(border=True)

with records_container:
    title_col, action_col = st.columns([3, 1.4])

    with title_col:
        st.markdown(
            """
            <p class="ph-records-title">Prediction Records</p>
            <p class="ph-records-subtitle">
                Browse every AI prediction along with the business inputs used during forecasting.
            </p>
            """,
            unsafe_allow_html=True
        )

    with action_col:
        btn_col1, btn_col2 = st.columns(2)

        # ---- Export CSV (existing export logic, same source data) ----
        with btn_col1:
            csv_bytes = history_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Export CSV",
                data=csv_bytes,
                file_name="prediction_history.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=history_df.empty
            )

        # ---- Clear History (with confirmation) ----
        with btn_col2:
            with st.popover("🗑️ Clear History", use_container_width=True, disabled=history_df.empty):
                st.warning("You are about to permanently delete all prediction history. This cannot be undone.")
                confirm_col1, confirm_col2 = st.columns(2)
                with confirm_col1:
                    cancel_clicked = st.button("Cancel", use_container_width=True, key="ph_cancel_clear")
                with confirm_col2:
                    delete_clicked = st.button("Delete", type="primary", use_container_width=True, key="ph_confirm_clear")

                if delete_clicked:
                    if _CLEAR_HISTORY_AVAILABLE:
                        clear_history()  # existing/implemented backend function
                        st.success("Prediction history cleared.")
                        st.rerun()
                    else:
                        st.error(
                            "clear_history() was not found in utils/database.py. "
                            "Add a function that deletes all rows from your predictions table, "
                            "then this button will work automatically."
                        )

    # ======================================================
    # PREDICTION HISTORY TABLE  (data prep logic unchanged)
    # ======================================================

    if not history_df.empty:

        history_display = history_df.copy()

        # Rename columns for presentation
        history_display = history_display.rename(
            columns={
                "prediction_time": "Prediction Time",
                "category": "Category",
                "sub_category": "Sub-Category",
                "region": "Region",
                "state": "State",
                "segment": "Customer Segment",
                "quantity": "Quantity",
                "discount": "Discount",
                "expected_profit": "Expected Profit",
                "predicted_sales": "Predicted Sales",
                "revenue_level": "Revenue Level",
                "dataset_filename": "Dataset",
            }
        )

        # Formatting
        history_display["Discount"] = (
            history_display["Discount"] * 100
        ).round(1).astype(str) + "%"

        history_display["Expected Profit"] = (
            "$" +
            history_display["Expected Profit"]
            .round(2)
            .astype(str)
        )

        history_display["Predicted Sales"] = (
            "$" +
            history_display["Predicted Sales"]
            .round(2)
            .astype(str)
        )

        # ---------- Revenue Level -> pill badge (display only) ----------
        def revenue_badge(value) -> str:
            text = str(value).strip()
            key = text.lower()
            if "high" in key:
                css_class, dot = "ph-badge-high", "🟢"
            elif "medium" in key or "med" in key:
                css_class, dot = "ph-badge-medium", "🟡"
            elif "low" in key:
                css_class, dot = "ph-badge-low", "🔴"
            else:
                css_class, dot = "ph-badge-medium", "⚪"
            return f'<span class="ph-badge {css_class}">{dot} {html_lib.escape(text)}</span>'

        if "Revenue Level" in history_display.columns:
            history_display["Revenue Level"] = history_display["Revenue Level"].apply(revenue_badge)

        # ---------- Build premium HTML table ----------
        columns = history_display.columns.tolist()

        header_html = "".join(f"<th>{html_lib.escape(str(col))}</th>" for col in columns)

        rows_html = ""
        for _, row in history_display.iterrows():
            cells = ""
            for col in columns:
                value = row[col]
                if col == "Revenue Level":
                    cells += f"<td>{value}</td>"  # already-escaped badge HTML
                else:
                    cells += f"<td>{html_lib.escape(str(value))}</td>"
            rows_html += f"<tr>{cells}</tr>"

        table_html = f"""
        <div class="ph-table-wrap">
            <table class="ph-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """

        st.markdown(table_html, unsafe_allow_html=True)


# ==========================================================
# EMPTY DATABASE MESSAGE  (unchanged)
# ==========================================================

if history_df.empty:

    st.info(
        """
No prediction history available yet.

Generate your first prediction from the AI Sales Prediction page.

Once predictions are generated, this page will automatically display:

• Historical prediction records

• Business trend analysis

• Revenue insights

• Exportable reports
"""
    )

    st.stop()
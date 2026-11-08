"""Data: upload, map columns, review data health, explore and set targets."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core import db, state
from core.schema import FIELDS, FIELD_BY_KEY
from ui import components as ui
from ui import shell, upload
from ui.charts import compact

dataset = state.get_dataset()
df = dataset.df

shell.header("Data", "Upload a sales file, map its columns, and check its health.")
st.space("small")


# ==========================================================
# 1. SOURCE
# ==========================================================

src_col, info_col = st.columns([1.4, 1], gap="medium")

with src_col:
    with ui.card("upload", "Upload a dataset", "CSV or Excel, one row per order line. Up to 200 MB."):
        uploaded = upload.file_picker("data")

with info_col:
    with ui.card("active", "Active dataset"):
        ui.dataset_chip(dataset.name, len(df), dataset.date_span, dataset.is_sample)
        st.space("xsmall")
        if not dataset.is_sample:
            if st.button("Switch to sample data", icon=":material/undo:", width="stretch"):
                state.use_sample()
                st.rerun()
        else:
            st.caption("Upload your own file to replace the sample across every page.")

# ==========================================================
# 2. MAP COLUMNS (only while an upload is pending)
# ==========================================================

if uploaded is not None:
    st.space("small")

    def _done(name: str) -> None:
        st.toast(f"{name} is now active across all pages.", icon=":material/check_circle:")
        st.rerun()

    upload.mapping_step(uploaded, "data", on_done=_done)
    st.stop()


# ==========================================================
# 3. REVIEW: HEALTH
# ==========================================================

report = dataset.report
st.space("small")

total_cells = max(df.shape[0] * df.shape[1], 1)
missing_cells = int(df.isna().sum().sum())
completeness = 1 - missing_cells / total_cells

h1, h2, h3, h4, h5 = st.columns(5)
with h1:
    ui.kpi_tile("Rows analysed", f"{len(df):,}", period=f"of {report.get('original_rows', len(df)):,} in file")
with h2:
    months = df["order_date"].dt.to_period("M").nunique()
    ui.kpi_tile("History", f"{months} months", period=dataset.date_span)
with h3:
    ui.kpi_tile("Completeness", f"{completeness:.1%}", period=f"{missing_cells:,} empty cells")
with h4:
    ui.kpi_tile("Duplicates removed", f"{report.get('duplicates_removed', 0):,}", period="exact duplicate rows")
with h5:
    mapped_count = sum(1 for v in dataset.mapping.values() if v)
    ui.kpi_tile("Fields mapped", f"{mapped_count} / {len(FIELDS)}", period="more fields → more views")

st.space("small")
left, right = st.columns([1, 1.25], gap="medium")

with left:
    with ui.card("health", "Data health", "What the automatic clean-up found and changed."):
        items = []
        dropped = report.get("rows_dropped_no_date", 0) + report.get("rows_dropped_no_revenue", 0)
        items.append({
            "tone": "good" if dropped == 0 else "warn",
            "title": "Every row has a date and revenue" if dropped == 0 else f"{dropped:,} rows skipped",
            "body": "Rows need an order date and a revenue value to be analysed."
                    if dropped == 0 else "They had no valid order date or revenue, so they can't be placed on a timeline.",
        })
        items.append({
            "tone": "good" if report.get("duplicates_removed", 0) == 0 else "info",
            "title": "No duplicate rows" if report.get("duplicates_removed", 0) == 0
                     else f"{report['duplicates_removed']:,} duplicate rows removed",
            "body": "Exact duplicates are removed so totals aren't double counted.",
        })
        numeric_missing = int(df.select_dtypes("number").isna().sum().sum())
        items.append({
            "tone": "good" if numeric_missing == 0 else "warn",
            "title": "No missing numbers" if numeric_missing == 0 else f"{numeric_missing:,} missing numeric values",
            "body": "Missing numbers are left empty, never guessed, so totals only include real values.",
        })
        if report.get("missing_values_handled"):
            items.append({
                "tone": "info",
                "title": f"{report['missing_values_handled']:,} empty labels set to “Unknown”",
                "body": "Keeps those rows visible in category and region breakdowns.",
            })
        for note in report.get("derived", []):
            items.append({"tone": "info", "title": note, "body": ""})
        ui.item_list(items)

with right:
    with ui.card("mapping-summary", "Column mapping", "How your file's columns feed the dashboard."):
        rows = [
            {"Field": f.label, "Your column": dataset.mapping.get(f.key) or "—",
             "Status": "Mapped" if dataset.mapping.get(f.key) else ("Derived" if f.key in df.columns else "Not mapped")}
            for f in FIELDS
        ]
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, width="stretch", height=360,
            column_config={"Status": st.column_config.TextColumn(width="small")},
        )

# ==========================================================
# 4. EXPLORER
# ==========================================================

st.space("small")
with ui.card("explorer", "Explore rows", "Search, sort and export the cleaned data."):
    search = st.text_input("Search", placeholder="Search any text column…", label_visibility="collapsed",
                           icon=":material/search:")
    view = df
    if search:
        text_cols = [c for c in df.columns if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object]
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            mask |= df[col].astype(str).str.contains(search, case=False, regex=False, na=False)
        view = df[mask]

    show_cols = [c for c in [f.key for f in FIELDS] if c in view.columns]
    column_config = {
        key: st.column_config.Column(FIELD_BY_KEY[key].label) for key in show_cols
    }
    column_config.update({
        "order_date": st.column_config.DateColumn("Order date", format="MMM D, YYYY"),
        "ship_date": st.column_config.DateColumn("Ship date", format="MMM D, YYYY"),
        "revenue": st.column_config.NumberColumn("Revenue", format="dollar"),
        "profit": st.column_config.NumberColumn("Profit", format="dollar"),
        "cost": st.column_config.NumberColumn("Cost", format="dollar"),
        "discount": st.column_config.NumberColumn("Discount", format="percent"),
    })
    st.dataframe(view[show_cols], hide_index=True, width="stretch", height=380,
                 column_config={k: v for k, v in column_config.items() if k in show_cols})

    c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="center")
    c1.caption(f"{len(view):,} rows")
    c2.download_button(
        "Download CSV", view[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="insightsphere_data.csv", mime="text/csv", icon=":material/download:", width="stretch",
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        view[show_cols].head(200_000).to_excel(writer, index=False, sheet_name="Data")
    c3.download_button(
        "Download Excel", buffer.getvalue(), file_name="insightsphere_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table:", width="stretch",
    )

# ==========================================================
# 5. TARGETS
# ==========================================================

st.space("small")
with ui.card("targets", "Monthly revenue targets",
             "Optional. Targets appear as progress bars on the Overview KPI tiles."):
    last_year = int(df["order_date"].dt.year.max())
    months = pd.period_range(f"{last_year}-01", f"{last_year}-12", freq="M").astype(str)
    actual = (
        df[df["order_date"].dt.year == last_year]
        .groupby(df["order_date"].dt.to_period("M").astype(str))["revenue"].sum()
    )
    saved = db.load_targets(dataset.digest).set_index("month")["revenue_target"]
    editor_df = pd.DataFrame({
        "month": months,
        "actual": [actual.get(m, float("nan")) for m in months],
        "revenue_target": [saved.get(m, float("nan")) for m in months],
    })
    edited = st.data_editor(
        editor_df, hide_index=True, width="stretch", key=f"targets-{dataset.digest}",
        disabled=["month", "actual"],
        column_config={
            "month": st.column_config.TextColumn("Month"),
            "actual": st.column_config.NumberColumn(f"Actual {last_year}", format="dollar"),
            "revenue_target": st.column_config.NumberColumn("Target", format="dollar", min_value=0),
        },
    )
    t1, t2 = st.columns([3, 1], vertical_alignment="center")
    total_target = edited["revenue_target"].sum(skipna=True)
    t1.caption(f"Annual target: {compact(total_target, '$') if total_target else 'not set'}")
    if t2.button("Save targets", type="primary", icon=":material/save:", width="stretch"):
        db.save_targets(dataset.digest, edited[["month", "revenue_target"]])
        st.toast("Targets saved.", icon=":material/check_circle:")

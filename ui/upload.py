"""
Upload and column-mapping flow, shared by the Home and Data pages.

    uploaded = upload.file_picker("home")
    if uploaded is not None:
        upload.mapping_step(uploaded, "home", on_done=...)
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from core import ingest, state
from core.schema import FIELDS, suggest_mapping, validate_mapping
from ui import components as ui

TYPES = ["csv", "xlsx", "xls"]


def _nonce_key(key: str) -> str:
    return f"_upload-nonce-{key}"


def file_picker(key: str):
    """The file drop zone. Bumping its nonce (after use or cancel) clears it."""
    nonce = st.session_state.setdefault(_nonce_key(key), 0)
    return st.file_uploader("Sales file", type=TYPES, key=f"upload-{key}-{nonce}",
                            label_visibility="collapsed")


def clear(key: str) -> None:
    st.session_state[_nonce_key(key)] = st.session_state.get(_nonce_key(key), 0) + 1


def mapping_step(uploaded, key: str, *, on_done: Callable[[str], None]) -> None:
    """
    Stepper + mapping editor for a freshly uploaded file. Fields are
    pre-filled from the column names; "Use this dataset" activates it across
    the app and calls on_done(filename).
    """
    data = uploaded.getvalue()
    try:
        raw, _ = ingest.read_and_clean(data, uploaded.name)
    except ValueError as exc:
        st.error(str(exc))
        return

    nonce = st.session_state.get(_nonce_key(key), 0)
    ui.stepper(["Upload", "Map columns", "Explore"], active=1)
    pending_key = f"_pending-mapping-{ingest.file_digest(data)}"
    suggested = st.session_state.setdefault(pending_key, suggest_mapping(raw.columns))

    with ui.card(f"mapping-{key}", "Map your columns",
                 "We pre-filled what we could recognise. Order date and revenue are required; "
                 "every other field unlocks more analysis."):
        options = ["—"] + list(raw.columns)
        chosen = {}
        cols = st.columns(3, gap="medium")
        for i, field in enumerate(FIELDS):
            current = suggested.get(field.key)
            with cols[i % 3]:
                pick = st.selectbox(
                    field.label + (" *" if field.required else ""), options,
                    index=options.index(current) if current in options else 0,
                    key=f"map-{key}-{nonce}-{field.key}", help=field.help or None,
                )
            chosen[field.key] = None if pick == "—" else pick

        problems = validate_mapping(chosen, raw)
        mapped = sum(1 for v in chosen.values() if v)
        st.caption(f"{mapped} of {len(FIELDS)} fields mapped · {len(raw):,} rows · {raw.shape[1]} columns")

        with st.expander("Preview the first rows", icon=":material/table_view:"):
            st.dataframe(raw.head(8), hide_index=True, width="stretch")

        for problem in problems:
            st.warning(problem, icon=":material/error:")

        left, right = st.columns([1, 1])
        with right:
            apply = st.button("Use this dataset", type="primary", icon=":material/check:",
                              width="stretch", disabled=bool(problems), key=f"apply-{key}")
        with left:
            if st.button("Cancel", width="stretch", key=f"cancel-{key}"):
                clear(key)
                st.rerun()

    if apply:
        state.activate_upload(data, uploaded.name, chosen)
        clear(key)
        st.session_state.pop(pending_key, None)
        on_done(uploaded.name)

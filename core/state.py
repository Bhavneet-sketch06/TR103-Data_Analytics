"""
Session state: which dataset is active.

The active upload is identified by its digest, kept both in session_state and
in the `ds` URL parameter. Because the upload itself is saved under
data/uploads/, a page reload (or the theme toggle, which reloads) or a shared
link brings the same dataset back.
"""

from __future__ import annotations

import streamlit as st

from core import ingest

KEY_DIGEST = "active_dataset_digest"
QUERY_DS = "ds"


def get_dataset() -> ingest.Dataset:
    digest = st.session_state.get(KEY_DIGEST) or st.query_params.get(QUERY_DS)
    if digest:
        dataset = ingest.load_upload(digest)
        if dataset is not None:
            st.session_state[KEY_DIGEST] = digest
            if st.query_params.get(QUERY_DS) != digest:
                st.query_params[QUERY_DS] = digest
            return dataset
        # Unknown or deleted upload: fall back to the sample cleanly.
        st.session_state.pop(KEY_DIGEST, None)
        if QUERY_DS in st.query_params:
            del st.query_params[QUERY_DS]
    return ingest.load_sample()


def activate_upload(data: bytes, filename: str, mapping: dict) -> None:
    digest = ingest.save_upload(data, filename, mapping)
    st.session_state[KEY_DIGEST] = digest
    st.query_params[QUERY_DS] = digest


def use_sample() -> None:
    st.session_state.pop(KEY_DIGEST, None)
    if QUERY_DS in st.query_params:
        del st.query_params[QUERY_DS]

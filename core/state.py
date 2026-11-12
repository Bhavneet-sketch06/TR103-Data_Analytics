"""
Session state: which dataset is active.

The app starts with no dataset: nothing is analysed until a file is uploaded
(or the sample is chosen on purpose). The active dataset is identified by its
upload digest, or SAMPLE for the bundled sample, kept both in session_state and
in the `ds` URL parameter, so a reload or a shared link brings the same data
back. Opening the app without `ds` starts empty again.
"""

from __future__ import annotations

import streamlit as st

from core import ingest

KEY_DIGEST = "active_dataset_digest"
QUERY_DS = "ds"
SAMPLE = "sample"


def get_dataset() -> ingest.Dataset | None:
    """The active dataset, or None when nothing has been loaded yet."""
    digest = st.session_state.get(KEY_DIGEST) or st.query_params.get(QUERY_DS)
    if not digest:
        return None
    dataset = ingest.load_sample() if digest == SAMPLE else ingest.load_upload(digest)
    if dataset is None:
        # Unknown or deleted upload: start empty rather than guess.
        clear()
        return None
    st.session_state[KEY_DIGEST] = digest
    if st.query_params.get(QUERY_DS) != digest:
        st.query_params[QUERY_DS] = digest
    return dataset


def activate_upload(data: bytes, filename: str, mapping: dict) -> None:
    digest = ingest.save_upload(data, filename, mapping)
    st.session_state[KEY_DIGEST] = digest
    st.query_params[QUERY_DS] = digest


def use_sample() -> None:
    st.session_state[KEY_DIGEST] = SAMPLE
    st.query_params[QUERY_DS] = SAMPLE


def clear() -> None:
    st.session_state.pop(KEY_DIGEST, None)
    if QUERY_DS in st.query_params:
        del st.query_params[QUERY_DS]

"""Privacy controls for the Statement Analyser (see the privacy rules in CLAUDE.md).

Statement data only ever lives in st.session_state under keys starting with "statement_",
so it disappears when the browser tab closes, and clear_statement_data() wipes it on demand.
"""

import os

import streamlit as st

UPLOAD_SETTING = "MRC_ALLOW_UPLOADS"
STATEMENT_PREFIX = "statement_"
UPLOADER_VERSION = "uploader_version"   # bumped to give the file uploader a fresh, empty widget

UPLOAD_DISABLED_NOTE = (
    "Upload is disabled in the online demo for privacy. Run the app locally to analyse your own statements."
)
UPLOAD_NOTICE = (
    "**Your statements stay on this computer.** Files are read in memory on the computer running this app, "
    "never saved to disk, never sent anywhere, and are cleared when you close the tab or click **Clear my data**. "
    "Account numbers, BSBs, card numbers, names and reference numbers are removed as soon as a file is read."
)


def uploads_allowed() -> bool:
    """Uploads are OFF unless MRC_ALLOW_UPLOADS is set to 1/true/yes/on (local use only)."""
    return os.environ.get(UPLOAD_SETTING, "").strip().lower() in ("1", "true", "yes", "on")


def clear_statement_data() -> None:
    """Wipe every piece of statement data from this session.

    If statement figures were copied into the Calculator, its inputs go back to the defaults too.
    """
    if st.session_state.get(f"{STATEMENT_PREFIX}applied"):
        st.session_state.pop("calculator_inputs", None)
        st.session_state.pop("calc_last_suggested", None)
    for key in [k for k in st.session_state if str(k).startswith(STATEMENT_PREFIX)]:
        del st.session_state[key]
    st.session_state[UPLOADER_VERSION] = st.session_state.get(UPLOADER_VERSION, 0) + 1

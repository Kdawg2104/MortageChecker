"""Privacy controls for the Statement Analyser (see the privacy rules in CLAUDE.md).

Statement data lives only in st.session_state["statement"] (plus "stmtw_" widgets), in memory.
Deletion is handled by ui/session_guard.py: after inactivity, on "Clear my data", or when the
server drops a closed tab's session (server.disconnectedSessionTTL in .streamlit/config.toml).
"""

import os

from ui.session_guard import timeout_text, wipe

UPLOAD_SETTING = "MRC_ALLOW_UPLOADS"

UPLOAD_DISABLED_NOTE = (
    "Upload is disabled in the online demo for privacy. Run the app locally to analyse your own statements."
)
UPLOAD_NOTICE = (
    f"**Your data is processed on this computer only and is automatically deleted after {timeout_text()} of "
    "inactivity, when you click 'Clear my data', or within about a minute of closing the tab.** Files are read in "
    "memory, never saved to disk or sent anywhere. Account numbers, BSBs, card numbers, names and reference "
    "numbers are removed as soon as a file is read."
)


def uploads_allowed() -> bool:
    """Uploads are OFF unless MRC_ALLOW_UPLOADS is set to 1/true/yes/on (local use only)."""
    return os.environ.get(UPLOAD_SETTING, "").strip().lower() in ("1", "true", "yes", "on")


def clear_statement_data() -> None:
    """Wipe every piece of statement data from this session straight away ("Clear my data")."""
    wipe(reason="cleared")

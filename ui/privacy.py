"""Privacy controls for the Statement Analyser (see the privacy rules in CLAUDE.md).

Statement data lives only in st.session_state["statement"] (plus "stmtw_" widgets), in memory.
Deletion is handled by ui/session_guard.py: after inactivity, on "Clear my data", or when the
session ends (closing the tab; on a server, server.disconnectedSessionTTL in .streamlit/config.toml).

Uploads are allowed only where the files can't reach a server we run:
- in the browser build (stlite): Python runs inside the visitor's browser, so files never leave their device;
- locally, when HEADROOM_ALLOW_UPLOADS is set (the "server" is the user's own computer).
Any other server deployment (e.g. Streamlit Community Cloud) offers synthetic samples only.
"""

import os
from collections.abc import Mapping

from engine.runtime import IS_BROWSER
from ui.session_guard import timeout_text, wipe

UPLOAD_SETTING = "HEADROOM_ALLOW_UPLOADS"

UPLOAD_DISABLED_NOTE = (
    "Upload is disabled in the online demo for privacy. Run the app locally to analyse your own statements."
)
UPLOAD_NOTICE = (
    f"**Your data is processed on this computer only and is automatically deleted after {timeout_text()} of "
    "inactivity, when you click 'Clear my data', or within about a minute of closing the tab.** Files are read in "
    "memory, never saved to disk or sent anywhere. Account numbers, BSBs, card numbers, names and reference "
    "numbers are removed as soon as a file is read."
)
BROWSER_UPLOAD_NOTICE = (
    "**Your statements are read inside your web browser on this device. They are never uploaded to any server, "
    f"never saved, and are deleted after {timeout_text()} of inactivity, when you click 'Clear my data', or when "
    "you close or refresh this tab.** Account numbers, BSBs, card numbers, names and reference numbers are removed "
    "as soon as a file is read."
)
VERIFY_STEPS = (
    "1. Open your browser's developer tools (F12, or right-click → Inspect) and choose the **Network** tab.\n"
    "2. Click the 🚫 button to clear the list, so only new requests show.\n"
    "3. Upload a statement and click **Analyse these files**.\n"
    "4. The list stays empty: no request carries your file anywhere. Everything you see was worked out by "
    "Python running inside this tab.\n\n"
    "The page also has a Content Security Policy that only lets it contact the server it was loaded from and the "
    "code library site it loads Python from, and the code is open on GitHub for anyone to check."
)


def uploads_allowed(is_browser: bool = IS_BROWSER, env: Mapping[str, str] | None = None) -> bool:
    """True in the browser build, or locally with HEADROOM_ALLOW_UPLOADS=1/true/yes/on; otherwise False."""
    if is_browser:
        return True
    env = os.environ if env is None else env
    return env.get(UPLOAD_SETTING, "").strip().lower() in ("1", "true", "yes", "on")


def upload_notice(is_browser: bool = IS_BROWSER) -> str:
    """The privacy notice shown above the upload box, worded for where the app is running."""
    return BROWSER_UPLOAD_NOTICE if is_browser else UPLOAD_NOTICE


def clear_statement_data() -> None:
    """Wipe every piece of statement data from this session straight away ("Clear my data")."""
    wipe(reason="cleared")

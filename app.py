"""Mortgage Reality Check: entry point.

Sets up the page, shared styling, the statement-data timeout, the first-visit disclaimer and navigation.
Each page lives in pages/; all calculations live in engine/.
"""

import streamlit as st

from ui.components import disclaimer_dialog, footer, load_css
from ui.session_guard import guard_rerun, status_fragment

st.set_page_config(page_title="Mortgage Reality Check", page_icon="🏠", layout="wide")
load_css()

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("app_pages/statement_analyser.py", title="Statement Analyser", icon=":material/receipt_long:"),
        st.Page("app_pages/calculator.py", title="Calculator", icon=":material/calculate:"),
        st.Page("app_pages/stress_scenarios.py", title="Stress Scenarios", icon=":material/thunderstorm:"),
        st.Page("app_pages/risk_simulator.py", title="Risk Simulator", icon=":material/casino:"),
        st.Page("app_pages/market_snapshot.py", title="Market Snapshot", icon=":material/monitoring:"),
        st.Page("app_pages/learn.py", title="Learn the Basics", icon=":material/school:"),
        st.Page("app_pages/about.py", title="About & Disclaimer", icon=":material/info:"),
    ],
    position="top",
)

# Statement data timeout: check the timer, then count this rerun as activity. The status
# fragment re-checks every 15 seconds on its own (without counting as activity).
guard_rerun()
status_fragment()

if not st.session_state.get("disclaimer_accepted"):
    disclaimer_dialog()

page.run()
footer()

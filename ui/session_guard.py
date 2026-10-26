"""Automatic deletion of statement data after a period of inactivity.

All statement data lives in ONE place, st.session_state["statement"] (a dict), including any
figures copied from it into the Calculator. Widgets that show statement data use keys starting
with "stmtw_" (Streamlit widgets can't live inside a dict). wipe() removes both.

Timing works two ways:
- guard_rerun() runs at the start of every normal page load or interaction: it first checks
  the timer (so data left idle too long is wiped even if the next click comes later), then
  records the interaction.
- status_fragment() reruns by itself every 15 seconds, so an idle tab still gets wiped. It
  only CHECKS the timer; its periodic runs never count as activity.

Every function takes the session state and a clock as arguments, so tests can use a plain
dict and a fake clock instead of waiting 10 minutes.
"""

import gc
import math
import os
import time
from collections.abc import Callable, MutableMapping

import streamlit as st

# 10 minutes. MRC_TIMEOUT_SECONDS can shorten it for manual testing only; the default stays 600.
TIMEOUT_SECONDS = int(os.environ.get("MRC_TIMEOUT_SECONDS", "600"))
WARNING_SECONDS = 60
CHECK_EVERY = "15s"
# "inactivity": every interaction restarts the timer. "absolute": the timer runs from when data was loaded.
TIMEOUT_MODE = "inactivity"

STATEMENT_KEY = "statement"
WIDGET_PREFIX = "stmtw_"
UPLOADER_VERSION = "uploader_version"
EXPIRED_FLAG = "statement_expired_notice"


def clock() -> float:
    """Current time in seconds. A module-level function so tests can replace it."""
    return time.time()


def _state(state: MutableMapping | None) -> MutableMapping:
    return st.session_state if state is None else state


def _now(now_fn: Callable[[], float] | None) -> float:
    return (now_fn or clock)()


def timeout_text() -> str:
    """'10 minutes' (or '90 seconds' when shortened for testing)."""
    if TIMEOUT_SECONDS % 60 == 0:
        minutes = TIMEOUT_SECONDS // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{TIMEOUT_SECONDS} seconds"


EXPIRED_MESSAGE = f"Your statement data was deleted after {timeout_text()} of inactivity."


def namespace(state: MutableMapping | None = None) -> dict | None:
    """The statement data dict, or None if nothing is loaded."""
    return _state(state).get(STATEMENT_KEY)


def has_data(state: MutableMapping | None = None) -> bool:
    return namespace(state) is not None


def start(state: MutableMapping | None = None, now_fn: Callable[[], float] | None = None) -> dict:
    """Create (or reuse) the statement namespace and start the timer."""
    state = _state(state)
    now = _now(now_fn)
    ns = state.get(STATEMENT_KEY)
    if ns is None:
        ns = state[STATEMENT_KEY] = {}
    ns["loaded_at"] = now
    ns["last_activity"] = now
    return ns


def touch(state: MutableMapping | None = None, now_fn: Callable[[], float] | None = None) -> None:
    """Record user activity (restarts the inactivity timer)."""
    ns = namespace(state)
    if ns is not None:
        ns["last_activity"] = _now(now_fn)


def seconds_left(state: MutableMapping | None = None, now_fn: Callable[[], float] | None = None) -> float | None:
    """Seconds until the data is deleted, or None if nothing is loaded."""
    ns = namespace(state)
    if ns is None:
        return None
    since = ns["loaded_at"] if TIMEOUT_MODE == "absolute" else ns["last_activity"]
    return TIMEOUT_SECONDS - (_now(now_fn) - since)


def check_and_expire(state: MutableMapping | None = None, now_fn: Callable[[], float] | None = None) -> bool:
    """Wipe the data if the time is up. Returns True if it was wiped. Never counts as activity."""
    left = seconds_left(state, now_fn)
    if left is not None and left <= 0:
        wipe(state, reason="timeout")
        return True
    return False


def wipe(state: MutableMapping | None = None, reason: str = "cleared") -> None:
    """Delete every piece of statement data from this session.

    Removes the namespace, the statement widgets and any Calculator widgets showing figures
    copied from the statements (those pages then fall back to the manual inputs). The file
    uploader gets a new key, which releases the uploaded files.
    """
    state = _state(state)
    ns = state.pop(STATEMENT_KEY, None)
    prefilled = list((ns or {}).get("prefill", {}))
    for name in prefilled:
        state.pop(f"calc_{name}", None)
    if prefilled:
        state.pop("calc_last_suggested", None)
    for key in [k for k in list(state.keys()) if str(k).startswith(WIDGET_PREFIX)]:
        del state[key]
    state[UPLOADER_VERSION] = state.get(UPLOADER_VERSION, 0) + 1
    if ns is not None:
        ns.clear()
    del ns
    gc.collect()   # releases the memory; Python can't guarantee it's overwritten
    if reason == "timeout":
        state[EXPIRED_FLAG] = True


# ---------------------------------------------------------------------------
# Streamlit hooks
# ---------------------------------------------------------------------------
def guard_rerun() -> None:
    """Call at the start of every normal rerun (app.py): expire first, then record activity."""
    if not check_and_expire():
        touch()
    if st.session_state.pop(EXPIRED_FLAG, False):
        st.warning(EXPIRED_MESSAGE, icon=":material/timer_off:")


@st.fragment(run_every=CHECK_EVERY)
def status_fragment() -> None:
    """Re-checks the timer every 15 s without counting as activity, and shows the status chip."""
    if check_and_expire():
        st.rerun()   # whole app, so every page falls back to the manual inputs
    left = seconds_left()
    if left is None:
        return
    if left <= WARNING_SECONDS:
        with st.container(border=True):
            st.warning(f"Your statement data will be deleted in {max(0, int(left))} seconds because of inactivity.",
                       icon=":material/timer:")
            keep, clear = st.columns(2)
            if keep.button("Keep my session", key=f"{WIDGET_PREFIX}keep", type="primary", width="stretch"):
                touch()
                st.rerun(scope="fragment")
            if clear.button("Clear now", key=f"{WIDGET_PREFIX}clear_now", width="stretch"):
                wipe()
                st.rerun()
        return
    chip, button = st.columns([4, 1], vertical_alignment="center")
    chip.markdown(f":material/lock: **Statement data loaded** — auto-deletes in {math.ceil(left / 60)} min if inactive")
    if button.button("Clear my data", key=f"{WIDGET_PREFIX}clear_chip", icon=":material/delete:"):
        wipe()
        st.rerun()

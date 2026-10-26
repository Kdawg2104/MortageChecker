"""10-minute inactivity timeout for statement data, tested with a fake clock (no waiting)."""

import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from engine.statements.categorise import categorise
from engine.statements.parse import parse_file
from tests.test_privacy import snapshot
from ui import session_guard as guard
from ui.privacy import UPLOAD_NOTICE, UPLOAD_SETTING

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
SAMPLES = ROOT / "data" / "samples"
MINUTE = 60


class FakeClock:
    """A clock the test moves forward by hand."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, minutes: float = 0, seconds: float = 0) -> None:
        self.now += minutes * MINUTE + seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def state(clock):
    """Session state with statement data loaded, figures copied to the Calculator, and unrelated state."""
    state = {
        "disclaimer_accepted": True,
        "calculator_inputs": {"income_0": 90_000, "borrowers": 1},
        "stress_events": {"base": []},
        "calc_income_0": 123_456,          # Calculator widget showing a statement-derived figure
        "calc_last_suggested": 2_800,
        "stmtw_editor_0": {"edited_rows": {}},
        "stmtw_upload_0": ["file"],
    }
    ns = guard.start(state, clock)
    ns["frame"] = "transactions"
    ns["prefill"] = {"income_0": 123_456, "borrowers": 1}
    return state


def test_constants():
    assert guard.TIMEOUT_SECONDS == 600
    assert guard.WARNING_SECONDS == 60
    assert guard.TIMEOUT_MODE == "inactivity"


def test_present_at_9_59_wiped_at_10_00(state, clock):
    clock.advance(minutes=9, seconds=59)
    assert not guard.check_and_expire(state, clock)
    assert guard.has_data(state)
    clock.advance(seconds=1)
    assert guard.check_and_expire(state, clock)
    assert not guard.has_data(state)


def test_interaction_resets_the_timer(state, clock):
    clock.advance(minutes=8)
    guard.touch(state, clock)            # the user clicks something at minute 8
    clock.advance(minutes=9)             # minute 17
    assert not guard.check_and_expire(state, clock)
    assert guard.has_data(state)
    clock.advance(minutes=1)             # minute 18 = 10 minutes after the last interaction
    assert guard.check_and_expire(state, clock)
    assert not guard.has_data(state)


def test_periodic_checks_do_not_reset_the_timer(state, clock):
    """The 15-second fragment only calls check_and_expire(), never touch()."""
    for _ in range(39):                  # 39 checks x 15 s = 9:45
        clock.advance(seconds=15)
        assert not guard.check_and_expire(state, clock)
    clock.advance(seconds=15)            # 10:00 with no interaction at all
    assert guard.check_and_expire(state, clock)


def test_seconds_left_counts_down(state, clock):
    assert guard.seconds_left(state, clock) == 600
    clock.advance(minutes=9, seconds=30)
    assert guard.seconds_left(state, clock) == 30
    assert guard.seconds_left({}, clock) is None


def test_absolute_mode_ignores_interactions(state, clock, monkeypatch):
    monkeypatch.setattr(guard, "TIMEOUT_MODE", "absolute")
    clock.advance(minutes=8)
    guard.touch(state, clock)
    clock.advance(minutes=2)
    assert guard.check_and_expire(state, clock)


def test_wipe_removes_statement_data_and_prefills_only(state):
    guard.wipe(state, reason="timeout")
    assert guard.STATEMENT_KEY not in state
    assert not any(str(k).startswith(guard.WIDGET_PREFIX) for k in state)
    assert "calc_income_0" not in state                 # statement figure shown in the Calculator
    assert "calc_last_suggested" not in state
    # Unrelated state is left alone, so pages fall back to the manual inputs
    assert state["disclaimer_accepted"] is True
    assert state["calculator_inputs"] == {"income_0": 90_000, "borrowers": 1}
    assert state["stress_events"] == {"base": []}
    assert state[guard.UPLOADER_VERSION] == 1           # new uploader key releases uploaded files
    assert state[guard.EXPIRED_FLAG] is True


def test_clearing_by_hand_shows_no_timeout_message(state):
    guard.wipe(state, reason="cleared")
    assert guard.EXPIRED_FLAG not in state
    assert not guard.has_data(state)


def test_nothing_to_expire_without_data(clock):
    state = {"disclaimer_accepted": True}
    clock.advance(minutes=60)
    assert not guard.check_and_expire(state, clock)
    assert state == {"disclaimer_accepted": True}


def test_privacy_notice_wording():
    assert ("Your data is processed on this computer only and is automatically deleted after 10 minutes of "
            "inactivity, when you click 'Clear my data', or within about a minute of closing the tab.") in UPLOAD_NOTICE


def test_closed_tab_sessions_dropped_after_a_minute():
    config = (ROOT / ".streamlit" / "config.toml").read_text()
    assert "disconnectedSessionTTL = 60" in config


def test_parsing_jamie_writes_no_files():
    files = {name: (SAMPLES / name).read_bytes() for name in ("sample_jamie_statement.pdf", "sample_jamie_statement.csv")}
    before_repo, before_tmp = snapshot(ROOT), snapshot(Path(tempfile.gettempdir()))
    for name, data in files.items():
        categorise(parse_file(name, data))
    assert snapshot(ROOT) == before_repo
    assert set(snapshot(Path(tempfile.gettempdir()))) - set(before_tmp) == set()


# ---------------- The real app (AppTest), with the clock replaced ----------------
def open_analyser(monkeypatch, fake: FakeClock) -> AppTest:
    monkeypatch.delenv(UPLOAD_SETTING, raising=False)
    monkeypatch.setattr(guard, "clock", fake)
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.session_state["disclaimer_accepted"] = True
    return at.switch_page("app_pages/statement_analyser.py").run()


def test_upload_not_available_by_default(monkeypatch, clock):
    at = open_analyser(monkeypatch, clock)
    assert at.get("file_uploader") == []


def test_status_chip_and_clear_button_while_loaded(monkeypatch, clock):
    at = open_analyser(monkeypatch, clock)
    at.button(key="sample_jamie").click().run()
    assert any("Statement data loaded" in m.value and "10 min" in m.value for m in at.markdown)
    at.button(key="stmtw_clear_chip").click().run()
    assert "statement" not in at.session_state
    assert not any("Statement data loaded" in m.value for m in at.markdown)


def test_clear_my_data_wipes_immediately(monkeypatch, clock):
    at = open_analyser(monkeypatch, clock)
    at.button(key="sample_alex").click().run()
    at.button(key="stmtw_clear_page").click().run()
    assert "statement" not in at.session_state
    for key in ("stmtw_filter", "stmtw_editor_0", "stmtw_help_0", "stmtw_gross_0_False"):
        assert key not in at.session_state


def test_timeout_falls_back_to_manual_calculator(monkeypatch, clock):
    at = open_analyser(monkeypatch, clock)
    at.button(key="sample_sam_jordan").click().run()
    at.button[[b.label for b in at.button].index("Use these numbers")].click().run()
    at.switch_page("app_pages/calculator.py").run()
    assert at.session_state["calc_borrowers"] == 2
    assert any("Using figures from your statements" in m.value for m in at.markdown)

    clock.advance(minutes=10, seconds=1)   # walked away
    at.run()
    assert not at.exception
    assert "statement" not in at.session_state
    assert any(guard.EXPIRED_MESSAGE in w.value for w in at.warning)
    assert at.session_state["calc_borrowers"] == 1                 # manual default again
    assert at.session_state["calc_income_0"] == 100_000
    assert not any("Using figures from your statements" in m.value for m in at.markdown)


def test_activity_keeps_data(monkeypatch, clock):
    at = open_analyser(monkeypatch, clock)
    at.button(key="sample_alex").click().run()
    for _ in range(3):
        clock.advance(minutes=8)
        at.run()                           # an interaction every 8 minutes
    assert "statement" in at.session_state

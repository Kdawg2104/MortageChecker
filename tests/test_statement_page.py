"""Statement Analyser page behaviour, run headlessly with Streamlit's AppTest (synthetic samples only)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui.privacy import UPLOAD_DISABLED_NOTE, UPLOAD_SETTING

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGE = "app_pages/statement_analyser.py"


def open_page() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.session_state["disclaimer_accepted"] = True
    return at.switch_page(PAGE).run()


def uploaders(at: AppTest) -> list:
    return at.get("file_uploader")


def test_upload_hidden_by_default(monkeypatch):
    monkeypatch.delenv(UPLOAD_SETTING, raising=False)
    at = open_page()
    assert not at.exception
    assert uploaders(at) == []
    assert any(UPLOAD_DISABLED_NOTE in info.value for info in at.info)


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_upload_shown_when_allowed(monkeypatch, value):
    monkeypatch.setenv(UPLOAD_SETTING, value)
    at = open_page()
    assert not at.exception
    assert len(uploaders(at)) == 1


def test_sample_to_calculator_and_clear(monkeypatch):
    monkeypatch.delenv(UPLOAD_SETTING, raising=False)
    at = open_page()
    at.button(key="sample_sam_jordan").click().run()
    assert not at.exception
    assert "statement_frame" in at.session_state

    at.button[[b.label for b in at.button].index("Use these numbers")].click().run()
    inputs = at.session_state["calculator_inputs"]
    assert inputs["borrowers"] == 2
    assert inputs["income_0"] == pytest.approx(110_000, abs=100)
    assert inputs["income_1"] == pytest.approx(75_000, abs=100)
    assert at.session_state["statement_applied"]

    at.switch_page("app_pages/calculator.py").run()
    assert not at.exception
    assert any("Using figures from your statements" in m.value for m in at.markdown)
    assert at.session_state["calc_expenses"] == inputs["expenses"]   # not overwritten by the lifestyle preset

    at.switch_page(PAGE).run()
    at.button[[b.label for b in at.button].index("Clear my data")].click().run()
    for key in ("statement_frame", "statement_source", "statement_applied", "statement_warnings"):
        assert key not in at.session_state
    assert "calculator_inputs" not in at.session_state or at.session_state["calculator_inputs"].get("borrowers") != 2


def test_editing_a_category_updates_totals(monkeypatch):
    monkeypatch.delenv(UPLOAD_SETTING, raising=False)
    at = open_page()
    at.button(key="sample_alex").click().run()
    frame = at.session_state["statement_frame"]
    netflix = frame.index[frame["description"].str.contains("NETFLIX")][0]
    frame.loc[netflix, "include"] = False          # same effect as unticking Include in the table
    at.run()
    assert not at.exception
    assert not at.session_state["statement_frame"].loc[netflix, "include"]

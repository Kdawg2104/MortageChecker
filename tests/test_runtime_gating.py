"""Statement uploads are ON only where files can't reach a server (CLAUDE.md privacy rules)."""

import sys

from engine import runtime
from ui.privacy import BROWSER_UPLOAD_NOTICE, UPLOAD_NOTICE, UPLOAD_SETTING, upload_notice, uploads_allowed


def test_runtime_detects_python_on_this_machine():
    assert runtime.IS_BROWSER == (sys.platform == "emscripten")
    assert runtime.IS_BROWSER is False   # the tests run in normal Python


def test_browser_build_allows_uploads():
    assert uploads_allowed(is_browser=True, env={}) is True


def test_local_with_setting_allows_uploads():
    for value in ("1", "true", "YES", " on "):
        assert uploads_allowed(is_browser=False, env={UPLOAD_SETTING: value}) is True


def test_server_without_setting_is_samples_only():
    assert uploads_allowed(is_browser=False, env={}) is False
    assert uploads_allowed(is_browser=False, env={UPLOAD_SETTING: "0"}) is False
    assert uploads_allowed(is_browser=False, env={"MRC_ALLOW_UPLOADS": "1"}) is False   # old name no longer works


def test_default_reads_the_real_environment(monkeypatch):
    monkeypatch.delenv(UPLOAD_SETTING, raising=False)
    assert uploads_allowed() is False
    monkeypatch.setenv(UPLOAD_SETTING, "1")
    assert uploads_allowed() is True


def test_notice_matches_where_the_app_runs():
    assert upload_notice(is_browser=True) == BROWSER_UPLOAD_NOTICE
    assert upload_notice(is_browser=False) == UPLOAD_NOTICE
    assert ("Your statements are read inside your web browser on this device. They are never uploaded to any "
            "server, never saved, and are deleted after 10 minutes of inactivity, when you click 'Clear my data', "
            "or when you close or refresh this tab.") in BROWSER_UPLOAD_NOTICE

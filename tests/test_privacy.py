"""Privacy rules from CLAUDE.md, enforced as tests."""

import os
import re
import tempfile
from pathlib import Path

from engine.statements.categorise import categorise
from engine.statements.parse import parse_file

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
ALLOWED_DATA_FOLDERS = ("data/samples/", "data/processed/", "data/raw/")
SKIP_FOLDERS = {".venv", ".git", ".idea", "__pycache__", ".pytest_cache", "node_modules"}
STATEMENT_EXTENSIONS = {".pdf", ".csv", ".ofx", ".qif"}


def snapshot(folder: Path) -> dict:
    """Every file under `folder` with its size and modification time."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_FOLDERS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                stat = path.stat()
                found[str(path)] = (stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                pass
    return found


def test_no_statement_files_outside_allowed_folders():
    """Rule 7: real statements must never sit in the repo, where they could be committed."""
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_FOLDERS]
        for name in filenames:
            relative = (Path(dirpath) / name).relative_to(ROOT).as_posix()
            if Path(name).suffix.lower() in STATEMENT_EXTENSIONS and not relative.startswith(ALLOWED_DATA_FOLDERS):
                offenders.append(relative)
    assert offenders == [], f"Statement-like files outside {ALLOWED_DATA_FOLDERS}: {offenders}"


def test_gitignore_has_privacy_rules():
    rules = (ROOT / ".gitignore").read_text().splitlines()
    for rule in ("/private/", "/statements/", "*.ofx", "*.qif", "*.pdf", "*.csv", "!data/samples/**"):
        assert rule in rules


def test_streamlit_telemetry_disabled():
    config = (ROOT / ".streamlit" / "config.toml").read_text()
    assert "gatherUsageStats = false" in config


def test_parsing_writes_no_files():
    """Rule 1: statements are processed in memory only."""
    data = {p.name: p.read_bytes() for p in SAMPLES.iterdir() if p.suffix in (".csv", ".pdf")}
    before_repo, before_tmp = snapshot(ROOT), snapshot(Path(tempfile.gettempdir()))
    for name, content in data.items():
        categorise(parse_file(name, content))
    assert snapshot(ROOT) == before_repo
    new_temp_files = set(snapshot(Path(tempfile.gettempdir()))) - set(before_tmp)
    assert new_temp_files == set()


def test_statement_engine_has_no_network_or_cache_code():
    """Rule 2: no network calls, and nothing that could persist statement data."""
    forbidden = ("import urllib", "import requests", "import socket", "import http", "from urllib", "from requests",
                 "from http", "to_csv", "to_pickle", "to_excel", "write_text", "write_bytes", "tofile", "tempfile",
                 "st.cache", "logging", "print(")
    builtin_open = re.compile(r"(?<![.\w])open\(")   # open(...) writes files; pdfplumber.open(BytesIO) is fine
    for path in (ROOT / "engine" / "statements").glob("*.py"):
        source = path.read_text()
        for word in forbidden:
            assert word not in source, f"{path.name} contains {word!r}"
        assert not builtin_open.search(source), f"{path.name} calls open()"


STATEMENT_PAGES = ("app_pages/statement_analyser.py", "app_pages/calculator.py", "app_pages/stress_scenarios.py",
                   "app_pages/risk_simulator.py", "ui/calculator_state.py", "ui/session_guard.py", "ui/privacy.py")


def test_no_caching_where_statement_figures_are_used():
    """Rule 1: statement data (incl. figures copied to other pages) must never be cached."""
    for name in STATEMENT_PAGES:
        source = (ROOT / name).read_text()
        assert "st.cache" not in source, f"{name} uses a Streamlit cache"

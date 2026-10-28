"""The browser build (scripts/build_web.py): complete, reproducible, and locked down by its CSP."""

import ast
import json
import re
from pathlib import Path

import pytest

from scripts import build_web

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SOURCES = {"'self'", "https://cdn.jsdelivr.net"}
DATA_EXTENSIONS = (".csv", ".json", ".yaml", ".css", ".svg", ".jpg", ".pdf")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Build twice into temporary folders, with fake wheels so the tests never touch the network."""
    original = build_web.fetch_wheel
    build_web.fetch_wheel = lambda wheel, cache=None: f"fake {wheel.filename}".encode()
    try:
        first, second = tmp_path_factory.mktemp("web1"), tmp_path_factory.mktemp("web2")
        files = build_web.build(first)
        build_web.build(second)
    finally:
        build_web.fetch_wheel = original
    return first, second, files


def csp_directives(html: str) -> dict[str, list[str]]:
    match = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html)
    assert match, "index.html has no Content-Security-Policy meta tag"
    directives = {}
    for part in match.group(1).split(";"):
        name, *sources = part.split()
        directives[name] = sources
    return directives


def mount_options(out: Path) -> dict:
    script = (out / "headroom.js").read_text()
    return json.loads(re.search(r"const options = (\{.*?\n\});", script, re.S).group(1))


# ---------------- Content Security Policy ----------------
def test_csp_limits_network_access(built):
    directives = csp_directives((built[0] / "index.html").read_text())
    assert set(directives["connect-src"]) <= ALLOWED_SOURCES
    assert directives["default-src"] == ["'self'"]
    assert directives["object-src"] == ["'none'"]
    assert directives["form-action"] == ["'none'"]
    for name, sources in directives.items():
        hosts = {s for s in sources if s.startswith("http")}
        assert hosts <= ALLOWED_SOURCES, f"{name} allows {hosts - ALLOWED_SOURCES}"
    assert "'unsafe-eval'" not in directives["script-src"]
    assert "'unsafe-inline'" not in directives["script-src"]


def test_no_fonts_analytics_or_trackers(built):
    out = built[0]
    page = "".join((out / name).read_text() for name in ("index.html", "headroom.js", "loading.css"))
    page += (ROOT / "assets" / "style.css").read_text()
    for word in ("fonts.googleapis", "fonts.gstatic", "google-analytics", "googletagmanager", "gtag(", "plausible",
                 "@import", "pypi.org", "pythonhosted"):
        assert word not in page


def test_stlite_version_pinned(built):
    html = (built[0] / "index.html").read_text()
    assert f"@stlite/browser@{build_web.STLITE_VERSION}/" in html
    assert re.fullmatch(r"\d+\.\d+\.\d+", build_web.STLITE_VERSION)
    assert "@latest" not in html


def test_no_persistent_browser_storage(built):
    options = mount_options(built[0])
    assert "idbfsMountpoints" not in options
    assert options["streamlitConfig"]["browser.gatherUsageStats"] is False
    assert options["env"] == {}   # no test-only timeout in a normal build


# ---------------- Completeness ----------------
def local_modules(path: Path) -> set[str]:
    """engine/ui/app_pages modules imported by one file, as file paths."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            if name.split(".")[0] in ("engine", "ui", "app_pages"):
                module = ROOT / Path(*name.split("."))
                found.add(f"{module.relative_to(ROOT).as_posix()}.py" if module.with_suffix(".py").exists()
                          else f"{module.relative_to(ROOT).as_posix()}/__init__.py")
    return found


def test_every_imported_module_is_included(built):
    files = set(built[2])
    to_visit, seen = ["app.py"], set()
    while to_visit:
        name = to_visit.pop()
        if name in seen:
            continue
        seen.add(name)
        assert name in files, f"{name} is imported but missing from the browser build"
        source = (ROOT / name).read_text()
        to_visit += sorted(local_modules(ROOT / name))
        to_visit += re.findall(r'"(app_pages/\w+\.py)"', source)   # st.Page, st.switch_page, st.page_link
    assert "app_pages/statement_analyser.py" in seen


def test_every_data_file_is_included(built):
    files = set(built[2])
    for folder in ("data/samples", "data/processed"):
        for path in (ROOT / folder).iterdir():
            assert f"{folder}/{path.name}" in files
    # Any data/asset file named in the app's code
    for name in files:
        if name.endswith(".py"):
            for literal in re.findall(r'"([\w.-]+(?:%s))"' % "|".join(re.escape(e) for e in DATA_EXTENSIONS),
                                      (ROOT / name).read_text()):
                matches = [p for p in (ROOT / "data").rglob(literal)] + list((ROOT / "assets").glob(literal))
                for match in matches:
                    if "raw" not in match.parts:
                        assert match.relative_to(ROOT).as_posix() in files, f"{match} is read but not included"
    for required in ("data/market_snapshot.json", "data/categories.yaml", "assets/style.css", "assets/favicon.svg",
                     ".streamlit/config.toml"):
        assert required in files


def test_files_are_copied_and_listed(built):
    out, _, files = built
    options = mount_options(out)
    assert options["entrypoint"] == "app.py"
    assert sorted(options["files"]) == files
    for name, spec in options["files"].items():
        assert (out / spec["url"]).read_bytes() == (ROOT / name).read_bytes()
    assert all(r.endswith(".whl") or r in build_web.PYODIDE_PACKAGES for r in options["requirements"])
    for wheel in build_web.WHEELS:
        assert (out / "wheels" / wheel.filename).exists()
    assert (out / "404.html").read_text() == (out / "index.html").read_text()


def test_build_is_reproducible(built):
    first, second, _ = built
    listing = lambda folder: sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert listing(first) == listing(second)
    for name in listing(first):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_loading_message(built):
    html = (built[0] / "index.html").read_text()
    assert "Loading Headroom…" in html
    assert "the first visit takes a little longer while the app loads in your browser." in html.lower()


def test_wheels_pinned_by_hash():
    for wheel in build_web.WHEELS:
        assert re.fullmatch(r"[0-9a-f]{64}", wheel.sha256)
        assert wheel.url.startswith("https://files.pythonhosted.org/") and wheel.url.endswith(wheel.filename)

"""Build the browser-only version of Headroom into web/ (served by GitHub Pages).

The browser version is the SAME code as the normal app: this script copies the app's files into
web/app/ and writes web/index.html, which loads stlite (Streamlit running on Pyodide, i.e. Python
compiled to WebAssembly) and mounts app.py. Everything then runs inside the visitor's browser.

Two Python packages that Pyodide doesn't ship (plotly, pdfminer.six) are downloaded once from PyPI,
checked against pinned SHA-256 hashes, and served from web/wheels/. That way the published page
never contacts PyPI, and its Content Security Policy can stay limited to two sources.

The output is reproducible: same source files in, byte-identical web/ out.

    python scripts/build_web.py                       # build web/
    python scripts/build_web.py --timeout-seconds 90  # TESTING ONLY: shorter inactivity timeout
    python -m http.server 8000 -d web                 # then open http://localhost:8000
"""

import argparse
import hashlib
import json
import shutil
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "scripts" / "web_template"
WEB = ROOT / "web"
WHEEL_CACHE = ROOT / ".wheel-cache"

# Pinned stlite release (18 Oct 2026): bundles Streamlit 1.65.0 and Pyodide 314.0.3 (Python 3.14).
STLITE_VERSION = "1.12.0"
STLITE_BASE = f"https://cdn.jsdelivr.net/npm/@stlite/browser@{STLITE_VERSION}/build"

# Every file the app imports or reads, as glob patterns relative to the project root.
# tests/test_web_build.py checks this list against the app's imports and data paths.
APP_PATTERNS = (
    "app.py",
    "app_pages/*.py",
    "engine/**/*.py",
    "ui/*.py",
    "assets/*.css",
    "assets/*.svg",
    "assets/*.jpg",
    "data/*.json",
    "data/*.yaml",
    "data/processed/*",
    "data/samples/*",
    ".streamlit/config.toml",
)


@dataclass(frozen=True)
class Wheel:
    filename: str
    url: str
    sha256: str


# Pure-Python packages not included in Pyodide 314.0.3. Versions match requirements in the local venv.
WHEELS = (
    Wheel(
        "plotly-7.1.0-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/e5/7d/905a3a3d51087515719058c94cfbda2ff0fc14417c20d557ae3e82d8b250/"
        "plotly-7.1.0-py3-none-any.whl",
        "dbb7fa18afce40d0a8e80d1bf162eceb3faa0ce5a77fe741ad09a74cf78f53f3",
    ),
    Wheel(
        "pdfminer_six-20260107-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/20/8b/28c4eaec9d6b036a52cb44720408f26b1a143ca9bce76cc19e8f5de00ab4/"
        "pdfminer_six-20260107-py3-none-any.whl",
        "366585ba97e80dffa8f00cebe303d2f381884d8637af4ce422f1df3ef38111a9",
    ),
    # Dependencies declared by stlite's Streamlit 1.65.0 wheel that Pyodide doesn't ship. Without them
    # here, micropip would look them up on pypi.org on every visit.
    Wheel(
        "itsdangerous-2.2.0-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/04/96/92447566d16df59b2a776c0fb82dbc4d9e07cd95062562af01e408583fc4/"
        "itsdangerous-2.2.0-py3-none-any.whl",
        "c6242fc49e35958c8b15141343aa660db5fc54d4f13a1db01a3f5891b98700ef",
    ),
    Wheel(
        "python_multipart-0.0.32-py3-none-any.whl",
        "https://files.pythonhosted.org/packages/e1/04/e8135ebd1ad02c56ec633277529b2602ff99ff634be76cdba5744cf554fd/"
        "python_multipart-0.0.32-py3-none-any.whl",
        "ff6d3f776f16878c894e52e107296ffc890e913c611b1a4ec6c44e2821fe2e23",
    ),
)


# Packages the app imports that Pyodide 314.0.3 ships ready-built (numpy, pandas and pyyaml have C code).
PYODIDE_PACKAGES = ("numpy", "pandas", "pyyaml")


def app_files(root: Path = ROOT) -> list[str]:
    """The app's files as sorted POSIX paths relative to root (skipping caches)."""
    found = set()
    for pattern in APP_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                found.add(path.relative_to(root).as_posix())
    return sorted(found)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_wheel(wheel: Wheel, cache: Path = WHEEL_CACHE) -> bytes:
    """A wheel's bytes from the local cache, downloading it once if needed. Fails on a hash mismatch."""
    cached = cache / wheel.filename
    if cached.exists() and sha256(cached.read_bytes()) == wheel.sha256:
        return cached.read_bytes()
    try:
        import certifi   # python.org Python has no CA bundle (see CLAUDE.md data notes)
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(wheel.url, context=context, timeout=120) as response:
        data = response.read()
    if sha256(data) != wheel.sha256:
        raise RuntimeError(f"{wheel.filename}: SHA-256 doesn't match the pinned hash")
    cache.mkdir(exist_ok=True)
    cached.write_bytes(data)
    return data


def mount_options(files: list[str], timeout_seconds: int | None = None) -> dict:
    """The options passed to stlite's mount(): entrypoint, app files, wheels and environment."""
    options = {
        "entrypoint": "app.py",
        # Fetched from this same site (relative URLs), then placed in Pyodide's in-memory file system.
        "files": {name: {"url": f"app/{name}"} for name in files},
        # Pyodide's own builds (loaded from its CDN), then the wheels served from this site.
        "requirements": list(PYODIDE_PACKAGES) + [f"wheels/{wheel.filename}" for wheel in WHEELS],
        "streamlitConfig": {"browser.gatherUsageStats": False, "client.toolbarMode": "viewer"},
        "env": {},
        "disableProgressToasts": True,   # index.html shows its own loading screen instead
    }
    if timeout_seconds:
        options["env"]["HEADROOM_TIMEOUT_SECONDS"] = str(timeout_seconds)   # testing only
    return options


def render(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def build(out: Path = WEB, timeout_seconds: int | None = None, root: Path = ROOT) -> list[str]:
    """Write the browser build to out/ (replacing what's there). Returns the app files included."""
    if out.exists():
        shutil.rmtree(out)
    (out / "app").mkdir(parents=True)
    (out / "wheels").mkdir()

    files = app_files(root)
    for name in files:
        target = out / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    for wheel in WHEELS:
        (out / "wheels" / wheel.filename).write_bytes(fetch_wheel(wheel))

    options = json.dumps(mount_options(files, timeout_seconds), indent=2, sort_keys=True)
    values = {"STLITE_BASE": STLITE_BASE, "STLITE_VERSION": STLITE_VERSION, "MOUNT_OPTIONS": options}
    for name in ("index.html", "headroom.js", "loading.css"):
        (out / name).write_text(render((TEMPLATE_DIR / name).read_text(encoding="utf-8"), **values), encoding="utf-8")
    # GitHub Pages serves 404.html for unknown paths, so reloading a page such as /statement_analyser
    # starts the app again (stlite then opens that page) instead of showing an error.
    shutil.copyfile(out / "index.html", out / "404.html")
    (out / "favicon.svg").write_bytes((root / "assets" / "favicon.svg").read_bytes())
    (out / ".nojekyll").write_text("")   # GitHub Pages: serve files as they are
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=WEB)
    parser.add_argument("--timeout-seconds", type=int, help="TESTING ONLY: shorter inactivity timeout")
    args = parser.parse_args()
    files = build(args.out, args.timeout_seconds)
    print(f"Built {args.out} with {len(files)} app files and {len(WHEELS)} wheels (stlite {STLITE_VERSION}).")


if __name__ == "__main__":
    main()

# Headroom — your mortgage reality check

A multi-page Streamlit app that helps Australians see whether a mortgage is realistic for their
income, lifestyle and the risk of rate rises. It is a portfolio project for GitHub and a resume, so
code quality, clear structure and the author's understanding of the code all matter. The author
knows Python from university.

## Structure

```
MortageChecker/
├── app.py                 Entry point: page config, CSS, first-visit disclaimer dialog, st.navigation, footer
├── app_pages/             One file per page (display only)
│   ├── home.py            Hero (main CTA: Statement Analyser), what the app does, market at a glance
│   ├── statement_analyser.py Sample/upload statements -> review -> "Use these numbers" pre-fills the Calculator
│   ├── calculator.py      Inputs (incl. upfront costs & savings) and results in expanders
│   ├── stress_scenarios.py Preset + custom life-event scenarios over 36 months, using Calculator inputs
│   ├── risk_simulator.py  Monte Carlo results: probabilities, fan charts, worst 5%, single-guess comparison
│   ├── market_snapshot.py Every market figure with date and source
│   ├── learn.py           Plain-English explainers with official links
│   └── about.py           Full disclaimer, key assumptions, about the project
├── ui/                    Shared display helpers (no calculations)
│   ├── components.py      money(), md_safe(), cards, hero, footer, disclaimer dialog
│   ├── calculator_state.py Calculator inputs in session state + household_from_inputs() (shared by pages)
│   ├── privacy.py         uploads_allowed() (browser, or HEADROOM_ALLOW_UPLOADS), notices, clear_statement_data()
│   ├── session_guard.py   10-minute inactivity timeout: statement namespace, touch/expire/wipe, status fragment
│   ├── charts.py          Plotly template "headroom" matching the theme
│   └── disclaimer.py      Disclaimer and assumptions wording (single source)
├── engine/                All calculations. Pure Python, NO Streamlit imports
│   ├── runtime.py         IS_BROWSER (sys.platform == "emscripten"): server Python vs stlite/Pyodide in the browser
│   ├── tax.py             AU resident tax 2026-27 (scalar take_home + vectorised take_home_array)
│   ├── loan.py            P&I repayments, max loan, borrowing power (APRA buffer), rate stress table
│   ├── budget.py          Lifestyle cost presets (placeholders), stress ratio/labels, 30%-rule check
│   ├── costs.py           NSW stamp duty + FHBAS, indicative LMI, 5% Deposit Scheme, fees, purchase_summary
│   ├── projection.py      Vectorised month-by-month projection on input ARRAYS (base for Phase 3)
│   ├── scenarios.py       Life events + stress presets that build projection input arrays
│   ├── simulation.py      Monte Carlo: block bootstrap of history, random job loss, runs projection.py
│   ├── market.py          Loads and validates data/market_snapshot.json
│   └── statements/        Statement Analyser: redact.py, parse.py (CSV/PDF), pdf_text.py (PDF backends),
│                          categorise.py, analyse.py, accuracy.py
├── data/market_snapshot.json  SINGLE source for all displayed market figures
├── data/categories.yaml   Editable keyword rules for statement categorisation
├── data/samples/          SYNTHETIC statements ("Sample Bank") + ground truth, from scripts/make_samples.py
├── data/raw/              Original RBA/ABS downloads (from scripts/update_data.py)
├── data/processed/        Clean monthly CSVs + metadata.json; history.csv feeds the simulator
├── scripts/update_data.py Downloads official RBA (A2, F5, F6) and ABS (CPI, WPI) data and processes it
├── scripts/make_samples.py Generates the synthetic sample statements (needs requirements-dev.txt)
├── scripts/build_web.py   Builds the browser-only version into web/ (stlite pin, file list, pinned wheels)
├── scripts/web_template/  index.html (CSP + loading screen), headroom.js (mount), loading.css
├── web/                   BUILD OUTPUT (gitignored). Deployed to GitHub Pages by .github/workflows/pages.yml
├── assets/favicon.svg     Page icon (house + upward arrow), drawn for this project
├── assets/style.css       ALL custom CSS (loaded once by ui.components.load_css)
├── assets/hero.jpg        Hero photo (added by the author; gradient fallback if missing)
├── .streamlit/config.toml Theme, telemetry off, closed-session TTL
├── tests/                 pytest tests for engine/ (incl. JSON-vs-engine consistency)
└── pytest.ini             Puts the project root on the path so tests can import engine
```

- The engine is kept free of UI code so it can be reused later (e.g. a mobile app backend).
- Environment: `.venv` with Python 3.14.
  - Run the app: `.venv/bin/streamlit run app.py`
  - Run the tests: `.venv/bin/python -m pytest`
  - Refresh historical data (manual, needs internet): `.venv/bin/python scripts/update_data.py`
  - Local use with statement uploads: `HEADROOM_ALLOW_UPLOADS=1 .venv/bin/streamlit run app.py`
  - Test the timeout quickly: `HEADROOM_ALLOW_UPLOADS=1 HEADROOM_TIMEOUT_SECONDS=90 .venv/bin/streamlit run app.py`
    (testing only; the default is 600 seconds)
  - Regenerate samples + accuracy report: `.venv/bin/python scripts/make_samples.py --report`
  - Browser build: `.venv/bin/python scripts/build_web.py`, then `.venv/bin/python -m http.server 8000 -d web`
    and open http://localhost:8000 (`--timeout-seconds 90` for a quick timeout test build; never deploy that)
- **The app never downloads data at runtime.** It reads data/processed/ only.

## Two runtimes, one codebase

- **Server** (`streamlit run app.py`, locally or Streamlit Community Cloud): normal Python.
- **Browser** (GitHub Pages, https://kdawg2104.github.io/MortageChecker/): stlite runs the SAME app.py inside
  the visitor's browser on Pyodide (Python compiled to WebAssembly). Never fork app logic; branch on
  `engine.runtime.IS_BROWSER` only where behaviour must differ (upload gating, notice wording).
- Pinned: `@stlite/browser@1.12.0` = Streamlit 1.65.0 + Pyodide 314.0.3 (Python 3.14, pandas 3, numpy 2.4).
  Code must work on Streamlit 1.65 (local venv is newer): check new Streamlit APIs before using them.
- Pyodide ships numpy, pandas, pyyaml, pyarrow. plotly, pdfminer.six and two Streamlit dependencies
  (itsdangerous, python-multipart) are pure-Python wheels that build_web.py downloads once, checks against
  pinned SHA-256 hashes and serves from web/wheels/, so the site never contacts PyPI.
- pdfplumber can't run in Pyodide (it imports pypdfium2, a C extension). `engine/statements/pdf_text.py` falls
  back to pdfminer.six with layout settings that give identical transactions (tests/test_pdf_text.py).
- New file the app reads? It must match `APP_PATTERNS` in build_web.py (tests/test_web_build.py checks).
- Measured (Oct 2026): Monte Carlo 5,000 futures takes 0.06 s in Pyodide, same as native, so no browser-only
  simulation limit. App start-up ~10–20 s with a warm cache; a cold first visit downloads roughly 50 MB (Pyodide + packages ~36 MB, wheels 16 MB), cached after.
- `st.spinner` doesn't show during blocking calls in stlite, and `time.sleep` is a no-op.

## Streamlit gotchas (learned the hard way)

- Page files live in `app_pages/`, NOT `pages/`. A folder named `pages/` triggers Streamlit's legacy
  auto-navigation, which bypasses app.py on direct URLs.
- `st.markdown` treats text between two `$` signs as LaTeX maths. Wrap any text with dollar amounts
  in `md_safe()` (or `html_safe()` inside HTML cards).
- Use `st.page_link` / `st.switch_page` for internal links. A plain `<a href>` reloads the page and
  starts a new session, losing inputs and re-showing the disclaimer.
- Streamlit discards widget values when you leave a page. The calculator saves inputs to
  `st.session_state["calculator_inputs"]` via `on_change` (the `remember()` helper) and restores them.

## Phases

1. **Done:** core tax, loan and budget engine with a Streamlit interface.
   - **1.5 Done:** multi-page layout, market snapshot, learning hub and disclaimers.
2. **Done:** upfront costs (NSW duty, LMI, 5% Deposit Scheme, fees), savings buffer, life events and
   combined stress scenarios.
   - **2.5 Done:** Statement Analyser (synthetic demo data, local-only processing, rules-based categories),
     plus a 10-minute inactivity timeout with automatic data wipe.
3. **Done:** Monte Carlo simulation of rates, inflation and wage growth using historical RBA/ABS data
   (Risk Simulator page). History windows: since Oct 1997 (WPI start) or since 2010.
4. Insights: probability of stress, savings runway, break points, risk-driver chart, "what to change" suggestions.
5. Quick/advanced modes, deployment to Streamlit Community Cloud, GitHub README.

Only build the phase that is asked for.

## Data notes

- Cash rate = month-end target built from RBA A2 decisions (F1.1 is only a monthly average).
- ABS replaced quarterly CPI with monthly CPI: quarterly (final release Sep qtr 2025) is used to Sep 2025,
  monthly from Oct 2025. Quarterly series are spread evenly: (1 + g)^(1/3) - 1 per month.
- The python.org Python has no CA bundle, so update_data.py uses certifi (certificate checks stay on).

## Phase 3 foundation

`engine/projection.py` is the base for the Monte Carlo simulation. `project()` takes month-by-month
arrays (rate, per-borrower income multiplier, expenses, one-off costs) that may carry leading batch
dimensions, e.g. `(n_sims, months)`; it loops only over months, never simulations, and taxes income with
`take_home_array`. `tests/test_projection.py::test_batched_inputs_match_single_runs` guards this.
`engine/scenarios.py` events edit those arrays, so Phase 3 can reuse them as random shocks.

## Privacy rules (Statement Analyser) — non-negotiable

1. Statement data is processed IN MEMORY ONLY. Never write uploaded files or parsed transactions to disk,
   logs, caches (no st.cache_data on statement data), databases or temp files.
2. No network calls during parsing/categorisation. No external APIs, no AI services. Everything runs locally.
3. Upload gating (`ui/privacy.py::uploads_allowed`):
   - Browser build (stlite): ON automatically, because files never leave the device. Notice: read inside your
     web browser, never uploaded, never saved, deleted after 10 minutes of inactivity / "Clear my data" /
     closing or refreshing the tab. Plus a "How to verify this yourself" expander (DevTools → Network).
   - Local Python with HEADROOM_ALLOW_UPLOADS=1: ON, with the "processed on this computer only" notice.
   - Any other server deployment (e.g. Streamlit Community Cloud): OFF; samples only, with the note
     "Upload is disabled in the online demo for privacy. Run the app locally to analyse your own statements."
4. Strip sensitive details immediately after parsing: account numbers, BSBs, card numbers, names, addresses,
   and reference numbers in descriptions (regex-based redaction). Never display raw statement headers.
5. "Clear my data" button that wipes all statement data from st.session_state.
6. Disable Streamlit telemetry: in .streamlit/config.toml set [browser] gatherUsageStats = false.
7. Prevent real statements reaching GitHub: .gitignore has /private/, /statements/ (root folders only, so
   engine/statements/ code is still tracked), *.ofx, *.qif, *.pdf, *.csv
   except data/samples/, data/processed/ and data/raw/ (public RBA/ABS data). tests/test_privacy.py fails if any
   .pdf/.csv exists outside those folders.
8. Never use real people's data in samples or tests — synthetic only.
9. Browser build: statement data in memory only. No IndexedDB, localStorage, persistent file system
   (no `idbfsMountpoints`), or file writes. Streamlit itself keeps only the theme choice in localStorage.
10. No network code anywhere in engine/, app_pages/ or ui/: no requests, urllib, httpx, http, socket,
    pyodide.http/pyfetch/open_url, js fetch/XMLHttpRequest (tests/test_privacy.py scans for them).
11. web/index.html has a Content-Security-Policy whose sources are ONLY 'self' and https://cdn.jsdelivr.net
    (stlite + Pyodide), each explained in a comment. No other domains, no Google Fonts, analytics or
    trackers; the stlite version is pinned exactly (tests/test_web_build.py).

How it's implemented:
- **One namespace.** All statement data lives in `st.session_state["statement"]` (a dict): transactions,
  reviewed categories, warnings, AND figures copied to the Calculator (`prefill`). Pages read
  `effective_inputs()` (manual inputs overlaid with `prefill`), so when the namespace goes, they fall back to
  the manual form. Widgets showing statement data use keys starting `stmtw_` (widgets can't live in a dict).
- **10-minute inactivity timeout** (`ui/session_guard.py`, `TIMEOUT_SECONDS = 600`, `TIMEOUT_MODE`
  "inactivity" or "absolute"). `guard_rerun()` runs at the start of every normal rerun in app.py: it checks
  the timer FIRST (so a click after a long absence still expires the data), then calls `touch()`.
  `status_fragment()` (`st.fragment(run_every="15s")`) re-checks while the tab sits idle and never calls
  `touch()`. Final minute: "Keep my session" / "Clear now". `wipe()` removes the namespace, `stmtw_*` keys,
  pre-filled `calc_*` widget keys and `calc_last_suggested`, bumps the uploader key, then `gc.collect()`.
- **Closed tabs:** `server.disconnectedSessionTTL = 60` in .streamlit/config.toml; Streamlit frees the session
  lazily, at some point after that, so the notice says "within about a minute of closing the tab". In the
  browser build, closing or refreshing the tab destroys the Python runtime (and all data) at once.
- **Timeout in the browser:** `st.fragment(run_every=...)` works in stlite 1.12.0 (tested: a 75-second test
  build wiped the data and showed the expired message), so session_guard.py is used unchanged; no JS timer.
- **Honest limits:** deleting releases memory; Python can't guarantee the bytes are overwritten immediately.
  The browser guarantee rests on the published code + CSP; visitors trust that GitHub Pages serves this repo's
  code and that jsDelivr serves the pinned packages unmodified (no subresource-integrity hashes yet).
- No `st.cache_*` in any page or helper that touches statement figures (tested). `engine/statements/` works on
  bytes/DataFrames; tests check it has no network, file-writing, logging or caching code and that parsing
  writes no files. Sample merchants are real businesses; people, employers and the bank ("Sample Bank") are
  fictional. `sample_jamie_*` is built to an exact spec (88 transactions, $40,000.00 → $49,322.77).

## Rules

- Keep calculations in engine/ and UI in app_pages/ and ui/. Never mix them.
- Any tax, lending or economic figure must be a named constant with its source and year in a comment.
- Market figures shown to users come only from data/market_snapshot.json (fields: id, name, value,
  unit, as_at, source, url, notes, plus category and decimals). Engine constants that duplicate a
  JSON figure must be covered by a consistency test in tests/test_market.py.
- Use official sources only for market data (RBA, ABS, APRA, ATO, Cotality, Moneysmart, Revenue NSW,
  NSW LRS, Housing Australia). No comparison sites. **One agreed exception:** LMI premiums, which no
  insurer or regulator publishes. engine/costs.py uses a cited broker-published table, labelled in the
  UI as an "indicative estimate".
- Custom CSS goes only in assets/style.css.
- Prefer clear, readable code over clever code; add short docstrings.
- Explain new functions to the user in plain English after writing them.
- Install packages with separate pip install commands, one per package.
- Don't add features from later phases unless asked.
- When committing, stage named paths only (never `git add -A`): the folder can contain the author's own
  untracked files (e.g. Photo2.jpg).
- No bank branding or bank names anywhere in the app.
- Every page shows the footer "General information only — not financial advice." with a link to About & Disclaimer.

## Known placeholders

- `engine/budget.py`: lifestyle presets, couple multiplier, per-dependant cost and the $1,000
  LOW_BUFFER_THRESHOLD are PLACEHOLDERS, to be replaced with ABS household spending data later.
- `engine/costs.py`: conveyancing, building & pest, lender fees and moving costs are PLACEHOLDER
  estimates (editable in the UI). LMI rates are indicative (see the rule above).
- Stamp duty is NSW only; other states are listed in `STATES` as "coming soon".
- `app_pages/home.py`: `HERO_PHOTO_CREDIT` needs the photographer's name once assets/hero.jpg is added.
- The RBA F6 default rate (Aug 2026) predates the 29 Sep 2026 cash rate rise. Update the JSON when
  the next F6 release is out.

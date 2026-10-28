# Headroom

*Your mortgage reality check.*

A Streamlit app that helps Australians see whether a mortgage is realistic for their income, lifestyle and
the risk of rate rises. General information only, not financial advice.

> **Status: work in progress.** Phases 1–3 (calculator, stress scenarios, statement analyser, Monte Carlo
> risk simulator) are built; insights, quick/advanced modes and deployment are still to come. A fuller README
> (screenshots, deployment, architecture) is planned for Phase 5.

## Features

- **Statement Analyser:** reads 3 months of bank transactions, works out income, spending and debts, lets
  you review every category, and pre-fills the rest of the app. Try it with synthetic sample statements.
- **Calculator:** 2026-27 Australian tax (incl. HECS/HELP), repayments, borrowing power at the APRA buffer,
  NSW stamp duty and first home buyer concessions, indicative LMI and the 5% Deposit Scheme.
- **Stress Scenarios:** 36-month projections with job loss, parental leave, rate rises and expense shocks.
- **Risk Simulator:** Monte Carlo simulation of rates, inflation and wages from RBA and ABS history.
- **Market Snapshot and Learn the Basics:** official figures with sources, and plain-English explainers.

## Statement Analyser

1. **Choose** a sample persona, or upload CSV / text-based PDF statements (when running locally).
2. **Review** what was found: income per earner and pay frequency, essentials, discretionary spending and debts.
3. **Correct** any category in an editable table; uncertain items are marked for checking.
4. **See** spending by category, money in vs out, and what a lender may look at (educational only).
5. **Use these numbers** to pre-fill the Calculator, Stress Scenarios and Risk Simulator.

Categorisation is rules-based (`data/categories.yaml`, human-readable and editable), with no AI services.
Gross income is estimated by inverting the tax engine from observed take-home pay.

## Try it

- **Browser version (your own statements, processed on your device):** https://kdawg2104.github.io/MortageChecker/
- **Streamlit Community Cloud demo (synthetic samples only):** link to be added once deployed.

## Privacy by design

Statement data is sensitive, so Headroom is built so that it never reaches a server.

**The browser version runs entirely on your device.** The GitHub Pages site is static files only. It uses
[stlite](https://github.com/whitphx/stlite) to run the same Python app inside your browser on Pyodide (Python
compiled to WebAssembly). When you upload a statement, the file goes from your disk into the Python running in
that tab, and nowhere else. There is no backend that could receive it.

- **No network calls in the app code.** A test scans `engine/`, `app_pages/` and `ui/` and fails on any network
  library or browser fetch (`requests`, `urllib`, `httpx`, `socket`, `pyfetch`, `open_url`, `js.fetch`...).
- **Content Security Policy.** `web/index.html` tells the browser to block every request except to the site
  itself and `cdn.jsdelivr.net` (which serves the pinned stlite release and Pyodide). Both only serve downloads.
  A test checks the policy allows no other domains. No analytics, trackers or Google Fonts.
- **In memory only.** No IndexedDB, localStorage, file system or caches hold statement data.
- **Automatic deletion.** All statement data, including figures copied into the Calculator, is deleted after
  **10 minutes of inactivity**, when you click **Clear my data**, or when you close or refresh the tab (which
  destroys the in-browser Python runtime). A status chip shows the time left; in the final minute you can choose
  "Keep my session".
- **Redaction.** Account numbers, BSBs, card numbers, personal names and reference numbers are removed as soon
  as a file is read; statement headers are never shown.
- **Verify it yourself.** Open developer tools → Network, clear the list, upload a statement: no request is sent.

**Server deployments are samples-only.** Uploads are switched on automatically in the browser build and locally
with `HEADROOM_ALLOW_UPLOADS=1` (your own computer is the server). Any other server deployment, such as Streamlit
Community Cloud, hides the upload box and offers synthetic samples only.

**Also:** Streamlit telemetry is off; `.gitignore` blocks statement-like files outside the synthetic sample and
public-data folders (a test fails if any appear); the sample statements come from the fictional "Sample Bank".

**Honest limits.** The guarantee rests on the published code and the CSP: you trust that GitHub Pages serves
this repository's code and jsDelivr serves the pinned packages unmodified. The code is open here for anyone to
check. Deleting data releases memory, but Python can't guarantee the old bytes are overwritten immediately.

These rules are enforced by `tests/test_privacy.py`, `tests/test_session_guard.py` (with a fake clock),
`tests/test_runtime_gating.py`, `tests/test_web_build.py` and `tests/test_statement_page.py`.

## Running it

```bash
pip install -r requirements.txt
```

Demo mode (samples only; use this for any online deployment):

```bash
streamlit run app.py
```

Local mode with your own statements:

```bash
HEADROOM_ALLOW_UPLOADS=1 streamlit run app.py
```

To try the timeout without waiting 10 minutes (testing only):

```bash
HEADROOM_ALLOW_UPLOADS=1 HEADROOM_TIMEOUT_SECONDS=90 streamlit run app.py
```

Browser version, built and served locally:

```bash
python scripts/build_web.py && python -m http.server 8000 -d web
```

Then open http://localhost:8000. Pushing to `main` builds and deploys it to GitHub Pages
(`.github/workflows/pages.yml`).

Tests:

```bash
python -m pytest
```

Developer scripts: `scripts/update_data.py` refreshes RBA/ABS history; `scripts/make_samples.py --report`
regenerates the synthetic statements (needs `pip install -r requirements-dev.txt`) and prints categorisation
accuracy.

## Disclaimer

Headroom is an independent personal project, not affiliated with any bank, lender or employer. It provides general information only, does not take into
account your objectives, financial situation or needs, and is not financial advice, credit advice or a loan
approval. See the About & Disclaimer page in the app.

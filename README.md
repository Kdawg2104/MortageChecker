# Mortgage Reality Check

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

## Privacy

Statement data is sensitive, so the analyser is built to keep it on your computer:

- **In memory only.** Files are read from memory, never saved to disk, logs, caches or databases.
- **Automatic deletion.** All statement data, including any figures copied into the Calculator, is deleted
  after **10 minutes of inactivity**, when you click **Clear my data**, or within about a minute of closing
  the tab. A check runs every 15 seconds, so it works even if you walk away; a status chip shows the time
  left, and in the final minute you can choose "Keep my session". Deleting releases the memory; like any
  Python program, the app can't guarantee the old bytes are overwritten immediately.
- **No network calls.** Parsing and categorisation run entirely locally: no external APIs or AI services.
- **Uploads are off by default.** The online demo only offers synthetic samples. Uploading your own
  statements needs the app running locally with `MRC_ALLOW_UPLOADS=1`.
- **Redaction.** Account numbers, BSBs, card numbers, personal names and reference numbers are removed as soon
  as a file is read; statement headers are never shown.
- **No telemetry.** Streamlit usage statistics are switched off.
- **Kept out of git.** `.gitignore` blocks statement-like files (`*.csv`, `*.pdf`, `*.ofx`, `*.qif`) outside the
  synthetic sample and public-data folders, and a test fails if any appear.
- **Synthetic samples only.** The sample statements come from the fictional "Sample Bank" with invented people.

These rules are enforced by tests in `tests/test_privacy.py`, `tests/test_session_guard.py` (with a fake
clock) and `tests/test_statement_page.py`.

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
MRC_ALLOW_UPLOADS=1 streamlit run app.py
```

To try the timeout without waiting 10 minutes (testing only):

```bash
MRC_ALLOW_UPLOADS=1 MRC_TIMEOUT_SECONDS=90 streamlit run app.py
```

Tests:

```bash
python -m pytest
```

Developer scripts: `scripts/update_data.py` refreshes RBA/ABS history; `scripts/make_samples.py --report`
regenerates the synthetic statements (needs `pip install -r requirements-dev.txt`) and prints categorisation
accuracy.

## Disclaimer

This is an independent personal portfolio project. It provides general information only, does not take into
account your objectives, financial situation or needs, and is not financial advice, credit advice or a loan
approval. See the About & Disclaimer page in the app.

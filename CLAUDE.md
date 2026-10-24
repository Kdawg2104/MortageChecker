# Mortgage Reality Check

A multi-page Streamlit app that helps Australians see whether a mortgage is realistic for their
income, lifestyle and the risk of rate rises. It is a portfolio project for GitHub and a resume, so
code quality, clear structure and the author's understanding of the code all matter. The author
knows Python from university.

## Structure

```
MortageChecker/
├── app.py                 Entry point: page config, CSS, first-visit disclaimer dialog, st.navigation, footer
├── app_pages/             One file per page (display only)
│   ├── home.py            Hero, what the app does, market at a glance, disclaimer box
│   ├── calculator.py      Inputs and results in expanders
│   ├── market_snapshot.py Every market figure with date and source
│   ├── learn.py           Plain-English explainers with official links
│   └── about.py           Full disclaimer, key assumptions, about the project
├── ui/                    Shared display helpers (no calculations)
│   ├── components.py      money(), md_safe(), cards, hero, footer, disclaimer dialog
│   └── disclaimer.py      Disclaimer and assumptions wording (single source)
├── engine/                All calculations. Pure Python, NO Streamlit imports
│   ├── tax.py             AU resident tax 2026-27: brackets, LITO, Medicare, HECS/HELP
│   ├── loan.py            P&I repayments, max loan, borrowing power (APRA buffer), rate stress table
│   ├── budget.py          Lifestyle cost presets (placeholders), stress ratio/labels, 30%-rule check
│   └── market.py          Loads and validates data/market_snapshot.json
├── data/market_snapshot.json  SINGLE source for all displayed market figures
├── assets/style.css       ALL custom CSS (loaded once by ui.components.load_css)
├── assets/hero.jpg        Hero photo (added by the author; gradient fallback if missing)
├── .streamlit/config.toml Theme
├── tests/                 pytest tests for engine/ (incl. JSON-vs-engine consistency)
└── pytest.ini             Puts the project root on the path so tests can import engine
```

- The engine is kept free of UI code so it can be reused later (e.g. a mobile app backend).
- Environment: `.venv` with Python 3.14.
  - Run the app: `.venv/bin/streamlit run app.py`
  - Run the tests: `.venv/bin/python -m pytest`

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
2. Combined stress scenarios and life events (job loss, parental leave, expense shocks), stamp duty and LMI.
3. Monte Carlo simulation of rates, inflation and wage growth using historical RBA/ABS data.
4. Insights: probability of stress, savings runway, break points, risk-driver chart, "what to change" suggestions.
5. Quick/advanced modes, deployment to Streamlit Community Cloud, GitHub README.

Only build the phase that is asked for.

## Rules

- Keep calculations in engine/ and UI in app_pages/ and ui/. Never mix them.
- Any tax, lending or economic figure must be a named constant with its source and year in a comment.
- Market figures shown to users come only from data/market_snapshot.json (fields: id, name, value,
  unit, as_at, source, url, notes, plus category and decimals). Engine constants that duplicate a
  JSON figure must be covered by a consistency test in tests/test_market.py.
- Use official sources only for market data (RBA, ABS, APRA, ATO, Cotality, Moneysmart). No comparison sites.
- Custom CSS goes only in assets/style.css.
- Prefer clear, readable code over clever code; add short docstrings.
- Explain new functions to the user in plain English after writing them.
- Install packages with separate pip install commands, one per package.
- Don't add features from later phases unless asked.
- No bank branding or bank names anywhere in the app.
- Every page shows the footer "General information only — not financial advice." with a link to About & Disclaimer.

## Known placeholders

- `engine/budget.py`: lifestyle presets, couple multiplier, per-dependant cost and the $1,000
  LOW_BUFFER_THRESHOLD are PLACEHOLDERS, to be replaced with ABS household spending data later.
- `app_pages/home.py`: `HERO_PHOTO_CREDIT` needs the photographer's name once assets/hero.jpg is added.
- The RBA F6 default rate (Aug 2026) predates the 29 Sep 2026 cash rate rise. Update the JSON when
  the next F6 release is out.

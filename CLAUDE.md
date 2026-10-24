# Mortgage Reality Check

A Streamlit app that helps Australians see whether a mortgage is realistic for their income,
lifestyle and the risk of rate rises. It is a portfolio project for GitHub and a resume, so code
quality, clear structure and the author's understanding of the code all matter. The author knows
Python from university.

## Structure

```
MortageChecker/
├── app.py            Streamlit interface only; imports from engine/
├── engine/           All calculations. Pure Python, NO Streamlit imports
│   ├── tax.py        AU resident tax 2026-27: brackets, LITO, Medicare, HECS/HELP
│   ├── loan.py       P&I repayments, max loan, borrowing power (APRA buffer), rate stress table
│   └── budget.py     Lifestyle cost presets (placeholders), stress ratio and labels
├── tests/            pytest tests for engine/
├── pytest.ini        Puts the project root on the path so tests can import engine
└── requirements.txt
```

The engine is kept free of UI code so it can be reused later (e.g. a mobile app backend).

Environment: `.venv` with Python 3.14.
- Run the app: `.venv/bin/streamlit run app.py`
- Run the tests: `.venv/bin/python -m pytest`

## Phases

1. **Done:** core tax, loan and budget engine with a Streamlit interface.
2. Combined stress scenarios and life events (job loss, parental leave, expense shocks), stamp duty and LMI.
3. Monte Carlo simulation of rates, inflation and wage growth using historical RBA/ABS data.
4. Insights: probability of stress, savings runway, break points, risk-driver chart, "what to change" suggestions.
5. Quick/advanced modes, deployment to Streamlit Community Cloud, GitHub README.

Only build the phase that is asked for.

## Rules

- Keep calculations in engine/ and UI in app.py. Never mix them.
- Any tax, lending or economic figure must be a named constant with its source and year in a comment.
- Prefer clear, readable code over clever code; add short docstrings.
- Explain new functions to the user in plain English after writing them.
- Install packages with separate pip install commands, one per package.
- Don't add features from later phases unless asked.
- No bank branding or bank names anywhere in the app.
- The app must show "General information only — not financial advice."

## Known placeholders

- `engine/budget.py` lifestyle presets, couple multiplier and per-dependant cost are PLACEHOLDERS,
  to be replaced with ABS household spending data in a later phase.

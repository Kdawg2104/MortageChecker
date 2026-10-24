"""Mortgage Reality Check: Streamlit interface.

All calculations live in engine/. This file only collects inputs and displays results.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.budget import LIFESTYLE_PRESETS, living_costs, stress_label, stress_ratio
from engine.loan import (
    APRA_SERVICEABILITY_BUFFER,
    assessment_rate,
    borrowing_power,
    monthly_repayment,
    stress_table,
)
from engine.tax import TAX_YEAR, take_home

MONTHS = 12
LMI_LVR_THRESHOLD = 80  # lenders usually charge LMI above 80% LVR (industry standard)


def money(value: float) -> str:
    """Format a number as whole dollars, e.g. -$1,234."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


st.set_page_config(page_title="Mortgage Reality Check", page_icon="🏠", layout="wide")
st.title("Mortgage Reality Check")
st.write("See whether a mortgage fits your income, your lifestyle and the risk of rate rises.")

# ---------------- Sidebar inputs ----------------
with st.sidebar:
    st.header("You")
    borrowers = st.radio("Number of borrowers", [1, 2], horizontal=True)

    people = []
    for i in range(borrowers):
        income = st.number_input(
            f"Borrower {i + 1} gross annual income ($)",
            min_value=0, value=100_000 if i == 0 else 80_000, step=5_000,
        )
        has_help = st.checkbox(f"Borrower {i + 1} has a HECS/HELP debt", key=f"help_{i}")
        people.append((income, has_help))

    dependants = st.number_input("Number of dependants", min_value=0, max_value=10, value=0)

    st.header("Spending")
    preset = st.selectbox("Lifestyle", list(LIFESTYLE_PRESETS), index=1)
    suggested = living_costs(preset, borrowers, dependants)
    # Refill the expenses field whenever the preset, borrowers or dependants change,
    # but keep any manual edit otherwise.
    if st.session_state.get("last_suggested") != suggested:
        st.session_state["last_suggested"] = suggested
        st.session_state["expenses"] = int(round(suggested))
    expenses = st.number_input(
        "Monthly living expenses, excluding housing ($)",
        min_value=0, step=100, key="expenses",
        help="Pre-filled from the lifestyle preset. Edit it to match your own spending.",
    )
    other_debts = st.number_input(
        "Other monthly debt repayments ($)", min_value=0, value=0, step=50,
        help="Car loans, personal loans, credit card minimums, etc.",
    )

    st.header("Property and loan")
    price = st.number_input("Property price ($)", min_value=0, value=750_000, step=10_000)
    deposit = st.number_input("Deposit ($)", min_value=0, value=150_000, step=5_000)
    rate = st.number_input("Interest rate (% p.a.)", min_value=0.0, max_value=20.0, value=6.5, step=0.05)
    years = st.slider("Loan term (years)", min_value=10, max_value=30, value=30)

# ---------------- Calculations (via engine) ----------------
tax_results = [take_home(income, has_help) for income, has_help in people]
gross_monthly = sum(r.gross for r in tax_results) / MONTHS
net_monthly = sum(r.net for r in tax_results) / MONTHS

loan_amount = max(0, price - deposit)
lvr = loan_amount / price * 100 if price > 0 else 0
repayment = monthly_repayment(loan_amount, rate, years)
left_over = net_monthly - repayment - expenses - other_debts
ratio = stress_ratio(repayment, gross_monthly)

surplus_before_mortgage = net_monthly - expenses - other_debts
max_borrow = borrowing_power(surplus_before_mortgage, rate, years)

# ---------------- Headline metrics ----------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Monthly take-home pay", money(net_monthly))
col2.metric("Monthly repayment", money(repayment))
col3.metric("Left over each month", money(left_over))
col4.metric(
    "Repayment as % of gross income",
    f"{ratio:.0%}" if ratio != float("inf") else "n/a",
    stress_label(ratio),
    delta_color="off",
)

# ---------------- Borrowing power ----------------
st.subheader("Can you borrow this much?")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Loan amount", money(loan_amount))
c2.metric("LVR", f"{lvr:.1f}%")
c3.metric("Assessment rate", f"{assessment_rate(rate):.2f}%")
c4.metric("Estimated borrowing power", money(max_borrow))

if loan_amount == 0:
    st.info("Your deposit covers the full price, so no loan is needed.")
elif loan_amount <= max_borrow:
    st.success(
        f"A lender testing repayments at {assessment_rate(rate):.2f}% "
        f"(your rate + {APRA_SERVICEABILITY_BUFFER:g}% buffer) would likely consider this loan serviceable."
    )
else:
    st.error(
        f"This loan is about {money(loan_amount - max_borrow)} more than your estimated borrowing power "
        f"at the {assessment_rate(rate):.2f}% assessment rate."
    )
if lvr > LMI_LVR_THRESHOLD:
    st.warning(
        f"Your LVR is above {LMI_LVR_THRESHOLD}%, so Lenders Mortgage Insurance (LMI) will likely apply."
    )

# ---------------- Rate rise stress test ----------------
st.subheader("What if rates rise?")
scenarios = stress_table(loan_amount, rate, years)
table = pd.DataFrame(scenarios)
table["left_over"] = net_monthly - table["repayment"] - expenses - other_debts
table["label"] = ["Current" if r == 0 else f"+{r:g}%" for r in table["rise"]]

fig = go.Figure(
    go.Bar(
        x=table["label"],
        y=table["left_over"],
        marker_color=["#d62728" if v < 0 else "#2ca02c" for v in table["left_over"]],
        text=[money(v) for v in table["left_over"]],
        textposition="outside",
    )
)
fig.update_layout(
    yaxis_title="Left over each month ($)",
    xaxis_title="Interest rate scenario",
    xaxis_type="category",  # stop Plotly reading "+1%" as a number
    height=380,
    margin=dict(t=30, b=10),
)
st.plotly_chart(fig, width="stretch")

st.dataframe(
    pd.DataFrame({
        "Scenario": table["label"],
        "Interest rate": [f"{r:.2f}%" for r in table["rate"]],
        "Monthly repayment": [money(v) for v in table["repayment"]],
        "Left over each month": [money(v) for v in table["left_over"]],
    }),
    hide_index=True,
    width="stretch",
)

# ---------------- Tax breakdown ----------------
with st.expander(f"Tax breakdown per person ({TAX_YEAR})"):
    st.dataframe(
        pd.DataFrame(
            {
                f"Borrower {i + 1}": {
                    "Gross income": money(r.gross),
                    "Income tax (after LITO)": money(r.income_tax),
                    "Medicare levy": money(r.medicare),
                    "HECS/HELP repayment": money(r.help),
                    "Take-home (annual)": money(r.net),
                    "Take-home (monthly)": money(r.net / MONTHS),
                }
                for i, r in enumerate(tax_results)
            }
        ),
        width="stretch",
    )

st.caption("General information only — not financial advice.")

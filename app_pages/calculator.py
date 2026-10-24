"""Calculator page: collects household, spending and loan details, then shows the results.

All maths comes from engine/; this page only gathers inputs and displays outcomes.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.budget import (
    LIFESTYLE_PRESETS,
    LOW_BUFFER_THRESHOLD,
    living_costs,
    stress_label,
    stress_ratio,
    thirty_percent_rule_misleading,
)
from engine.loan import (
    APRA_SERVICEABILITY_BUFFER,
    assessment_rate,
    borrowing_power,
    monthly_repayment,
    stress_table,
)
from engine.tax import TAX_YEAR, take_home
from ui.components import get_snapshot, md_safe, money, what_this_means

MONTHS = 12
LMI_LVR_THRESHOLD = 80  # lenders usually charge LMI above 80% LVR (Moneysmart, LMI glossary)

default_rate = get_snapshot().get("avg_variable_rate_new")

DEFAULT_INPUTS = {
    "borrowers": 1,
    "income_0": 100_000,
    "income_1": 80_000,
    "help_0": False,
    "help_1": False,
    "dependants": 0,
    "preset": "Moderate",
    "other_debts": 0,
    "price": 750_000,
    "deposit": 150_000,
    "rate": float(default_rate.value),
    "years": 30,
}
# Streamlit discards widget values when you leave a page. So every input is saved
# into a plain dict ("calculator_inputs") the moment it changes, and all widgets
# are restored from that dict at the start of each run.
saved = st.session_state.setdefault("calculator_inputs", dict(DEFAULT_INPUTS))
for name, value in saved.items():
    st.session_state[f"calc_{name}"] = value


def _save_input(name: str) -> None:
    st.session_state["calculator_inputs"][name] = st.session_state[f"calc_{name}"]


def remember(name: str) -> dict:
    """Widget arguments that link a widget to its saved value."""
    return {"key": f"calc_{name}", "on_change": _save_input, "args": (name,)}


st.title("Calculator")
st.write("Fill in the three sections below. Results update as you type.")

# ---------------- Inputs ----------------
with st.expander("1. Your household", expanded=True, icon=":material/group:"):
    borrowers = st.radio("Number of borrowers", [1, 2], horizontal=True, **remember("borrowers"))
    people = []
    for i in range(borrowers):
        col_income, col_help = st.columns([2, 1], vertical_alignment="bottom")
        income = col_income.number_input(
            f"Borrower {i + 1} gross annual income ($)", min_value=0, step=5_000, **remember(f"income_{i}")
        )
        has_help = col_help.checkbox("Has a HECS/HELP debt", **remember(f"help_{i}"))
        people.append((income, has_help))
    dependants = st.number_input("Number of dependants", min_value=0, max_value=10, **remember("dependants"))

with st.expander("2. Your spending", icon=":material/shopping_cart:"):
    preset = st.selectbox("Lifestyle", list(LIFESTYLE_PRESETS), **remember("preset"))
    suggested = living_costs(preset, borrowers, dependants)
    # Refill expenses when the preset, borrowers or dependants change; keep manual edits otherwise.
    if st.session_state.get("calc_last_suggested") != suggested or "expenses" not in saved:
        st.session_state["calc_last_suggested"] = suggested
        saved["expenses"] = st.session_state["calc_expenses"] = int(round(suggested))
    expenses = st.number_input(
        "Monthly living expenses, excluding housing ($)", min_value=0, step=100, **remember("expenses"),
        help="Pre-filled from the lifestyle preset (placeholder figures). Edit it to match your own spending.",
    )
    other_debts = st.number_input(
        "Other monthly debt repayments ($)", min_value=0, step=50, **remember("other_debts"),
        help="Car loans, personal loans, credit card minimums, etc.",
    )

with st.expander("3. Your loan", icon=":material/home:"):
    col_price, col_deposit = st.columns(2)
    price = col_price.number_input("Property price ($)", min_value=0, step=10_000, **remember("price"))
    deposit = col_deposit.number_input("Deposit ($)", min_value=0, step=5_000, **remember("deposit"))
    rate = st.number_input(
        "Interest rate (% p.a.)", min_value=0.0, max_value=20.0, step=0.05, **remember("rate")
    )
    st.caption(
        f"Default: {default_rate.value:.{default_rate.decimals}f}%, the {default_rate.name.lower()} "
        f"as at {default_rate.as_at} ({default_rate.source}). {default_rate.notes}"
    )
    years = st.slider("Loan term (years)", min_value=10, max_value=30, **remember("years"))

# ---------------- Calculations (via engine) ----------------
tax_results = [take_home(income, has_help) for income, has_help in people]
gross_monthly = sum(r.gross for r in tax_results) / MONTHS
net_monthly = sum(r.net for r in tax_results) / MONTHS

loan_amount = max(0, price - deposit)
lvr = loan_amount / price * 100 if price > 0 else 0
repayment = monthly_repayment(loan_amount, rate, years)
left_over = net_monthly - repayment - expenses - other_debts
ratio = stress_ratio(repayment, gross_monthly)
label = stress_label(ratio)

surplus_before_mortgage = net_monthly - expenses - other_debts
max_borrow = borrowing_power(surplus_before_mortgage, rate, years)
test_rate = assessment_rate(rate)

st.header("Your results")

# ---------------- Summary ----------------
with st.expander("Your summary", expanded=True, icon=":material/summarize:"):
    col1, col2 = st.columns(2)
    col1.metric("Monthly take-home pay", money(net_monthly))
    col2.metric("Monthly repayment", money(repayment))
    col3, col4 = st.columns(2)
    col3.metric("Left over each month", money(left_over))
    col4.metric(
        "Repayment as % of gross income",
        f"{ratio:.0%}" if ratio != float("inf") else "n/a",
        label,
        delta_color="off",
        delta_arrow="off",
    )

    if left_over < 0:
        meaning = (
            f"After repayments and living costs you'd be {money(-left_over)} short each month, "
            "so this loan doesn't fit your current budget."
        )
    else:
        meaning = (
            f"After your repayment, living costs and other debts you'd have about {money(left_over)} "
            "left each month for savings and surprises."
        )
    what_this_means(meaning)

    if thirty_percent_rule_misleading(ratio, loan_amount, max_borrow, left_over):
        reason = (
            "the loan is above your estimated borrowing power"
            if loan_amount > max_borrow
            else f"you'd have less than {money(LOW_BUFFER_THRESHOLD)} a month left over"
        )
        st.warning(
            md_safe(
                'Your repayment is under 30% of gross income, which usually counts as "not in stress". '
                f"But for this household the 30% rule alone can be misleading: {reason}. "
                "Living costs, dependants and other debts matter as much as the ratio."
            ),
            icon=":material/warning:",
        )

# ---------------- Borrowing power ----------------
with st.expander("Can you borrow this much?", icon=":material/account_balance:"):
    col1, col2 = st.columns(2)
    col1.metric("Loan amount", money(loan_amount))
    col2.metric("LVR (loan ÷ price)", f"{lvr:.1f}%")
    col3, col4 = st.columns(2)
    col3.metric("Assessment rate", f"{test_rate:.2f}%")
    col4.metric("Estimated borrowing power", money(max_borrow))

    if loan_amount == 0:
        st.info("Your deposit covers the full price, so no loan is needed.")
    elif loan_amount <= max_borrow:
        st.success(
            f"A lender testing repayments at {test_rate:.2f}% (your rate + "
            f"{APRA_SERVICEABILITY_BUFFER:g}% buffer) would likely consider this loan serviceable."
        )
    else:
        st.error(
            md_safe(
                f"This loan is about {money(loan_amount - max_borrow)} more than your estimated "
                f"borrowing power at the {test_rate:.2f}% assessment rate."
            )
        )
    if lvr > LMI_LVR_THRESHOLD:
        st.warning(
            f"Your LVR is above {LMI_LVR_THRESHOLD}%, so Lenders Mortgage Insurance (LMI) will likely apply."
        )

    what_this_means(
        "lenders check you could still pay if your rate were "
        f"{APRA_SERVICEABILITY_BUFFER:g} percentage points higher. Based on what you have left "
        f"after living costs, that test suggests a maximum loan of about {money(max_borrow)}."
    )

# ---------------- Rate rise stress test ----------------
with st.expander("What if rates rise?", icon=":material/trending_up:"):
    table = pd.DataFrame(stress_table(loan_amount, rate, years))
    table["left_over"] = net_monthly - table["repayment"] - expenses - other_debts
    table["label"] = ["Current" if r == 0 else f"+{r:g}%" for r in table["rise"]]

    fig = go.Figure(
        go.Bar(
            x=table["label"],
            y=table["left_over"],
            marker_color=["#d64545" if v < 0 else "#0e7c7b" for v in table["left_over"]],
            text=[money(v) for v in table["left_over"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        yaxis_title="Left over each month ($)",
        xaxis_title="Interest rate scenario",
        xaxis_type="category",  # stop Plotly reading "+1%" as a number
        height=360,
        margin=dict(t=30, b=10, l=10, r=10),
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

    worst = table.iloc[-1]
    if worst["left_over"] < 0:
        meaning = (
            f"If rates rose {worst['rise']:g} percentage points, your repayment would go up by "
            f"{money(worst['repayment'] - repayment)} a month and your budget would run "
            f"{money(-worst['left_over'])} short."
        )
    else:
        meaning = (
            f"Even if rates rose {worst['rise']:g} percentage points, you'd still have about "
            f"{money(worst['left_over'])} left each month."
        )
    what_this_means(meaning)

# ---------------- Tax breakdown ----------------
with st.expander("How your take-home pay was calculated", icon=":material/receipt_long:"):
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
    total_deductions = sum(r.gross - r.net for r in tax_results)
    what_this_means(
        f"using {TAX_YEAR} Australian resident rates, about "
        f"{money(total_deductions / MONTHS)} a month goes on tax, Medicare and HECS/HELP, "
        f"leaving {money(net_monthly)} a month to live on."
    )

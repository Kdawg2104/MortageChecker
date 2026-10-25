"""Calculator inputs shared between pages.

The Calculator page edits these inputs; the Stress Scenarios page reads them. Both turn
them into engine objects with household_from_inputs(), so the two pages always agree.
"""

import streamlit as st

from engine.budget import living_costs
from engine.costs import DEFAULT_OTHER_COSTS, STATES, PurchaseSummary, purchase_summary
from engine.scenarios import Household
from ui.components import get_snapshot

# Session-state key for each editable "other cost", e.g. "Moving costs" -> "cost_moving_costs"
OTHER_COST_KEYS = {
    label: "cost_" + "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")
    for label in DEFAULT_OTHER_COSTS
}


def default_inputs() -> dict:
    """Starting values for every calculator input."""
    return {
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
        "rate": float(get_snapshot().get("avg_variable_rate_new").value),
        "years": 30,
        "state": "NSW",
        "savings": 200_000,
        "savings_habit": None,
        "first_home_buyer": False,
        "use_scheme": False,
        "scheme_location": "Sydney or NSW regional centre",
        "single_parent": False,
        "capitalise_lmi": True,
        **{key: float(DEFAULT_OTHER_COSTS[label]) for label, key in OTHER_COST_KEYS.items()},
    }


def saved_inputs() -> dict:
    """The calculator inputs for this session, with defaults filled in for anything missing."""
    saved = st.session_state.setdefault("calculator_inputs", {})
    for key, value in default_inputs().items():
        saved.setdefault(key, value)
    return saved


def calculator_visited() -> bool:
    return "calculator_inputs" in st.session_state


def monthly_expenses(inputs: dict) -> float:
    """Living costs: the user's edited figure, or the lifestyle preset if not set yet."""
    if "expenses" in inputs:
        return inputs["expenses"]
    return living_costs(inputs["preset"], inputs["borrowers"], inputs["dependants"])


def other_costs(inputs: dict) -> dict:
    return {label: inputs[key] for label, key in OTHER_COST_KEYS.items()}


def summary_from_inputs(inputs: dict) -> PurchaseSummary:
    """Duty, LMI, fees, loan and savings left, from the calculator inputs."""
    supported = STATES[inputs["state"]]["supported"]
    return purchase_summary(
        price=inputs["price"],
        deposit=inputs["deposit"],
        savings=inputs["savings"],
        state=inputs["state"],
        first_home_buyer=inputs["first_home_buyer"],
        use_scheme=inputs["use_scheme"] and supported,
        scheme_location=inputs["scheme_location"],
        single_parent=inputs["single_parent"],
        capitalise_lmi=inputs["capitalise_lmi"],
        other_costs=other_costs(inputs),
    )


def household_from_inputs(inputs: dict) -> tuple[Household, PurchaseSummary]:
    """The household the stress scenarios run on: real loan and starting buffer included."""
    summary = summary_from_inputs(inputs)
    borrowers = inputs["borrowers"]
    household = Household(
        incomes=tuple(inputs[f"income_{i}"] for i in range(borrowers)),
        has_help=tuple(inputs[f"help_{i}"] for i in range(borrowers)),
        annual_rate=inputs["rate"],
        monthly_expenses=monthly_expenses(inputs),
        other_debts=inputs["other_debts"],
        loan=summary.loan,
        term_years=inputs["years"],
        starting_savings=summary.savings_left,
        savings_cap=inputs["savings_habit"] or None,
    )
    return household, summary

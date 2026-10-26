"""Stress Scenarios page: projects the Calculator's household through combined shocks over 36 months.

Reads the Calculator inputs from session state. All maths comes from engine/scenarios.py
and engine/projection.py; this page only builds scenarios and displays results.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.projection import NEVER
from engine.scenarios import (
    DEFAULT_MONTHS,
    PRESETS,
    ExpenseShock,
    JobLoss,
    LivingCostChange,
    NewDependant,
    ParentalLeave,
    PartTime,
    RateChange,
    run_scenario,
)
from ui.calculator_state import calculator_visited, effective_inputs, household_from_inputs
from ui.components import md_safe, money, statement_badge, what_this_means

CUSTOM = "custom"
SCENARIO_NAMES = {**{key: preset.name for key, preset in PRESETS.items()}, CUSTOM: "Custom"}
LINE_COLOURS = {"base": "#0e7c7b", "mild": "#d9a21b", "severe": "#e07b39", "worst": "#d64545", CUSTOM: "#5b5fc7"}
EVENT_TYPES = (
    "Job loss", "Parental leave", "Going part-time", "Expense shock",
    "New dependant", "Rate change", "Living cost change",
)

visited = calculator_visited()
inputs = effective_inputs()
household, summary = household_from_inputs(inputs)

# Each scenario's editable event list, starting from the presets
events_by_scenario = st.session_state.setdefault(
    "stress_events", {**{key: list(preset.events) for key, preset in PRESETS.items()}, CUSTOM: []}
)

st.title("Stress Scenarios")
statement_badge()
st.write(
    f"What happens to your savings over the next {DEFAULT_MONTHS} months if things go wrong? "
    "Each scenario starts with the buffer you'd have left after buying."
)
if not visited:
    st.info("You haven't filled in the Calculator yet, so this uses its example household.", icon=":material/info:")
    st.page_link("app_pages/calculator.py", label="Go to the Calculator", icon=":material/calculate:")

col1, col2, col3 = st.columns(3)
col1.metric("Starting savings buffer", money(household.starting_savings))
col2.metric("Loan", money(household.loan))
col3.metric("Interest rate", f"{household.annual_rate:.2f}%")
if household.starting_savings < 0:
    st.error(md_safe(f"You'd start {money(-household.starting_savings)} short after buying, so every scenario begins below zero."))


# ---------------- Scenario picker ----------------
st.subheader("Choose scenarios")
preset_columns = st.columns(len(PRESETS))
for column, (key, preset) in zip(preset_columns, PRESETS.items()):
    with column.container(border=True):
        st.markdown(f"**{preset.name}**")
        st.caption(md_safe(preset.description))

selected = st.pills(
    "Scenarios to compare",
    list(SCENARIO_NAMES),
    format_func=SCENARIO_NAMES.get,
    selection_mode="multi",
    default=list(PRESETS),
    key="stress_selected",
)


def borrower_choice(key: str) -> int | None:
    """Pick which borrower an event affects. None means the higher earner."""
    options = [None] + list(range(len(household.incomes)))
    return st.selectbox(
        "Who", options, key=key,
        format_func=lambda b: "Higher earner" if b is None else f"Borrower {b + 1}",
    )


def event_builder(scenario: str) -> None:
    """A small form to add one life event to a scenario."""
    kind = st.selectbox("Add an event", EVENT_TYPES, key=f"kind_{scenario}")
    with st.form(f"add_{scenario}", border=False):
        c1, c2, c3 = st.columns(3)
        if kind in ("Job loss", "Parental leave", "Going part-time"):
            with c1:
                who = borrower_choice(f"who_{scenario}")
            start = c2.number_input("From month", 1, DEFAULT_MONTHS, 1, key=f"start_{scenario}")
            if kind == "Job loss":
                duration = c3.number_input("For how many months", 1, DEFAULT_MONTHS, 3, key=f"dur_{scenario}")
                pct = st.slider("% of income still received", 0, 100, 0, key=f"pct_{scenario}")
                event = JobLoss(who, start, duration, pct)
            elif kind == "Parental leave":
                duration = c3.number_input("For how many months", 1, DEFAULT_MONTHS, 6, key=f"dur_{scenario}")
                pct = st.slider("% of pay received", 0, 100, 0, key=f"pct_{scenario}")
                event = ParentalLeave(who, start, duration, pct)
            else:
                pct = c3.slider("New % of income", 10, 100, 60, key=f"pct_{scenario}")
                event = PartTime(who, start, pct)
        elif kind == "Expense shock":
            month = c1.number_input("In month", 1, DEFAULT_MONTHS, 1, key=f"start_{scenario}")
            amount = c2.number_input("Amount ($)", 0, 200_000, 5_000, step=500, key=f"amt_{scenario}")
            event = ExpenseShock(month, amount)
        elif kind == "New dependant":
            event = NewDependant(c1.number_input("From month", 1, DEFAULT_MONTHS, 1, key=f"start_{scenario}"))
        elif kind == "Rate change":
            start = c1.number_input("From month", 1, DEFAULT_MONTHS, 1, key=f"start_{scenario}")
            change = c2.number_input("Change (percentage points)", -5.0, 10.0, 1.0, step=0.25, key=f"chg_{scenario}")
            event = RateChange(start, change)
        else:
            start = c1.number_input("From month", 1, DEFAULT_MONTHS, 1, key=f"start_{scenario}")
            pct = c2.number_input("Change in living costs (%)", -50.0, 100.0, 5.0, step=1.0, key=f"chg_{scenario}")
            event = LivingCostChange(start, pct)
        if st.form_submit_button("Add event", icon=":material/add:"):
            events_by_scenario[scenario].append(event)
            st.rerun()


def event_list(scenario: str) -> None:
    """Show a scenario's events with a remove button for each."""
    events = events_by_scenario[scenario]
    if not events:
        st.caption("No events: nothing changes in this scenario.")
    for i, event in enumerate(events):
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.markdown(md_safe(f"- {event.describe()}"))
        if c2.button("Remove", key=f"remove_{scenario}_{i}", icon=":material/delete:"):
            events.pop(i)
            st.rerun()


for scenario in selected:
    with st.expander(f"Edit {SCENARIO_NAMES[scenario]}", expanded=scenario == CUSTOM, icon=":material/tune:"):
        event_list(scenario)
        event_builder(scenario)
        if scenario in PRESETS and st.button("Reset to preset", key=f"reset_{scenario}", icon=":material/restart_alt:"):
            events_by_scenario[scenario] = list(PRESETS[scenario].events)
            st.rerun()

if not selected:
    st.info("Pick at least one scenario above.")
    st.stop()

# ---------------- Run scenarios (via engine) ----------------
results = {scenario: run_scenario(household, events_by_scenario[scenario]) for scenario in selected}


def runs_out_text(month: int) -> str:
    return "Never" if month == NEVER else f"Month {month}"


def ratio_text(ratio: float) -> str:
    """Repayment / income; infinite when a month has no income at all (e.g. the only earner's job loss)."""
    return "No income" if np.isinf(ratio) else f"{ratio:.0%}"


st.header("Results")

# ---------------- Summary cards ----------------
CARDS_PER_ROW = 3
for start in range(0, len(selected), CARDS_PER_ROW):
    for column, scenario in zip(st.columns(CARDS_PER_ROW), selected[start:start + CARDS_PER_ROW]):
        result = results[scenario]
        with column.container(border=True):
            st.markdown(f"**{SCENARIO_NAMES[scenario]}**")
            st.metric("Lowest savings", money(float(result.lowest_savings)))
            st.metric("Savings run out", runs_out_text(int(result.first_negative_savings_month)))
            st.metric("Peak repayment / income", ratio_text(float(result.peak_stress_ratio)))

# ---------------- Savings chart ----------------
months_axis = list(range(DEFAULT_MONTHS + 1))
fig = go.Figure()
for scenario in selected:
    savings = np.concatenate([[household.starting_savings], results[scenario].savings])
    fig.add_trace(go.Scatter(
        x=months_axis, y=savings, mode="lines", name=SCENARIO_NAMES[scenario],
        line=dict(color=LINE_COLOURS[scenario], width=3),
        hovertemplate="Month %{x}: $%{y:,.0f}<extra>" + SCENARIO_NAMES[scenario] + "</extra>",
    ))
fig.add_hline(y=0, line=dict(color="#1f2933", width=3), annotation_text="Savings run out", annotation_position="bottom right")
fig.update_layout(
    title="Savings balance over time",
    xaxis_title="Months after buying",
    yaxis_title="Savings ($)",
    yaxis_tickformat="$,.0f",
    height=420,
    margin=dict(t=50, b=10, l=10, r=10),
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig, width="stretch")

# ---------------- Comparison table ----------------
rows = []
for scenario in selected:
    r = results[scenario]
    rows.append({
        "Scenario": SCENARIO_NAMES[scenario],
        "Lowest savings": money(float(r.lowest_savings)),
        f"Savings after {DEFAULT_MONTHS} months": money(float(r.savings[-1])),
        "Savings run out": runs_out_text(int(r.first_negative_savings_month)),
        "First month in stress (30%+)": runs_out_text(int(r.first_stress_month)),
        "First month in severe stress (40%+)": runs_out_text(int(r.first_severe_stress_month)),
        "Peak repayment / income": ratio_text(float(r.peak_stress_ratio)),
        "Highest repayment": money(float(r.repayment.max())),
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------- Takeaway ----------------
sentences = []
for scenario in selected:
    name = SCENARIO_NAMES[scenario]
    month = int(results[scenario].first_negative_savings_month)
    if month == NEVER:
        sentences.append(
            f"In the {name} scenario your savings never run out over {DEFAULT_MONTHS} months "
            f"(lowest point {money(float(results[scenario].lowest_savings))})."
        )
    elif month == 1:
        sentences.append(f"In the {name} scenario your savings run out in the first month.")
    else:
        sentences.append(f"In the {name} scenario your savings last {month - 1} months before running out.")
what_this_means(" ".join(sentences))
st.caption(
    "Assumes a variable-rate P&I loan whose repayment is recalculated when the rate changes, tax thresholds "
    "held at 2026-27 levels, and shocks starting in month 1 unless you change them."
)

"""Risk Simulator page: Monte Carlo simulation of rates, inflation and wages for the Calculator household.

All maths comes from engine/simulation.py (which reuses engine/projection.py); this page only
collects settings and displays results. It reads pre-processed data and never downloads anything.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.budget import stress_label
from engine.projection import NEVER
from engine.scenarios import Household
from engine.simulation import (
    DEFAULT_BLOCK,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_SEED,
    DEFAULT_SIMS,
    DEFAULT_WINDOW,
    HISTORY_WINDOWS,
    HORIZON_CHOICES,
    JOB_LOSS_ANNUAL_CHANCE,
    JOB_LOSS_MONTHS,
    SimulationResult,
    SimulationSettings,
    run_simulation,
)
from ui.calculator_state import calculator_visited, household_from_inputs, saved_inputs
from ui.components import get_snapshot, md_safe, money, what_this_means

METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "metadata.json"
SIM_CHOICES = (1_000, 5_000, 10_000)
BAND_COLOUR = "14, 124, 123"   # theme teal as "r, g, b"


@st.cache_resource(max_entries=4, show_spinner="Simulating thousands of possible futures…")
def simulate(household: Household, cash_rate: float, settings: SimulationSettings) -> SimulationResult:
    """Run (or reuse) a simulation; identical inputs give identical results thanks to the seed."""
    return run_simulation(household, cash_rate, settings)


@st.cache_data
def load_metadata() -> dict:
    return json.loads(METADATA_PATH.read_text())


def pct(value: float) -> str:
    """Format a chance (0-1) as a whole-number percentage, showing small non-zero chances as <1%."""
    if 0 < value < 0.005:
        return "<1%"
    return f"{value:.0%}"


def fan_chart(bands: dict, title: str, y_title: str, tick_format: str, months: int,
              start_value: float | None = None, zero_line: bool = False) -> go.Figure:
    """Percentile bands over time: light 5–95%, darker 25–75%, and the median line."""
    x = np.arange(1, months + 1) / 12
    series = dict(bands)
    if start_value is not None:  # start every band at today's value (year 0)
        x = np.concatenate([[0.0], x])
        series = {p: np.concatenate([[start_value], v]) for p, v in series.items()}
    fig = go.Figure()
    for low, high, alpha, label in ((5, 95, 0.15, "5th–95th percentile"), (25, 75, 0.35, "25th–75th percentile")):
        fig.add_trace(go.Scatter(x=x, y=series[high], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=x, y=series[low], mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor=f"rgba({BAND_COLOUR}, {alpha})", name=label, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=x, y=series[50], mode="lines", name="Median (typical future)",
        line=dict(color=f"rgb({BAND_COLOUR})", width=3),
    ))
    if zero_line:
        fig.add_hline(y=0, line=dict(color="#1f2933", width=3), annotation_text="Savings run out",
                      annotation_position="bottom right")
    fig.update_layout(
        title=title, xaxis_title="Years after buying", yaxis_title=y_title, yaxis_tickformat=tick_format,
        height=420, margin=dict(t=50, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.2),
        hovermode="x unified",
    )
    return fig


visited = calculator_visited()
household, summary = household_from_inputs(saved_inputs())
cash_rate = get_snapshot().get("cash_rate")
metadata = load_metadata()

st.title("Risk Simulator")
st.write(
    "Instead of testing one guess, this simulates thousands of possible futures for interest rates, "
    "inflation and wages, built from real Australian history, and counts how often your household gets into trouble."
)
if not visited:
    st.info("You haven't filled in the Calculator yet, so this uses its example household.", icon=":material/info:")
    st.page_link("app_pages/calculator.py", label="Go to the Calculator", icon=":material/calculate:")
if household.starting_savings < 0:
    st.error(md_safe(f"You'd start {money(-household.starting_savings)} short after buying, so savings begin below zero."))

# ---------------- Settings ----------------
settings = st.session_state.get("sim_settings", SimulationSettings())
with st.form("sim_settings_form"):
    st.markdown("**Simulation settings**")
    c1, c2 = st.columns(2)
    window = c1.selectbox("History to sample from", list(HISTORY_WINDOWS), index=list(HISTORY_WINDOWS).index(settings.window))
    horizon = c2.segmented_control(
        "How far ahead", HORIZON_CHOICES, default=settings.horizon_years, format_func=lambda y: f"{y} years"
    )
    n_sims = st.select_slider(
        "Number of simulated futures", SIM_CHOICES, value=settings.n_sims, format_func=lambda n: f"{n:,}",
        help="More futures give steadier percentages but take a little longer.",
    )
    include_job_loss = st.toggle("Include job-loss risk", value=settings.include_job_loss)
    c3, c4 = st.columns(2)
    chance = c3.number_input(
        "Chance each earner loses their job in a year (%)", 0.0, 50.0, settings.job_loss_chance * 100, step=0.5,
        help=f"Default {JOB_LOSS_ANNUAL_CHANCE:.0%} is a placeholder assumption, not an official figure.",
    )
    months_out = c4.number_input("Months without income each time", 1, 24, settings.job_loss_months)
    with st.expander("Advanced"):
        c5, c6 = st.columns(2)
        block = c5.number_input(
            "Block length (months)", 3, 36, settings.block_length,
            help="History is sampled in runs of consecutive months, so realistic sequences (like a run of rate rises) are kept.",
        )
        seed = c6.number_input("Random seed", 0, 1_000_000, settings.seed, help="Same seed, same results.")
    if st.form_submit_button("Run simulation", type="primary", icon=":material/play_arrow:"):
        settings = SimulationSettings(
            n_sims=n_sims, horizon_years=horizon or DEFAULT_HORIZON_YEARS, window=window, block_length=block,
            seed=seed, include_job_loss=include_job_loss, job_loss_chance=chance / 100, job_loss_months=months_out,
        )
        st.session_state["sim_settings"] = settings

result = simulate(household, cash_rate.value, settings)
months = settings.months
years = settings.horizon_years
p = result.projection

# ---------------- Headline ----------------
st.header("Results")
st.caption(
    f"{settings.n_sims:,} futures over {years} years, sampled from {result.history_range[0]} to "
    f"{result.history_range[1]}{', including job-loss risk' if settings.include_job_loss else ''}."
)
c1, c2 = st.columns(2)
c1.metric("Chance of mortgage stress (30%+)", pct(result.chance_of_stress), border=True,
          help="Share of futures where repayments reach 30% of gross income in at least one month.")
c2.metric("Chance of severe stress (40%+)", pct(result.chance_of_severe_stress), border=True)
c3, c4 = st.columns(2)
c3.metric("Chance savings run out", pct(result.chance_savings_run_out), border=True,
          help="Share of futures where your savings balance drops below $0 at some point.")
median_month = result.median_months_until_run_out
c4.metric(
    "Typical time until they run out",
    "Doesn't happen" if median_month is None else f"{median_month:.0f} months",
    border=True, help="Median month savings first go below $0, among the futures where they do.",
)

chance_out = result.chance_savings_run_out
if chance_out == 0:
    takeaway = f"in none of the {settings.n_sims:,} simulated futures do your savings run out within {years} years."
else:
    one_in = max(1, round(1 / chance_out))
    takeaway = (
        f"in about 1 in {one_in} simulated futures ({pct(chance_out)}) your savings run out, typically after "
        f"about {median_month:.0f} months ({median_month / 12:.1f} years)."
    )
takeaway += f" Repayments reach 30% of your income at some point in {pct(result.chance_of_stress)} of futures."
what_this_means(takeaway)

# ---------------- Fan charts ----------------
tab_savings, tab_rate, tab_repayment = st.tabs(["Savings balance", "Mortgage rate", "Monthly repayment"])
with tab_savings:
    st.plotly_chart(fan_chart(result.savings_bands, "Savings balance", "Savings ($)", "$,.0f", months,
                              start_value=household.starting_savings, zero_line=True), width="stretch")
with tab_rate:
    st.plotly_chart(fan_chart({k: v / 100 for k, v in result.rate_bands.items()}, "Mortgage interest rate",
                              "Rate (% p.a.)", ".1%", months, start_value=household.annual_rate / 100), width="stretch")
with tab_repayment:
    st.plotly_chart(fan_chart(result.repayment_bands, "Monthly repayment", "Repayment ($)", "$,.0f", months),
                    width="stretch")
st.caption("The shaded bands show where most futures fall: the darker band holds the middle half, the lighter band 90%.")

# ---------------- Worst 5% ----------------
worst = result.worst_summary
with st.container(border=True):
    st.subheader("The worst 5% of futures")
    st.caption("The 1 in 20 futures with the lowest savings, averaged. A household version of 'value at risk'.")
    w1, w2 = st.columns(2)
    w1.metric("Average lowest savings", money(worst["lowest_savings"]))
    w2.metric(f"Average savings after {years} years", money(worst["final_savings"]))
    w3, w4 = st.columns(2)
    w3.metric("Average peak mortgage rate", f"{worst['peak_mortgage_rate']:.2f}%")
    w4.metric("Of these, savings run out in", pct(worst["share_run_out"]))

# ---------------- Comparison with the single scenario ----------------
st.subheader("One guess vs thousands of futures")
single = result.single_scenario
ratio_today = float(single.stress_ratio[0])
single_run_out = int(single.first_negative_savings_month)
final_rates = result.economy.mortgage_rate[:, -1]
comparison = pd.DataFrame({
    "Measure": [
        "Repayment / gross income",
        "Savings run out",
        "Lowest savings",
        f"Mortgage rate in {years} years",
    ],
    "Single guess (nothing changes)": [
        "n/a" if np.isinf(ratio_today) else f"{ratio_today:.0%} ({stress_label(ratio_today).lower()})",
        "Never" if single_run_out == NEVER else f"Month {single_run_out}",
        money(float(single.lowest_savings)),
        f"{household.annual_rate:.2f}%",
    ],
    "Simulation": [
        f"{pct(result.chance_of_stress)} chance of 30%+ at some point",
        f"{pct(result.chance_savings_run_out)} chance",
        f"Median {money(float(np.median(p.lowest_savings)))}; worst 5% average {money(worst['lowest_savings'])}",
        f"Middle 90%: {np.percentile(final_rates, 5):.1f}% to {np.percentile(final_rates, 95):.1f}%",
    ],
})
st.dataframe(comparison, hide_index=True, width="stretch")
what_this_means(
    "the single guess assumes rates, prices and pay never change. The simulation shows how wide the range of "
    "realistic outcomes is, and how likely the bad ones are."
)

# ---------------- How it works ----------------
with st.expander("How this works", icon=":material/help:"):
    series = metadata["series"]
    st.markdown(md_safe(f"""
1. **Real history.** Month-by-month changes in the RBA cash rate, ABS consumer prices (CPI) and the ABS Wage
   Price Index, lined up so each row is the same calendar month.
2. **Block bootstrap.** Each simulated future is stitched together from random **{settings.block_length}-month
   runs of consecutive history**. Taking all three series from the same months keeps their real relationship,
   e.g. rate rises tending to come with high inflation.
3. **Your rate moves with the cash rate.** Today's cash rate ({cash_rate.value:.2f}%) plus the sampled changes,
   never below 0.10%. Your lender's margin ({household.annual_rate - cash_rate.value:+.2f} points) stays the same.
4. **Your household, month by month.** Pay grows with wages (taxed with 2026-27 rules, so no bracket indexation),
   living costs grow with prices, repayments are recalculated when the rate changes, and the surplus goes to savings:
   the same engine as Stress Scenarios.

**Data** (official sources, downloaded {metadata['downloaded']}):
- RBA cash rate decisions (table A2): {series['cash_rate']['start']} to {series['cash_rate']['end']}
- ABS CPI (quarterly to Sep 2025, then monthly): {series['cpi_growth']['start']} to {series['cpi_growth']['end']}
- ABS Wage Price Index: {series['wage_growth']['start']} to {series['wage_growth']['end']}

Quarterly figures are spread evenly across their three months.

**Limits.** Rate changes are added up without anything pulling them back to "normal", so over 10 years the range of
rates gets wide (in reality the RBA moves rates back toward a neutral level). Other debts stay fixed, and the lender's
margin never changes. This is based on past patterns, **not a forecast**: the future can include things history doesn't.
"""))

import numpy as np
import pytest

from engine.budget import COST_PER_DEPENDANT
from engine.scenarios import (
    PRESETS,
    ExpenseShock,
    Household,
    JobLoss,
    LivingCostChange,
    NewDependant,
    ParentalLeave,
    PartTime,
    RateChange,
    build_inputs,
    run_scenario,
)
from engine.tax import take_home

HOUSEHOLD = Household(
    incomes=(120_000, 80_000),
    has_help=(False, True),
    annual_rate=6.2,
    monthly_expenses=4_760,
    other_debts=200,
    loan=650_000,
    term_years=30,
    starting_savings=40_000,
)


@pytest.mark.parametrize("months_lost", [1, 3, 6])
def test_job_loss_costs_exactly_that_take_home(months_lost):
    base = run_scenario(HOUSEHOLD)
    hit = run_scenario(HOUSEHOLD, [JobLoss(borrower=1, start=4, duration=months_lost)])
    monthly_take_home = take_home(80_000, has_help=True).net / 12
    assert base.savings[-1] - hit.savings[-1] == pytest.approx(months_lost * monthly_take_home)


def test_expense_shock_reduces_savings_from_that_month():
    base = run_scenario(HOUSEHOLD)
    hit = run_scenario(HOUSEHOLD, [ExpenseShock(month=10, amount=7_500)])
    difference = base.savings - hit.savings
    assert difference[:9] == pytest.approx(np.zeros(9))
    assert difference[9:] == pytest.approx(np.full(27, 7_500))


def test_rate_change_from_month():
    inputs = build_inputs(HOUSEHOLD, [RateChange(start=13, change_pp=2.0)])
    assert inputs.annual_rate[11] == pytest.approx(6.2)
    assert inputs.annual_rate[12] == pytest.approx(8.2)


def test_rate_cannot_go_negative():
    inputs = build_inputs(HOUSEHOLD, [RateChange(start=1, change_pp=-10)])
    assert inputs.annual_rate.min() == 0


def test_part_time_is_ongoing():
    inputs = build_inputs(HOUSEHOLD, [PartTime(borrower=0, start=7, pct=60)])
    assert inputs.income_multiplier[0, 5] == 1.0
    assert inputs.income_multiplier[0, 6:] == pytest.approx(np.full(30, 0.6))


def test_parental_leave_pays_partial_income():
    inputs = build_inputs(HOUSEHOLD, [ParentalLeave(borrower=1, start=2, duration=4, pay_pct=50)])
    assert inputs.income_multiplier[1, 1:5] == pytest.approx(np.full(4, 0.5))
    assert inputs.income_multiplier[1, 5] == 1.0


def test_new_dependant_adds_cost():
    inputs = build_inputs(HOUSEHOLD, [NewDependant(start=5)])
    assert inputs.expenses[4] - inputs.expenses[3] == pytest.approx(COST_PER_DEPENDANT)


def test_living_cost_change():
    inputs = build_inputs(HOUSEHOLD, [LivingCostChange(start=1, pct=10)])
    assert inputs.expenses[0] == pytest.approx(4_760 * 1.1)


def test_unnamed_borrower_is_the_higher_earner():
    inputs = build_inputs(HOUSEHOLD, [JobLoss(start=1, duration=2)])
    assert inputs.income_multiplier[0, :2] == pytest.approx([0, 0])
    assert inputs.income_multiplier[1, :2] == pytest.approx([1, 1])


def test_event_for_missing_borrower_is_ignored():
    single = Household((90_000,), (False,), 6.2, 2_800, 0, 500_000, 30, 20_000)
    inputs = build_inputs(single, [JobLoss(borrower=1, start=1, duration=3)])
    assert inputs.income_multiplier == pytest.approx(np.ones((1, 36)))


def test_presets_get_progressively_worse():
    lowest = [float(run_scenario(HOUSEHOLD, PRESETS[key].events).lowest_savings) for key in ("base", "mild", "severe", "worst")]
    assert lowest == sorted(lowest, reverse=True)

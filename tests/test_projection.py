import numpy as np
import pytest

from engine.loan import monthly_repayment
from engine.projection import NEVER, ProjectionInputs, project, savings_runway
from engine.tax import take_home, take_home_array

MONTHS = 36


def make_inputs(**overrides) -> ProjectionInputs:
    values = dict(
        annual_rate=np.full(MONTHS, 6.0),
        income_multiplier=np.ones((2, MONTHS)),
        expenses=np.full(MONTHS, 4_000.0),
        one_off=np.zeros(MONTHS),
        base_gross=(110_000, 70_000),
        has_help=(True, False),
        other_debts=300.0,
        principal=600_000,
        term_years=30,
        starting_savings=30_000,
    )
    values.update(overrides)
    return ProjectionInputs(**values)


@pytest.mark.parametrize("has_help", [False, True])
def test_vectorised_tax_matches_scalar(has_help):
    incomes = np.arange(0, 400_001, 1_000.0)
    expected = [take_home(x, has_help).net for x in incomes]
    assert take_home_array(incomes, has_help) == pytest.approx(expected)


def test_constant_inputs_match_phase_1_repayment():
    result = project(make_inputs())
    assert result.repayment == pytest.approx(np.full(MONTHS, monthly_repayment(600_000, 6.0, 30)))


def test_savings_change_by_exactly_the_surplus():
    result = project(make_inputs())
    changes = np.diff(np.concatenate([[30_000], result.savings]))
    assert changes == pytest.approx(result.surplus)


def test_surplus_is_take_home_minus_outgoings():
    result = project(make_inputs())
    expected = result.take_home - 4_000 - 300 - result.repayment
    assert result.surplus == pytest.approx(expected)


def test_batched_inputs_match_single_runs():
    rng = np.random.default_rng(0)
    rates = 6.0 + rng.normal(0, 0.5, size=(5, MONTHS)).cumsum(axis=-1) / 10
    batched = project(make_inputs(annual_rate=rates))
    for i in range(5):
        single = project(make_inputs(annual_rate=rates[i]))
        assert batched.savings[i] == pytest.approx(single.savings)
        assert batched.repayment[i] == pytest.approx(single.repayment)


def test_repayment_rises_when_rate_rises():
    rates = np.full(MONTHS, 6.0)
    rates[12:] = 8.0
    result = project(make_inputs(annual_rate=rates))
    assert result.repayment[12] > result.repayment[11]


def test_savings_cap_limits_what_is_saved():
    capped = project(make_inputs(savings_cap=500.0))
    assert np.diff(np.concatenate([[30_000], capped.savings])) == pytest.approx(np.full(MONTHS, 500.0))


def test_savings_cap_does_not_hide_shortfalls():
    expenses = np.full(MONTHS, 4_000.0)
    expenses[5] = 50_000
    result = project(make_inputs(expenses=expenses, savings_cap=500.0))
    assert result.savings[5] - result.savings[4] == pytest.approx(result.surplus[5])


def test_first_month_measures():
    result = project(make_inputs(starting_savings=1_000, expenses=np.full(MONTHS, 9_000.0)))
    assert result.first_negative_savings_month == 1
    calm = project(make_inputs(base_gross=(400_000, 200_000)))
    assert calm.first_stress_month == NEVER
    assert calm.first_negative_savings_month == NEVER


def test_lowest_savings_includes_starting_balance():
    result = project(make_inputs(base_gross=(400_000, 200_000)))
    assert result.lowest_savings == 30_000


def test_zero_loan():
    result = project(make_inputs(principal=0))
    assert result.repayment == pytest.approx(np.zeros(MONTHS))


def test_savings_runway():
    assert savings_runway(30_000, 6_000) == pytest.approx(5)
    assert savings_runway(0, 6_000) == 0
    assert savings_runway(10_000, 0) == float("inf")

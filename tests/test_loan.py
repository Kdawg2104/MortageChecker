import pytest

from engine.loan import (
    APRA_SERVICEABILITY_BUFFER,
    borrowing_power,
    max_loan,
    monthly_repayment,
    stress_table,
)


def test_known_repayment():
    # $500,000 over 30 years at 6% is a widely quoted ~$2,997.75/month
    assert monthly_repayment(500_000, 6.0, 30) == pytest.approx(2_997.75, abs=0.01)


@pytest.mark.parametrize("rate", [0, 3.5, 6.5, 9.5])
@pytest.mark.parametrize("years", [10, 25, 30])
def test_repayment_and_max_loan_are_inverses(rate, years):
    principal = 650_000
    repayment = monthly_repayment(principal, rate, years)
    assert max_loan(repayment, rate, years) == pytest.approx(principal)


def test_zero_loan():
    assert monthly_repayment(0, 6.5, 30) == 0


def test_zero_interest():
    assert monthly_repayment(360_000, 0, 30) == pytest.approx(1_000)
    assert max_loan(1_000, 0, 30) == pytest.approx(360_000)


def test_no_capacity_means_no_loan():
    assert max_loan(0, 6.5, 30) == 0
    assert max_loan(-500, 6.5, 30) == 0


def test_borrowing_power_uses_buffer():
    surplus = 4_000
    expected = max_loan(surplus, 6.5 + APRA_SERVICEABILITY_BUFFER, 30)
    assert borrowing_power(surplus, 6.5, 30) == pytest.approx(expected)
    assert borrowing_power(surplus, 6.5, 30) < max_loan(surplus, 6.5, 30)


def test_stress_table():
    table = stress_table(500_000, 6.0, 30)
    assert [row["rise"] for row in table] == [0, 1, 2, 3]
    assert [row["rate"] for row in table] == [6.0, 7.0, 8.0, 9.0]
    repayments = [row["repayment"] for row in table]
    assert repayments == sorted(repayments)
    assert repayments[0] == pytest.approx(monthly_repayment(500_000, 6.0, 30))

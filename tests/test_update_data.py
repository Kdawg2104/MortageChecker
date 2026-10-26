import pandas as pd
import pytest

from scripts.update_data import (
    cash_rate_changes,
    cash_rate_month_end,
    parse_rba_number,
    quarterly_to_monthly,
    splice_cpi,
)


def test_quarter_spread_evenly_and_compounds_back():
    index = pd.Series([100.0, 103.0, 103.0], index=pd.PeriodIndex(["2020-03", "2020-06", "2020-09"], freq="M"))
    monthly = quarterly_to_monthly(index)
    assert list(monthly.index.astype(str)) == ["2020-04", "2020-05", "2020-06", "2020-07", "2020-08", "2020-09"]
    april_to_june = monthly.iloc[:3]
    assert april_to_june.nunique() == 1  # spread evenly
    assert (1 + april_to_june).prod() == pytest.approx(1.03)
    assert monthly.iloc[3:].tolist() == pytest.approx([0, 0, 0])


def test_cash_rate_month_end_carries_forward():
    decisions = pd.Series([4.35, 4.60], index=pd.PeriodIndex(["2026-01", "2026-04"], freq="M"))
    month_end = cash_rate_month_end(decisions, pd.Period("2026-06", freq="M"))
    assert month_end.tolist() == [4.35, 4.35, 4.35, 4.60, 4.60, 4.60]


def test_two_decisions_in_one_month_keeps_the_last():
    decisions = pd.Series([1.0, 0.5], index=pd.PeriodIndex(["2020-03", "2020-03"], freq="M"))
    assert cash_rate_month_end(decisions, pd.Period("2020-03", freq="M")).tolist() == [0.5]


def test_cash_rate_change_is_difference_of_month_end_levels():
    levels = pd.Series([4.35, 4.35, 4.60], index=pd.PeriodIndex(["2026-07", "2026-08", "2026-09"], freq="M"))
    assert cash_rate_changes(levels).tolist() == pytest.approx([0.0, 0.25])


def test_rba_range_values_use_midpoint():
    assert parse_rba_number("17.00 to 17.50") == pytest.approx(17.25)
    assert parse_rba_number("4.60") == pytest.approx(4.60)


def test_cpi_splice_switches_to_monthly_in_october_2025():
    months = pd.period_range("2025-07", "2025-12", freq="M")
    quarterly = pd.Series(0.01, index=months)
    monthly = pd.Series(0.02, index=months)
    spliced = splice_cpi(quarterly, monthly)
    assert spliced.tolist() == [0.01, 0.01, 0.01, 0.02, 0.02, 0.02]

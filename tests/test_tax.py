import pytest

from engine.tax import (
    help_repayment,
    income_tax,
    low_income_tax_offset,
    medicare_levy,
    take_home,
)


def test_100k_no_help():
    result = take_home(100_000, has_help=False)
    assert result.income_tax == pytest.approx(20_520)
    assert result.medicare == pytest.approx(2_000)
    assert result.help == 0
    assert result.net == pytest.approx(77_480)


def test_help_repayment_110k():
    assert help_repayment(110_000) == pytest.approx(6_071, abs=1)


def test_help_only_applied_when_flagged():
    assert take_home(110_000, has_help=True).help == pytest.approx(6_071, abs=1)
    assert take_home(110_000, has_help=False).help == 0


def test_help_below_threshold_is_zero():
    assert help_repayment(69_528) == 0


def test_help_top_tier_uses_total_income():
    assert help_repayment(200_000) == pytest.approx(20_000)


def test_help_tiers_join_up_smoothly():
    # The 17c tier and the 10% tier should meet (almost) exactly at $186,051
    assert help_repayment(186_051) == pytest.approx(help_repayment(186_052), abs=2)


@pytest.mark.parametrize(
    "income, expected",
    [(30_000, 700), (37_500, 700), (45_000, 325), (66_667, 0), (90_000, 0)],
)
def test_lito(income, expected):
    assert low_income_tax_offset(income) == pytest.approx(expected, abs=0.01)


def test_medicare_phase_in():
    assert medicare_levy(28_011) == 0
    assert medicare_levy(30_000) == pytest.approx((30_000 - 28_011) * 0.10)
    assert medicare_levy(40_000) == pytest.approx(800)


def test_lito_cannot_make_tax_negative():
    # $20,000: $270 tax before offsets, $700 LITO, so tax is $0, not -$430
    assert income_tax(20_000) == 0


def test_zero_income():
    result = take_home(0, has_help=True)
    assert result.income_tax == 0
    assert result.medicare == 0
    assert result.help == 0
    assert result.net == 0


def test_top_bracket():
    # 4,020 + 27,000 + 20,350 + 4,500 = 55,870 on $200,000 (no LITO at this income)
    assert income_tax(200_000) == pytest.approx(55_870)

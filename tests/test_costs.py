import pytest

from engine.costs import (
    DEFAULT_OTHER_COSTS,
    deposit_scheme_check,
    lmi_premium,
    nsw_first_home_duty,
    nsw_transfer_duty,
    purchase_summary,
    transfer_duty,
)


# Revenue NSW 2026-27 general examples, plus the worked examples on "How to calculate transfer duty"
@pytest.mark.parametrize(
    "value, duty",
    [(700_000, 25_687), (800_000, 30_187), (1_000_000, 39_187), (1_350_000, 55_537), (450_000, 14_437)],
)
def test_nsw_general_duty(value, duty):
    assert nsw_transfer_duty(value) == pytest.approx(duty)


def test_premium_property_duty():
    # Revenue NSW worked example: $4,000,000 -> $194,137 + $130,000 x 7% = $203,237
    assert nsw_transfer_duty(4_000_000) == pytest.approx(203_237)


def test_minimum_duty():
    assert nsw_transfer_duty(1_000) == 20


def test_first_home_buyer_exempt_at_800k():
    assert nsw_first_home_duty(800_000) == 0


# Official 2026-27 FHBAS concession table (nsw.gov.au)
@pytest.mark.parametrize(
    "value, duty",
    [(850_000, 9_796.75), (900_000, 19_593.50), (950_000, 29_390.25), (990_000, 37_227.65)],
)
def test_first_home_buyer_concession(value, duty):
    assert nsw_first_home_duty(value) == pytest.approx(duty)


def test_first_home_buyer_full_duty_from_1m():
    assert nsw_first_home_duty(1_000_000) == pytest.approx(nsw_transfer_duty(1_000_000))
    assert nsw_first_home_duty(1_200_000) == pytest.approx(nsw_transfer_duty(1_200_000))


def test_unsupported_state_raises():
    with pytest.raises(NotImplementedError):
        transfer_duty("VIC", 700_000)


def test_lmi_zero_at_or_below_80():
    assert lmi_premium(600_000, 80.0) == 0
    assert lmi_premium(500_000, 70.0) == 0


def test_lmi_rises_with_lvr():
    premiums = [lmi_premium(500_000, lvr) for lvr in (84, 89, 94)]
    assert 0 < premiums[0] < premiums[1] < premiums[2]


def test_lmi_not_insurable_above_95():
    assert lmi_premium(500_000, 96) is None


def test_scheme_applies_under_cap():
    check = deposit_scheme_check(900_000, 45_000, "Sydney or NSW regional centre", single_parent=False)
    assert check.applies


def test_scheme_does_not_apply_over_cap():
    check = deposit_scheme_check(1_600_000, 200_000, "Sydney or NSW regional centre", single_parent=False)
    assert not check.applies
    assert "cap" in check.message


def test_scheme_rest_of_nsw_cap():
    assert not deposit_scheme_check(850_000, 50_000, "Rest of NSW", single_parent=False).applies


def test_scheme_single_parent_two_percent():
    assert deposit_scheme_check(700_000, 14_000, "Rest of NSW", single_parent=True).applies
    assert not deposit_scheme_check(700_000, 14_000, "Rest of NSW", single_parent=False).applies


def test_no_lmi_with_scheme():
    summary = purchase_summary(700_000, 35_000, 80_000, use_scheme=True, first_home_buyer=True)
    assert summary.scheme.applies
    assert summary.lmi == 0
    assert summary.loan == 665_000


def test_purchase_summary_adds_up():
    summary = purchase_summary(800_000, 160_000, 220_000)
    other = sum(DEFAULT_OTHER_COSTS.values())
    assert summary.duty == pytest.approx(30_187)
    assert summary.lmi == 0
    assert summary.upfront_costs == pytest.approx(30_187 + other)
    assert summary.savings_left == pytest.approx(220_000 - 160_000 - 30_187 - other)
    assert summary.lvr == pytest.approx(80.0)


def test_capitalised_lmi_goes_on_the_loan():
    added = purchase_summary(700_000, 70_000, 120_000, capitalise_lmi=True)
    upfront = purchase_summary(700_000, 70_000, 120_000, capitalise_lmi=False)
    assert added.loan == pytest.approx(630_000 + added.lmi)
    assert upfront.loan == 630_000
    assert upfront.savings_left == pytest.approx(added.savings_left - upfront.lmi)


def test_shortfall_when_savings_too_low():
    summary = purchase_summary(800_000, 160_000, 150_000)
    assert summary.savings_left < 0
    assert summary.shortfall == pytest.approx(-summary.savings_left)

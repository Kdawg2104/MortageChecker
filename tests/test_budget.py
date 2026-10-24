import math

import pytest

from engine.budget import living_costs, stress_label, stress_ratio


def test_single_preset():
    assert living_costs("Moderate", borrowers=1) == 2_800


def test_couple_with_dependants():
    assert living_costs("Moderate", borrowers=2, dependants=2) == pytest.approx(2_800 * 1.7 + 1_800)


def test_stress_ratio():
    assert stress_ratio(3_000, 10_000) == pytest.approx(0.30)


def test_stress_ratio_zero_income():
    assert math.isinf(stress_ratio(2_000, 0))
    assert stress_ratio(0, 0) == 0


@pytest.mark.parametrize(
    "ratio, label",
    [
        (0.0, "Below stress threshold"),
        (0.299, "Below stress threshold"),
        (0.30, "Mortgage stress"),
        (0.399, "Mortgage stress"),
        (0.40, "Severe mortgage stress"),
        (float("inf"), "Severe mortgage stress"),
    ],
)
def test_stress_label(ratio, label):
    assert stress_label(ratio) == label

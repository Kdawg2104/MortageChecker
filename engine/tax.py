"""Australian resident individual tax calculations for the 2026-27 financial year.

Covers income tax, the Low Income Tax Offset (LITO), the Medicare levy and
HECS/HELP compulsory repayments. All figures are annual amounts in AUD.
"""

from dataclasses import dataclass

import numpy as np

TAX_YEAR = "2026-27"

# --- Income tax brackets (ATO, resident rates, 2026-27) ---
# Each tuple is (lower threshold, marginal rate). Income above a threshold is
# taxed at that rate until the next threshold.
TAX_BRACKETS = (
    (0, 0.00),
    (18_200, 0.15),
    (45_000, 0.30),
    (135_000, 0.37),
    (190_000, 0.45),
)

# --- Low Income Tax Offset (ATO, 2026-27) ---
LITO_MAX = 700
LITO_FULL_THRESHOLD = 37_500     # full $700 offset up to here
LITO_MID_THRESHOLD = 45_000      # offset is $325 here
LITO_TAPER_1 = 0.05              # 5c per $ between $37,500 and $45,000
LITO_TAPER_2 = 0.015             # 1.5c per $ above $45,000 (reaches $0 at ~$66,667)

# --- Medicare levy (ATO, 2026-27) ---
MEDICARE_RATE = 0.02
MEDICARE_LOW_THRESHOLD = 28_011  # no levy at or below this income
MEDICARE_PHASE_IN_RATE = 0.10    # 10c per $ above the threshold until 2% is reached

# --- HECS/HELP compulsory repayment, marginal system (ATO, 2026-27) ---
HELP_THRESHOLD = 69_528
HELP_TIER_2_THRESHOLD = 129_717
HELP_TIER_3_THRESHOLD = 186_051
HELP_TIER_1_RATE = 0.15          # 15c per $ above $69,528
HELP_TIER_2_BASE = 9_028         # repayment at $129,717
HELP_TIER_2_RATE = 0.17          # 17c per $ above $129,717
HELP_TOP_RATE = 0.10             # 10% of TOTAL income above $186,051


@dataclass(frozen=True)
class TaxResult:
    """Annual tax breakdown for one person."""

    gross: float
    income_tax: float
    medicare: float
    help: float
    net: float


def income_tax_before_offsets(income: float) -> float:
    """Tax from the marginal brackets alone, before any offsets."""
    tax = 0.0
    for i, (threshold, rate) in enumerate(TAX_BRACKETS):
        upper = TAX_BRACKETS[i + 1][0] if i + 1 < len(TAX_BRACKETS) else float("inf")
        if income > threshold:
            tax += (min(income, upper) - threshold) * rate
    return tax


def low_income_tax_offset(income: float) -> float:
    """Low Income Tax Offset: $700, tapering to $0 at about $66,667."""
    if income <= LITO_FULL_THRESHOLD:
        return LITO_MAX
    if income <= LITO_MID_THRESHOLD:
        return LITO_MAX - (income - LITO_FULL_THRESHOLD) * LITO_TAPER_1
    mid_value = LITO_MAX - (LITO_MID_THRESHOLD - LITO_FULL_THRESHOLD) * LITO_TAPER_1
    return max(0.0, mid_value - (income - LITO_MID_THRESHOLD) * LITO_TAPER_2)


def income_tax(income: float) -> float:
    """Income tax after LITO. The offset is non-refundable, so tax never goes below $0."""
    return max(0.0, income_tax_before_offsets(income) - low_income_tax_offset(income))


def medicare_levy(income: float) -> float:
    """Medicare levy with the low-income phase-in."""
    if income <= MEDICARE_LOW_THRESHOLD:
        return 0.0
    phase_in = (income - MEDICARE_LOW_THRESHOLD) * MEDICARE_PHASE_IN_RATE
    return min(phase_in, income * MEDICARE_RATE)


def help_repayment(income: float) -> float:
    """Compulsory HECS/HELP repayment under the marginal system."""
    if income <= HELP_THRESHOLD:
        return 0.0
    if income <= HELP_TIER_2_THRESHOLD:
        return (income - HELP_THRESHOLD) * HELP_TIER_1_RATE
    if income <= HELP_TIER_3_THRESHOLD:
        return HELP_TIER_2_BASE + (income - HELP_TIER_2_THRESHOLD) * HELP_TIER_2_RATE
    return income * HELP_TOP_RATE


def take_home(income: float, has_help: bool = False) -> TaxResult:
    """Full annual breakdown: gross income, each deduction, and net take-home pay."""
    income = max(0.0, income)
    tax = income_tax(income)
    medicare = medicare_levy(income)
    help_amount = help_repayment(income) if has_help else 0.0
    return TaxResult(
        gross=income,
        income_tax=tax,
        medicare=medicare,
        help=help_amount,
        net=income - tax - medicare - help_amount,
    )


def take_home_array(income: np.ndarray, has_help: bool = False) -> np.ndarray:
    """Vectorised take_home(): annual net income for an array of annual gross incomes.

    Same rules and constants as the functions above, written with numpy so thousands
    of incomes (e.g. every month of every simulation) are taxed at once.
    """
    income = np.maximum(np.asarray(income, dtype=float), 0.0)

    # Income tax: tax each bracket's slice of income at that bracket's rate
    tax = np.zeros_like(income)
    for i, (threshold, rate) in enumerate(TAX_BRACKETS):
        upper = TAX_BRACKETS[i + 1][0] if i + 1 < len(TAX_BRACKETS) else np.inf
        tax += np.clip(income - threshold, 0, upper - threshold) * rate

    # Low Income Tax Offset, tapering in two steps
    mid_value = LITO_MAX - (LITO_MID_THRESHOLD - LITO_FULL_THRESHOLD) * LITO_TAPER_1
    lito = np.where(
        income <= LITO_FULL_THRESHOLD,
        LITO_MAX,
        np.where(
            income <= LITO_MID_THRESHOLD,
            LITO_MAX - (income - LITO_FULL_THRESHOLD) * LITO_TAPER_1,
            np.maximum(0.0, mid_value - (income - LITO_MID_THRESHOLD) * LITO_TAPER_2),
        ),
    )
    tax = np.maximum(0.0, tax - lito)

    # Medicare levy with low-income phase-in
    medicare = np.where(
        income <= MEDICARE_LOW_THRESHOLD,
        0.0,
        np.minimum((income - MEDICARE_LOW_THRESHOLD) * MEDICARE_PHASE_IN_RATE, income * MEDICARE_RATE),
    )

    # HECS/HELP, marginal system
    if has_help:
        help_amount = np.select(
            [income <= HELP_THRESHOLD, income <= HELP_TIER_2_THRESHOLD, income <= HELP_TIER_3_THRESHOLD],
            [
                0.0,
                (income - HELP_THRESHOLD) * HELP_TIER_1_RATE,
                HELP_TIER_2_BASE + (income - HELP_TIER_2_THRESHOLD) * HELP_TIER_2_RATE,
            ],
            default=income * HELP_TOP_RATE,
        )
    else:
        help_amount = 0.0

    return income - tax - medicare - help_amount

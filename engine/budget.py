"""Household living costs and mortgage stress measures. All amounts are monthly AUD."""

# PLACEHOLDER figures: monthly living costs for one adult, excluding housing.
# These are rough estimates to be replaced with ABS Household Expenditure
# Survey data in a later phase.
LIFESTYLE_PRESETS = {
    "Frugal": 1_800,
    "Moderate": 2_800,
    "Comfortable": 4_200,
}

# PLACEHOLDER scaling: a couple costs less than two singles living apart.
# To be replaced with ABS equivalence-scale data in a later phase.
COUPLE_MULTIPLIER = 1.7
COST_PER_DEPENDANT = 900  # PLACEHOLDER, monthly

# Mortgage stress thresholds as a share of gross household income. The 30%
# rule of thumb is widely used in Australian housing research (e.g. AHURI).
STRESS_THRESHOLD = 0.30
SEVERE_STRESS_THRESHOLD = 0.40

# PLACEHOLDER judgement call, not an official figure: a household with less than
# this left over each month has little room for surprises. Revisit in Phase 4.
LOW_BUFFER_THRESHOLD = 1_000


def living_costs(preset: str, borrowers: int = 1, dependants: int = 0) -> float:
    """Estimated monthly living costs for the household, excluding housing."""
    base = LIFESTYLE_PRESETS[preset]
    if borrowers >= 2:
        base *= COUPLE_MULTIPLIER
    return base + dependants * COST_PER_DEPENDANT


def stress_ratio(repayment: float, gross_monthly_income: float) -> float:
    """Mortgage repayment as a fraction of gross monthly income (0.3 means 30%)."""
    if gross_monthly_income <= 0:
        return float("inf") if repayment > 0 else 0.0
    return repayment / gross_monthly_income


def stress_label(ratio: float) -> str:
    """Plain-English label for a stress ratio."""
    if ratio < STRESS_THRESHOLD:
        return "Below stress threshold"
    if ratio < SEVERE_STRESS_THRESHOLD:
        return "Mortgage stress"
    return "Severe mortgage stress"


def thirty_percent_rule_misleading(
    ratio: float, loan_amount: float, borrowing_power: float, left_over: float
) -> bool:
    """True when the 30% rule says "fine" but the household's budget says otherwise.

    That happens when repayments are under 30% of gross income, yet the loan is
    above the estimated borrowing power or very little money is left each month.
    """
    if loan_amount <= 0 or ratio >= STRESS_THRESHOLD:
        return False
    return loan_amount > borrowing_power or left_over < LOW_BUFFER_THRESHOLD

"""Principal and interest loan maths: repayments, borrowing limits and rate stress tests.

Rates are passed as annual percentages (6.5 means 6.5%). Repayments are monthly.
"""

# APRA serviceability buffer: lenders assess loans at the actual rate plus this
# many percentage points. Source: APRA, buffer confirmed at 3.0 points, May 2026.
APRA_SERVICEABILITY_BUFFER = 3.0

MONTHS_PER_YEAR = 12


def monthly_repayment(principal: float, annual_rate: float, years: int) -> float:
    """Monthly principal and interest repayment that pays off the loan over the term.

    Uses the standard amortisation formula P * r / (1 - (1 + r)^-n), where r is
    the monthly rate and n the number of months.
    """
    if principal <= 0:
        return 0.0
    n = years * MONTHS_PER_YEAR
    r = annual_rate / 100 / MONTHS_PER_YEAR
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def max_loan(monthly_capacity: float, annual_rate: float, years: int) -> float:
    """Largest loan a given monthly repayment can pay off: the inverse of monthly_repayment."""
    if monthly_capacity <= 0:
        return 0.0
    n = years * MONTHS_PER_YEAR
    r = annual_rate / 100 / MONTHS_PER_YEAR
    if r == 0:
        return monthly_capacity * n
    return monthly_capacity * (1 - (1 + r) ** -n) / r


def assessment_rate(annual_rate: float, buffer: float = APRA_SERVICEABILITY_BUFFER) -> float:
    """The rate a lender tests your repayments at: actual rate plus the buffer."""
    return annual_rate + buffer


def borrowing_power(
    monthly_surplus: float,
    annual_rate: float,
    years: int,
    buffer: float = APRA_SERVICEABILITY_BUFFER,
) -> float:
    """Estimated maximum loan, assuming the whole monthly surplus goes to repayments
    tested at the assessment rate."""
    return max_loan(monthly_surplus, assessment_rate(annual_rate, buffer), years)


def stress_table(
    principal: float,
    annual_rate: float,
    years: int,
    rises: tuple[float, ...] = (0, 1, 2, 3),
) -> list[dict]:
    """Monthly repayment if rates rise by each amount in `rises` (percentage points).

    Returns one dict per scenario: {"rise", "rate", "repayment"}.
    """
    return [
        {
            "rise": rise,
            "rate": annual_rate + rise,
            "repayment": monthly_repayment(principal, annual_rate + rise, years),
        }
        for rise in rises
    ]

"""Month-by-month household projection: income, costs, a variable-rate mortgage and savings.

Inputs are month-by-month numpy ARRAYS, not single numbers. An array can also carry extra
leading dimensions, e.g. shape (n_sims, months), so the same code projects one scenario or
thousands of simulated futures at once (Phase 3). The only Python loop is over months.
"""

from dataclasses import dataclass

import numpy as np

from engine.budget import SEVERE_STRESS_THRESHOLD, STRESS_THRESHOLD
from engine.tax import take_home_array

MONTHS_PER_YEAR = 12
NEVER = -1  # returned by the "first month" measures when something never happens


@dataclass(frozen=True)
class ProjectionInputs:
    """Everything the projection needs. Arrays end in a months dimension."""

    annual_rate: np.ndarray        # (..., months) mortgage rate, % p.a.
    income_multiplier: np.ndarray  # (..., borrowers, months) 1.0 = normal pay, 0.0 = no pay
    expenses: np.ndarray           # (..., months) living costs per month
    one_off: np.ndarray            # (..., months) one-off costs in a month (e.g. repairs)
    base_gross: tuple[float, ...]  # each borrower's normal gross annual income
    has_help: tuple[bool, ...]     # each borrower's HECS/HELP status
    other_debts: float             # other debt repayments per month
    principal: float               # loan amount at the start
    term_years: int
    starting_savings: float        # buffer left after buying
    savings_cap: float | None = None  # most of a positive surplus that gets saved each month

    @property
    def months(self) -> int:
        return self.annual_rate.shape[-1]


@dataclass(frozen=True)
class ProjectionResult:
    """Month-by-month results (each array ends in a months dimension) plus summary measures."""

    annual_rate: np.ndarray
    gross_income: np.ndarray   # household gross income per month
    take_home: np.ndarray      # household take-home pay per month
    expenses: np.ndarray
    one_off: np.ndarray
    repayment: np.ndarray
    balance: np.ndarray        # loan balance at the end of each month
    surplus: np.ndarray        # take-home minus everything paid out that month
    savings: np.ndarray        # savings balance at the end of each month
    stress_ratio: np.ndarray   # repayment / gross income
    starting_savings: float = 0.0

    @staticmethod
    def _first_month(mask: np.ndarray) -> np.ndarray:
        """1-based month where mask is first True, or NEVER."""
        return np.where(mask.any(axis=-1), mask.argmax(axis=-1) + 1, NEVER)

    @property
    def first_stress_month(self) -> np.ndarray:
        return self._first_month(self.stress_ratio >= STRESS_THRESHOLD)

    @property
    def first_severe_stress_month(self) -> np.ndarray:
        return self._first_month(self.stress_ratio >= SEVERE_STRESS_THRESHOLD)

    @property
    def first_negative_savings_month(self) -> np.ndarray:
        return self._first_month(self.savings < 0)

    @property
    def lowest_savings(self) -> np.ndarray:
        """Lowest balance over the horizon, including the starting buffer."""
        return np.minimum(self.savings.min(axis=-1), self.starting_savings)

    @property
    def peak_stress_ratio(self) -> np.ndarray:
        return self.stress_ratio.max(axis=-1)


def _repayment(balance: np.ndarray, monthly_rate: np.ndarray, months_left: int) -> np.ndarray:
    """P&I repayment that clears `balance` in `months_left` months (same formula as loan.py)."""
    months_left = max(months_left, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        amortised = balance * monthly_rate / (1 - (1 + monthly_rate) ** -months_left)
    payment = np.where(monthly_rate == 0, balance / months_left, amortised)
    return np.where(balance > 0, payment, 0.0)


def project(inputs: ProjectionInputs) -> ProjectionResult:
    """Run the household forward month by month."""
    months = inputs.months
    batch = np.broadcast_shapes(
        inputs.annual_rate.shape[:-1],
        inputs.expenses.shape[:-1],
        inputs.one_off.shape[:-1],
        inputs.income_multiplier.shape[:-2],
    )
    rate = np.broadcast_to(inputs.annual_rate, batch + (months,))
    expenses = np.broadcast_to(inputs.expenses, batch + (months,))
    one_off = np.broadcast_to(inputs.one_off, batch + (months,))
    borrowers = len(inputs.base_gross)
    multiplier = np.broadcast_to(inputs.income_multiplier, batch + (borrowers, months))

    # Income: each borrower's pay that month, annualised for tax (as payroll withholding does)
    gross = np.zeros(batch + (months,))
    take_home = np.zeros(batch + (months,))
    for b in range(borrowers):
        annual_gross = inputs.base_gross[b] * multiplier[..., b, :]
        gross += annual_gross / MONTHS_PER_YEAR
        take_home += take_home_array(annual_gross, inputs.has_help[b]) / MONTHS_PER_YEAR

    # Variable P&I loan: repayment recalculated every month from balance, rate and term left
    total_months = inputs.term_years * MONTHS_PER_YEAR
    balance = np.full(batch, float(inputs.principal))
    repayment = np.zeros(batch + (months,))
    balances = np.zeros(batch + (months,))
    for m in range(months):
        monthly_rate = rate[..., m] / 100 / MONTHS_PER_YEAR
        payment = _repayment(balance, monthly_rate, total_months - m)
        balance = balance * (1 + monthly_rate) - payment
        repayment[..., m] = payment
        balances[..., m] = balance

    surplus = take_home - expenses - inputs.other_debts - repayment - one_off
    if inputs.savings_cap is None:
        saved = surplus
    else:
        saved = np.where(surplus > 0, np.minimum(surplus, inputs.savings_cap), surplus)
    savings = inputs.starting_savings + np.cumsum(saved, axis=-1)

    with np.errstate(divide="ignore", invalid="ignore"):
        stress = np.where(gross > 0, repayment / gross, np.where(repayment > 0, np.inf, 0.0))

    return ProjectionResult(
        annual_rate=rate,
        gross_income=gross,
        take_home=take_home,
        expenses=expenses,
        one_off=one_off,
        repayment=repayment,
        balance=balances,
        surplus=surplus,
        savings=savings,
        stress_ratio=stress,
        starting_savings=inputs.starting_savings,
    )


def savings_runway(buffer: float, monthly_outgoings: float) -> float:
    """Months a savings buffer would last if all income stopped. inf if nothing goes out."""
    if buffer <= 0:
        return 0.0
    if monthly_outgoings <= 0:
        return float("inf")
    return buffer / monthly_outgoings

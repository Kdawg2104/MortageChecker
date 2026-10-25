"""Life events and stress-scenario presets.

A scenario is a list of events. Each event edits the month-by-month input arrays
(rate, income, expenses, one-off costs) that engine/projection.py runs on. Months are
1-based here (month 1 is the first month after buying), as users would describe them.
"""

from dataclasses import dataclass, field

import numpy as np

from engine.budget import COST_PER_DEPENDANT
from engine.projection import ProjectionInputs, ProjectionResult, project

DEFAULT_MONTHS = 36


@dataclass(frozen=True)
class Household:
    """The household's starting position, taken from the calculator."""

    incomes: tuple[float, ...]     # gross annual income per borrower
    has_help: tuple[bool, ...]
    annual_rate: float             # current mortgage rate, % p.a.
    monthly_expenses: float        # living costs excluding housing
    other_debts: float
    loan: float
    term_years: int
    starting_savings: float        # savings left after buying
    savings_cap: float | None = None

    @property
    def higher_earner(self) -> int:
        return int(np.argmax(self.incomes))


@dataclass
class ScenarioArrays:
    """Month-by-month arrays that events edit before the projection runs."""

    rate: np.ndarray               # (months,)
    income: np.ndarray             # (borrowers, months) multipliers
    expenses: np.ndarray           # (months,)
    one_off: np.ndarray            # (months,)


def _who(borrower: int | None) -> str:
    return "Higher earner" if borrower is None else f"Borrower {borrower + 1}"


def _borrower(borrower: int | None, household: Household) -> int | None:
    """Resolve the borrower an event affects. None means the higher earner."""
    index = household.higher_earner if borrower is None else borrower
    return index if index < len(household.incomes) else None


@dataclass(frozen=True)
class JobLoss:
    """A borrower loses their income for a while; replaced_pct is any income that continues."""

    borrower: int | None = None
    start: int = 1
    duration: int = 3
    replaced_pct: float = 0.0

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        b = _borrower(self.borrower, household)
        if b is not None:
            arrays.income[b, self.start - 1:self.start - 1 + self.duration] *= self.replaced_pct / 100

    def describe(self) -> str:
        return f"{_who(self.borrower)}: job loss for {self.duration} months from month {self.start} ({self.replaced_pct:g}% of income replaced)"


@dataclass(frozen=True)
class ParentalLeave:
    """A borrower takes leave on reduced pay (pay_pct of normal)."""

    borrower: int | None = None
    start: int = 1
    duration: int = 6
    pay_pct: float = 0.0

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        b = _borrower(self.borrower, household)
        if b is not None:
            arrays.income[b, self.start - 1:self.start - 1 + self.duration] *= self.pay_pct / 100

    def describe(self) -> str:
        return f"{_who(self.borrower)}: parental leave for {self.duration} months from month {self.start} at {self.pay_pct:g}% pay"


@dataclass(frozen=True)
class PartTime:
    """A borrower moves to part-time from a given month, earning pct of normal income."""

    borrower: int | None = None
    start: int = 1
    pct: float = 60.0

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        b = _borrower(self.borrower, household)
        if b is not None:
            arrays.income[b, self.start - 1:] *= self.pct / 100

    def describe(self) -> str:
        return f"{_who(self.borrower)}: part-time at {self.pct:g}% of income from month {self.start}"


@dataclass(frozen=True)
class ExpenseShock:
    """A one-off cost in a given month (car, medical, repairs)."""

    month: int = 1
    amount: float = 5_000

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        if self.month <= arrays.one_off.shape[-1]:
            arrays.one_off[self.month - 1] += self.amount

    def describe(self) -> str:
        return f"One-off cost of ${self.amount:,.0f} in month {self.month}"


@dataclass(frozen=True)
class NewDependant:
    """A new dependant from a given month, adding the per-dependant monthly cost."""

    start: int = 1

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        arrays.expenses[self.start - 1:] += COST_PER_DEPENDANT

    def describe(self) -> str:
        return f"New dependant from month {self.start} (+${COST_PER_DEPENDANT:,.0f}/month)"


@dataclass(frozen=True)
class RateChange:
    """Interest rate moves by change_pp percentage points from a given month (floored at 0%)."""

    start: int = 1
    change_pp: float = 1.0

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        arrays.rate[self.start - 1:] = np.maximum(arrays.rate[self.start - 1:] + self.change_pp, 0.0)

    def describe(self) -> str:
        return f"Interest rate {self.change_pp:+g} percentage points from month {self.start}"


@dataclass(frozen=True)
class LivingCostChange:
    """Living costs change by pct percent from a given month."""

    start: int = 1
    pct: float = 5.0

    def apply(self, arrays: ScenarioArrays, household: Household) -> None:
        arrays.expenses[self.start - 1:] *= 1 + self.pct / 100

    def describe(self) -> str:
        return f"Living costs {self.pct:+g}% from month {self.start}"


Event = JobLoss | ParentalLeave | PartTime | ExpenseShock | NewDependant | RateChange | LivingCostChange


@dataclass(frozen=True)
class Scenario:
    """A named, editable set of events."""

    name: str
    description: str
    events: tuple = field(default_factory=tuple)


# Combined stress-scenario presets. Shocks start in month 1, when the buffer is smallest.
# "One borrower" is the higher earner.
PRESETS = {
    "base": Scenario("Base", "Nothing changes.", ()),
    "mild": Scenario(
        "Mild", "Rates +1%, living costs +5%.",
        (RateChange(1, 1.0), LivingCostChange(1, 5.0)),
    ),
    "severe": Scenario(
        "Severe", "Rates +2%, living costs +10%, one borrower loses income for 3 months.",
        (RateChange(1, 2.0), LivingCostChange(1, 10.0), JobLoss(None, 1, 3)),
    ),
    "worst": Scenario(
        "Worst case", "Rates +3%, living costs +15%, one borrower loses income for 6 months, $10,000 expense shock.",
        (RateChange(1, 3.0), LivingCostChange(1, 15.0), JobLoss(None, 1, 6), ExpenseShock(1, 10_000)),
    ),
}


def build_inputs(household: Household, events=(), months: int = DEFAULT_MONTHS) -> ProjectionInputs:
    """Turn a household and its events into the arrays projection.py runs on.

    Starts from flat arrays (nothing changes), then applies each event in order.
    """
    arrays = ScenarioArrays(
        rate=np.full(months, float(household.annual_rate)),
        income=np.ones((len(household.incomes), months)),
        expenses=np.full(months, float(household.monthly_expenses)),
        one_off=np.zeros(months),
    )
    for event in events:
        event.apply(arrays, household)
    return ProjectionInputs(
        annual_rate=arrays.rate,
        income_multiplier=arrays.income,
        expenses=arrays.expenses,
        one_off=arrays.one_off,
        base_gross=tuple(household.incomes),
        has_help=tuple(household.has_help),
        other_debts=household.other_debts,
        principal=household.loan,
        term_years=household.term_years,
        starting_savings=household.starting_savings,
        savings_cap=household.savings_cap,
    )


def run_scenario(household: Household, events=(), months: int = DEFAULT_MONTHS) -> ProjectionResult:
    """Build the arrays for a scenario and project it."""
    return project(build_inputs(household, events, months))

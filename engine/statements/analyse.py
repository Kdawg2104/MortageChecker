"""Turn categorised transactions into monthly figures the rest of the app can use.

Also estimates gross income by inverting the tax engine, and lists the things a lender may
look at (educational only: never a credit decision, and no bank's actual rules).
"""

import re
from dataclasses import dataclass, field

import pandas as pd

from engine.statements.categorise import (
    FREQUENCIES,
    IncomeSource,
    category_groups,
    detect_income,
    earners,
)
from engine.statements.parse import coverage_days
from engine.tax import take_home

DAYS_PER_MONTH = 365.25 / 12
HIGH_DISCRETIONARY_SHARE = 0.35   # judgement threshold for the educational flag, not a lending rule
IRREGULAR_INCOME_SHARE = 0.20     # likewise


@dataclass(frozen=True)
class StatementSummary:
    """Monthly averages over the statement period (only rows marked include)."""

    start: pd.Timestamp
    end: pd.Timestamp
    days: int
    months: float
    transactions: int
    income_sources: list[IncomeSource]
    monthly_income: float
    by_category: dict[str, float] = field(default_factory=dict)   # monthly spend (positive) per category
    housing: float = 0.0
    essentials: float = 0.0
    discretionary: float = 0.0
    debts: dict[str, float] = field(default_factory=dict)        # monthly repayment per debt category
    transfers_excluded: float = 0.0

    @property
    def debt_total(self) -> float:
        return sum(self.debts.values())

    @property
    def spending(self) -> float:
        return self.housing + self.essentials + self.discretionary + self.debt_total

    @property
    def left_over(self) -> float:
        return self.monthly_income - self.spending

    @property
    def regular_earners(self) -> list[IncomeSource]:
        return earners(self.income_sources)


def summarise(frame: pd.DataFrame) -> StatementSummary:
    """Monthly averages from categorised transactions.

    Regular payments (weekly rent, monthly bills) use their typical amount and frequency.
    Everything else is averaged over the whole period, so a quarterly bill paid once in 3 months
    counts as a third of its amount each month. Transfers between own accounts are left out.
    """
    groups = category_groups()
    rows = frame[frame["include"]]
    days = coverage_days(frame)
    months = max(days / DAYS_PER_MONTH, 1e-9)

    spend = rows[(rows["amount"] < 0) & (rows["category"].map(groups) != "transfer")]
    by_category = {}
    for (category, _, frequency), group in spend.groupby(
        ["category", "merchant", spend["recurring"].fillna("")], dropna=False
    ):
        if frequency:   # regular payment: typical amount x payments per year, so the period's length doesn't matter
            monthly = -group["amount"].median() * FREQUENCIES[frequency][2] / 12
        else:           # one-off or irregular (incl. a quarterly bill seen once): averaged over the period
            monthly = -group["amount"].sum() / months
        by_category[category] = by_category.get(category, 0.0) + monthly
    by_category = {c: round(float(v), 2) for c, v in by_category.items()}

    def total(group: str) -> float:
        return round(sum(v for c, v in by_category.items() if groups.get(c) == group), 2)

    sources = detect_income(frame, months)
    transfers = rows[rows["category"].map(groups) == "transfer"]["amount"].abs().sum() / months
    return StatementSummary(
        start=frame["date"].min(),
        end=frame["date"].max(),
        days=days,
        months=round(months, 2),
        transactions=len(frame),
        income_sources=sources,
        monthly_income=round(sum(s.monthly_net for s in sources), 2),
        by_category=dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        housing=total("housing"),
        essentials=total("essential"),
        discretionary=total("discretionary"),
        debts={c: v for c, v in by_category.items() if groups.get(c) == "debt"},
        transfers_excluded=round(float(transfers), 2),
    )


def monthly_cash_flow(frame: pd.DataFrame) -> pd.DataFrame:
    """Money in and money out per calendar month (transfers excluded)."""
    groups = category_groups()
    rows = frame[frame["include"] & (frame["category"].map(groups) != "transfer")]
    month = rows["date"].dt.to_period("M").astype(str)
    return pd.DataFrame({
        "money_in": rows["amount"].clip(lower=0).groupby(month).sum(),
        "money_out": (-rows["amount"].clip(upper=0)).groupby(month).sum(),
    }).round(2)


def estimate_gross(monthly_net: float, has_help: bool = False) -> float:
    """Gross annual income whose take-home pay is `monthly_net` a month.

    Inverts the tax engine by bisection (take-home always rises with gross income), so
    income tax, the Low Income Tax Offset, Medicare and HECS/HELP are all accounted for.
    """
    target = monthly_net * 12
    if target <= 0:
        return 0.0
    low, high = 0.0, 2_000_000.0
    for _ in range(60):
        mid = (low + high) / 2
        if take_home(mid, has_help).net < target:
            low = mid
        else:
            high = mid
    return round((low + high) / 2, 2)


def payer_name(source: IncomeSource) -> str:
    """Readable payer name without words like SALARY/PAYROLL."""
    name = re.sub(r"\b(SALARY|PAYROLL|WAGES|PAY|NET)\b", " ", source.payer)
    return " ".join(name.split()).title() or source.payer.title()


@dataclass(frozen=True)
class Flag:
    """Something a lender may look at, explained neutrally."""

    title: str
    detail: str
    explanation: str


def lender_flags(frame: pd.DataFrame, summary: StatementSummary) -> list[Flag]:
    """Patterns lenders commonly ask about. Educational only; not a credit assessment."""
    rows = frame[frame["include"]]
    flags = []

    bnpl = rows[rows["category"] == "Debt – BNPL"]
    if len(bnpl):
        flags.append(Flag(
            "Buy now, pay later",
            f"{len(bnpl)} repayments, about ${summary.debts.get('Debt – BNPL', 0):,.0f} a month.",
            "BNPL repayments are a regular commitment, so lenders often count them like other debts.",
        ))
    gambling = rows[rows["category"] == "Gambling"]
    if len(gambling):
        flags.append(Flag(
            "Gambling transactions",
            f"{len(gambling)} transactions, about ${summary.by_category.get('Gambling', 0):,.0f} a month.",
            "Lenders usually review gambling spending when judging how much of your income is really available.",
        ))
    if rows["balance"].notna().any() and (rows["balance"] < 0).any():
        overdrawn = rows.loc[rows["balance"] < 0, "date"].dt.date.nunique()
        flags.append(Flag(
            "Account overdrawn",
            f"The balance was below $0 on {overdrawn} day(s).",
            "A negative balance can suggest money is tight between pay days, so lenders often ask about it.",
        ))
    fee_pattern = r"\bDISHONOU?R|\bOVERDRAWN|\bOVERDRAFT|\bDECLINED|\bLATE PAYMENT"
    fees = rows[(rows["category"] == "Fees") & rows["description"].str.upper().str.contains(fee_pattern, regex=True)]
    if len(fees):
        flags.append(Flag(
            "Dishonour or overdraft fees",
            f"{len(fees)} fee(s) for missed or overdrawn payments.",
            "These fees show payments that couldn't be made, which lenders treat as a sign of budget pressure.",
        ))
    if summary.monthly_income > 0 and summary.discretionary / summary.monthly_income > HIGH_DISCRETIONARY_SHARE:
        flags.append(Flag(
            "High discretionary spending",
            f"About {summary.discretionary / summary.monthly_income:.0%} of income goes on non-essentials.",
            "Lenders compare your actual spending with typical living costs; high spending can reduce how much they'll lend.",
        ))
    irregular = sum(s.monthly_net for s in summary.income_sources if not s.regular)
    if summary.monthly_income > 0 and irregular / summary.monthly_income > IRREGULAR_INCOME_SHARE:
        flags.append(Flag(
            "Irregular income",
            f"About {irregular / summary.monthly_income:.0%} of income arrives at irregular times or amounts.",
            "Casual and gig income is often averaged over a longer period, or only partly counted, by lenders.",
        ))
    return flags


def household_income_split(summary: StatementSummary) -> list[float]:
    """Monthly take-home per earner. With no regular salary, all income counts as one earner."""
    regular = summary.regular_earners
    if not regular:
        return [summary.monthly_income]
    other = summary.monthly_income - sum(e.monthly_net for e in regular)
    split = [e.monthly_net for e in regular]
    split[0] += other   # extra income (e.g. interest, side work) goes with the main earner
    return split


def to_calculator_inputs(summary: StatementSummary, gross_incomes: list[float], has_help: list[bool]) -> dict:
    """Calculator fields from the reviewed statement figures.

    The Calculator's living costs exclude housing, so rent/mortgage is left out of `expenses`.
    """
    inputs = {
        "borrowers": len(gross_incomes),
        "expenses": int(round(summary.essentials + summary.discretionary)),
        "other_debts": int(round(summary.debt_total)),
    }
    for i, (gross, helps) in enumerate(zip(gross_incomes, has_help)):
        inputs[f"income_{i}"] = int(round(gross))
        inputs[f"help_{i}"] = bool(helps)
    return inputs


def annualised(amount: float, frequency: str) -> float:
    return amount * FREQUENCIES[frequency][2]

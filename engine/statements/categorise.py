"""Rules-based categorisation, recurring-payment and income detection.

Rules live in data/categories.yaml (human-readable, editable). No AI or network services:
every decision can be traced to a keyword rule or a simple date/amount pattern.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "categories.yaml"

OTHER = "Other"
OTHER_INCOME = "Income – other"
SALARY = "Income – salary"
TRANSFER = "Transfers (own accounts)"

HIGH, MEDIUM, LOW = "high", "medium", "low"

# Typical gap in days between payments for each frequency, with tolerance, and payments per year
FREQUENCIES = {
    "weekly": (7, 2, 52),
    "fortnightly": (14, 3, 26),
    "monthly": (30.4, 5, 12),
    "quarterly": (91, 10, 4),
}
AMOUNT_TOLERANCE = 0.15   # "similar amount": within 15% of the typical amount
TRANSFER_WINDOW_DAYS = 3  # matching in/out amounts this close together look like a transfer


@dataclass(frozen=True)
class Rule:
    name: str
    group: str
    direction: str
    merchants: tuple[re.Pattern, ...]
    keywords: tuple[re.Pattern, ...]


def _word_pattern(text: str) -> re.Pattern:
    """Match `text` as whole words, so "FEE" doesn't match "COFFEE"."""
    return re.compile(rf"(?<![A-Z0-9]){re.escape(text.strip().upper())}(?![A-Z0-9])")


def load_rules(path: Path = RULES_PATH) -> list[Rule]:
    """Read the categorisation rules from YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Rule(
            name=c["name"],
            group=c["group"],
            direction=c.get("direction", "any"),
            merchants=tuple(_word_pattern(m) for m in c.get("merchants", [])),
            keywords=tuple(_word_pattern(k) for k in c.get("keywords", [])),
        )
        for c in raw["categories"]
    ]


def category_groups(rules: list[Rule] | None = None) -> dict[str, str]:
    """Category name -> group (income, housing, essential, discretionary, debt, transfer)."""
    return {r.name: r.group for r in (rules or load_rules())}


def merchant_key(description: str) -> str:
    """A stable name for the merchant/payer: no placeholders, digits, card words or punctuation."""
    text = re.sub(r"\[\w+\]", " ", str(description).upper())
    text = re.sub(r"\b(CARD|ACCT|REF|RECEIPT|DIRECT DEBIT|PAYMENT|THANK YOU)\b", " ", text)
    text = re.sub(r"[^A-Z& ]", " ", text)
    return " ".join(text.split()[:4])


def _direction_ok(rule: Rule, amount: float) -> bool:
    return rule.direction == "any" or (rule.direction == "credit") == (amount > 0)


def categorise_one(description: str, amount: float, rules: list[Rule]) -> tuple[str, str]:
    """(category, confidence) for one transaction: merchant names first, then generic keywords."""
    text = str(description).upper()
    for attribute, confidence in (("merchants", HIGH), ("keywords", MEDIUM)):
        for rule in rules:
            if _direction_ok(rule, amount) and any(p.search(text) for p in getattr(rule, attribute)):
                return rule.name, confidence
    return (OTHER_INCOME if amount > 0 else OTHER), LOW


def frequency_of(dates: pd.Series) -> str | None:
    """Frequency label if the dates are regularly spaced, otherwise None."""
    dates = pd.Series(sorted(dates))
    if len(dates) < 2:
        return None
    gaps = dates.diff().dt.days.dropna()
    typical = gaps.median()
    for label, (days, tolerance, _) in FREQUENCIES.items():
        if abs(typical - days) <= tolerance and (abs(gaps - days) <= tolerance * 1.5).mean() >= 0.75:
            # one gap is enough for quarterly; shorter cycles need 3+ payments to be convincing
            if label == "quarterly" or len(dates) >= 3:
                return label
    return None


def detect_recurring(frame: pd.DataFrame) -> pd.Series:
    """Frequency label for each transaction whose merchant repeats regularly with similar amounts."""
    result = pd.Series(None, index=frame.index, dtype=object)
    for (_, positive), group in frame.groupby([frame["merchant"], frame["amount"] > 0]):
        if len(group) < 3:
            continue
        typical = group["amount"].abs().median()
        similar = (group["amount"].abs() - typical).abs() <= AMOUNT_TOLERANCE * typical
        if similar.mean() < 0.75:
            continue
        label = frequency_of(group.loc[similar, "date"])
        if label:
            result.loc[group.index] = label
    return result


def flag_likely_transfers(frame: pd.DataFrame) -> pd.Series:
    """True for a money-out and money-in of the same amount within a few days that mention a transfer.

    These are probably moves between the user's own accounts; they're flagged for review.
    """
    flagged = pd.Series(False, index=frame.index)
    mentions = frame["description"].str.upper().str.contains(r"\bTRANSFER|\bTFR\b|\bXFER\b", regex=True)
    candidates = frame[mentions & (frame["category"] != TRANSFER)]
    for i, row in candidates.iterrows():
        opposite = frame[
            (frame["amount"].round(2) == -round(row["amount"], 2))
            & ((frame["date"] - row["date"]).abs().dt.days <= TRANSFER_WINDOW_DAYS)
        ]
        if not opposite.empty:
            flagged.loc[[i, *opposite.index]] = True
    return flagged


def categorise(frame: pd.DataFrame, rules: list[Rule] | None = None) -> pd.DataFrame:
    """Add merchant, category, confidence, recurring and include columns (a new DataFrame)."""
    rules = rules or load_rules()
    out = frame.copy()
    out["merchant"] = out["description"].map(merchant_key)
    results = [categorise_one(d, a, rules) for d, a in zip(out["description"], out["amount"])]
    out["category"] = [c for c, _ in results]
    out["confidence"] = [c for _, c in results]

    likely = flag_likely_transfers(out)
    out.loc[likely, "category"] = TRANSFER
    out.loc[likely, "confidence"] = LOW

    out["recurring"] = detect_recurring(out)
    # A regular payer whose credits weren't recognised as salary still deserves a second look
    regular_credit = out["recurring"].notna() & (out["amount"] > 0) & (out["category"] == OTHER_INCOME)
    out.loc[regular_credit, "confidence"] = MEDIUM
    out["include"] = True
    return out


@dataclass(frozen=True)
class IncomeSource:
    """One payer of income found in the statements."""

    payer: str
    category: str
    frequency: str | None      # None = irregular
    typical_amount: float      # median payment
    monthly_net: float         # take-home per month from this payer
    payments: int

    @property
    def regular(self) -> bool:
        return self.frequency is not None


def detect_income(frame: pd.DataFrame, months: float) -> list[IncomeSource]:
    """Income payers, largest first. Regular pay is annualised from its typical amount and
    frequency; irregular income is averaged over the period."""
    groups = category_groups()
    income = frame[frame["include"] & (frame["amount"] > 0) & frame["category"].map(groups).eq("income")]
    sources = []
    for (payer, category), group in income.groupby(["merchant", "category"]):
        typical = float(group["amount"].median())
        steady = ((group["amount"] - typical).abs() <= AMOUNT_TOLERANCE * typical).mean() >= 0.75
        frequency = frequency_of(group["date"]) if steady and len(group) >= 3 else None
        if frequency:
            monthly = typical * FREQUENCIES[frequency][2] / 12
        else:
            monthly = float(group["amount"].sum()) / months
        sources.append(IncomeSource(payer, category, frequency, round(typical, 2), round(monthly, 2), len(group)))
    return sorted(sources, key=lambda s: s.monthly_net, reverse=True)


def earners(sources: list[IncomeSource]) -> list[IncomeSource]:
    """Regular salary payers, treated as the household's earners (at most two)."""
    return [s for s in sources if s.regular and s.category == SALARY][:2]


def value_accuracy(predicted: list[str], truth: list[str], amounts: list[float]) -> float:
    """Share of money (absolute dollars) that was put in the right category."""
    amounts = np.abs(np.asarray(amounts, dtype=float))
    correct = np.array([p == t for p, t in zip(predicted, truth)])
    return float(amounts[correct].sum() / amounts.sum()) if amounts.sum() else 1.0

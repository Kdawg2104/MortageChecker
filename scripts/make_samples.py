"""Generate SYNTHETIC 3-month bank statements for the Statement Analyser demo and tests.

Everything here is invented: the bank ("Sample Bank"), the people, employers, addresses and
account details. Merchants are common Australian businesses so the categorisation rules get
realistic input. Every file is marked "SAMPLE — NOT A REAL STATEMENT".

    .venv/bin/python scripts/make_samples.py            # write data/samples/
    .venv/bin/python scripts/make_samples.py --report   # also print categorisation accuracy

Needs reportlab (requirements-dev.txt) for the PDFs.
"""

import csv
import io
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tax import take_home  # noqa: E402  (after sys.path so the script runs directly)

SAMPLES = ROOT / "data" / "samples"
START = date(2026, 7, 1)
END = date(2026, 9, 30)
SAMPLE_MARK = "SAMPLE — NOT A REAL STATEMENT"
BANK = "Sample Bank"


@dataclass
class Statement:
    """One persona's synthetic statement and its ground truth."""

    key: str
    holder: str
    address: str
    bsb: str
    account: str
    opening_balance: float
    csv_layout: str
    rows: list = field(default_factory=list)   # dicts: date, description, amount, category
    truth: dict = field(default_factory=dict)

    def add(self, day: date, description: str, amount: float, category: str) -> None:
        if START <= day <= END:
            self.rows.append({"date": day, "description": description, "amount": round(amount, 2), "category": category})

    def finish(self) -> None:
        """Sort by date (stable) and add the running balance."""
        self.rows.sort(key=lambda r: r["date"])
        balance = self.opening_balance
        for row in self.rows:
            balance = round(balance + row["amount"], 2)
            row["balance"] = balance


def every(first: date, days: int):
    day = first
    while day <= END:
        yield day
        day += timedelta(days=days)


def monthly(day_of_month: int):
    for month in (7, 8, 9):
        yield date(2026, month, day_of_month)


def card(rng: random.Random) -> str:
    return f"CARD {rng.randint(4000, 4999)}XXXXXXXX{rng.randint(1000, 9999)}"


def receipt(rng: random.Random) -> str:
    return f"RECEIPT {rng.randint(100000, 999999)}"


def everyday_spending(s: Statement, rng: random.Random, scale: float, grocers=("WOOLWORTHS", "COLES", "ALDI STORES")) -> None:
    """Groceries, fuel, transport, dining, shopping and health that most households have."""
    for day in every(START + timedelta(days=rng.randint(0, 3)), 4):
        shop = rng.choice(grocers)
        s.add(day, f"{shop} {rng.randint(1000, 9999)} SYDNEY {card(rng)}", -rng.uniform(45, 140) * scale, "Groceries")
    for day in every(START + timedelta(days=2), 9):
        s.add(day, f"{rng.choice(['AMPOL', 'BP', 'SHELL COLES EXPRESS'])} {rng.choice(['PARRAMATTA', 'RYDE', 'NEWTOWN'])} {card(rng)}",
              -rng.uniform(55, 90), "Transport/fuel")
    for day in every(START + timedelta(days=1), 6):
        s.add(day, f"TRANSPORTFORNSW OPAL {receipt(rng)}", -rng.uniform(20, 50), "Transport/fuel")
    for day in every(START + timedelta(days=rng.randint(0, 2)), 5):
        s.add(day, f"{rng.choice(['UBER *EATS', 'MENULOG', 'MCDONALDS', 'GUZMAN Y GOMEZ'])} {card(rng)}",
              -rng.uniform(18, 55) * scale, "Dining/takeaway")
    for day in every(START + timedelta(days=5), 15):
        s.add(day, f"{rng.choice(['KMART', 'JB HI-FI', 'AMAZON AU', 'BIG W'])} {card(rng)}", -rng.uniform(25, 160) * scale, "Shopping")
    for day in every(START + timedelta(days=12), 30):
        s.add(day, f"CHEMIST WAREHOUSE {card(rng)}", -rng.uniform(15, 60), "Health")


def make_alex() -> Statement:
    rng = random.Random(1)
    s = Statement("alex", "Alex Taylor", "12 Example Street, Faketown NSW 2999", "999-001", "11223344", 2_400.00, "amount")
    gross = 85_000
    pay = round(take_home(gross, has_help=True).net / 26, 2)
    for day in every(date(2026, 7, 2), 14):
        s.add(day, f"SALARY WATTLE LOGISTICS PTY LTD REF {rng.randint(10000000, 99999999)}", pay, "Income – salary")
    for day in every(date(2026, 7, 1), 7):
        s.add(day, f"RENT HARBOURSIDE REALTY REF {rng.randint(100000, 999999)}", -620.00, "Rent/mortgage")
    s.add(date(2026, 8, 18), "ORIGIN ENERGY BILL PAYMENT", -412.35, "Utilities")       # quarterly electricity
    for day in monthly(9):
        s.add(day, "SYDNEY WATER DIRECT DEBIT", -38.20, "Utilities")
        s.add(day + timedelta(days=3), "TELSTRA MOBILE DIRECT DEBIT", -65.00, "Phone/internet")
        s.add(day + timedelta(days=5), "AUSSIE BROADBAND INTERNET", -89.00, "Phone/internet")
        s.add(day + timedelta(days=1), f"NETFLIX.COM {card(rng)}", -18.99, "Subscriptions")
        s.add(day + timedelta(days=8), f"SPOTIFY AU {card(rng)}", -13.99, "Subscriptions")
        s.add(day + timedelta(days=11), f"DISNEY PLUS {card(rng)}", -15.99, "Subscriptions")
        s.add(day + timedelta(days=4), "BUDGET DIRECT INSURANCE CONTENTS", -24.50, "Insurance")
        s.add(day + timedelta(days=6), "FITNESS FIRST MEMBERSHIP", -59.95, "Health")
    for day in every(date(2026, 7, 6), 14):
        s.add(day, f"AFTERPAY {receipt(rng)}", -rng.choice([42.50, 61.25, 88.00]), "Debt – BNPL")
    for day in every(date(2026, 7, 3), 14):
        s.add(day, f"TRANSFER TO SAVINGS ACCT {rng.randint(10000000, 99999999)}", -300.00, "Transfers (own accounts)")
    s.add(date(2026, 8, 30), f"TRANSFER FROM SAVINGS ACCT {rng.randint(10000000, 99999999)}", 400.00, "Transfers (own accounts)")
    s.add(date(2026, 7, 20), "TRANSFER TO J CITIZEN DINNER", -45.00, "Other")
    s.add(date(2026, 8, 5), "ATM WITHDRAWAL KING ST", -100.00, "Cash withdrawals")
    everyday_spending(s, rng, scale=0.6)
    s.finish()
    s.truth = {"earners": [{"payer": "WATTLE LOGISTICS", "gross": gross, "has_help": True, "frequency": "fortnightly", "net_pay": pay}]}
    return s


def make_sam_jordan() -> Statement:
    rng = random.Random(2)
    s = Statement("sam_jordan", "Sam Nguyen & Jordan Lee", "7 Sample Avenue, Mocksville NSW 2998", "999-002", "55667788",
                  6_800.00, "debit_credit")
    sam_pay = round(take_home(110_000, has_help=False).net / 26, 2)
    jordan_pay = round(take_home(75_000, has_help=False).net / 12, 2)
    for day in every(date(2026, 7, 9), 14):
        s.add(day, "PAYROLL COASTAL HEALTH SERVICES PTY LTD", sam_pay, "Income – salary")
    for day in monthly(15):
        s.add(day, "SALARY BLUEGUM EDUCATION LTD", jordan_pay, "Income – salary")
        s.add(date(2026, day.month, 1), f"RENT PARKVIEW PROPERTY MANAGEMENT REF {rng.randint(100000, 999999)}", -3_250.00, "Rent/mortgage")
        s.add(day + timedelta(days=5), "DRIVEFINANCE CAR LOAN REPAYMENT", -612.40, "Debt – car/personal loan")
        s.add(day + timedelta(days=10), f"CREDIT CARD PAYMENT THANK YOU {card(rng)}", -rng.uniform(450, 750), "Debt – credit card")
        s.add(day - timedelta(days=4), "NRMA INSURANCE CAR & HOME", -186.70, "Insurance")
        s.add(day - timedelta(days=2), "MEDIBANK PRIVATE HEALTH", -298.40, "Insurance")
        s.add(day + timedelta(days=2), "OPTUS MOBILE AND HOME INTERNET", -145.00, "Phone/internet")
        s.add(day + timedelta(days=7), f"NETFLIX.COM {card(rng)}", -25.99, "Subscriptions")
        s.add(day + timedelta(days=3), "AGL ENERGY DIRECT DEBIT", -235.10, "Utilities")
    for day in every(date(2026, 7, 3), 7):
        s.add(day, "LITTLE SPROUTS CHILDCARE CENTRE", -410.00, "Childcare/education")
    for day in every(date(2026, 7, 10), 14):
        s.add(day, f"INTERNAL TRANSFER TO OFFSET ACCT {rng.randint(10000000, 99999999)}", -800.00, "Transfers (own accounts)")
    s.add(date(2026, 9, 2), f"INTERNAL TRANSFER FROM OFFSET ACCT {rng.randint(10000000, 99999999)}", 1_500.00, "Transfers (own accounts)")
    everyday_spending(s, rng, scale=1.4)
    for day in every(START + timedelta(days=1), 5):
        s.add(day, f"{rng.choice(['WOOLWORTHS', 'COLES'])} {rng.randint(1000, 9999)} RYDE {card(rng)}", -rng.uniform(60, 180), "Groceries")
    s.finish()
    s.truth = {"earners": [
        {"payer": "COASTAL HEALTH", "gross": 110_000, "has_help": False, "frequency": "fortnightly", "net_pay": sam_pay},
        {"payer": "BLUEGUM EDUCATION", "gross": 75_000, "has_help": False, "frequency": "monthly", "net_pay": jordan_pay},
    ]}
    return s


def make_riley() -> Statement:
    rng = random.Random(3)
    s = Statement("riley", "Riley Morgan", "3 Placeholder Lane, Nowhere NSW 2997", "999-003", "99001122", 1_450.00, "posted")
    for day in every(date(2026, 7, 6), 7):
        s.add(day, "UBER BV DRIVER PAYOUT", round(rng.uniform(180, 620), 2), "Income – other")
    for day in sorted(rng.sample([START + timedelta(days=d) for d in range(0, 92)], 7)):
        s.add(day, "WAGES HARBOUR CAFE PTY LTD", round(rng.uniform(320, 980), 2), "Income – salary")
    for day in monthly(1):
        s.add(day, "RENT SHARE HOUSE BOND & RENT PAYMENT", -1_100.00, "Rent/mortgage")
        s.add(day + timedelta(days=12), "VODAFONE PREPAID RECHARGE", -45.00, "Phone/internet")
        s.add(day + timedelta(days=4), f"SPOTIFY AU {card(rng)}", -13.99, "Subscriptions")
        s.add(day + timedelta(days=9), f"YOUTUBE PREMIUM {card(rng)}", -16.99, "Subscriptions")
        s.add(day + timedelta(days=15), "MONTHLY ACCOUNT FEE", -5.00, "Fees")
    for day in every(date(2026, 7, 4), 6):
        s.add(day, f"{rng.choice(['SPORTSBET', 'TAB NSW', 'LADBROKES'])} {receipt(rng)}", -rng.choice([20, 30, 50, 80]), "Gambling")
    for day in every(date(2026, 7, 8), 14):
        s.add(day, f"ZIP PAY REPAYMENT {receipt(rng)}", -rng.choice([65.00, 80.00]), "Debt – BNPL")
    for day in every(date(2026, 7, 11), 10):
        s.add(day, f"ATM WITHDRAWAL {rng.choice(['GEORGE ST', 'OXFORD ST'])}", -rng.choice([50, 100, 200]), "Cash withdrawals")
    s.add(date(2026, 8, 22), f"AFTERPAY DISHONOURED PAYMENT {receipt(rng)}", 0.00, "Debt – BNPL")
    s.add(date(2026, 8, 22), "DISHONOUR FEE", -15.00, "Fees")
    s.add(date(2026, 9, 14), "OVERDRAWN ACCOUNT FEE", -10.00, "Fees")
    s.add(date(2026, 7, 25), "TRANSFER FROM M MORGAN BIRTHDAY", 200.00, "Income – other")
    everyday_spending(s, rng, scale=0.9, grocers=("COLES", "ALDI STORES", "IGA"))
    for day in every(START + timedelta(days=3), 6):
        s.add(day, f"{rng.choice(['UBER *EATS', 'DOORDASH', 'GRILLD'])} {card(rng)}", -rng.uniform(22, 48), "Dining/takeaway")
    s.rows = [r for r in s.rows if r["amount"] != 0]   # a dishonoured payment doesn't move money
    s.finish()
    s.truth = {"earners": [], "irregular": True}
    return s


# ---------------------------------------------------------------------------
# Writing files
# ---------------------------------------------------------------------------
def money(x: float) -> str:
    return f"{x:,.2f}"


def write_csv(s: Statement) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"{BANK} — {SAMPLE_MARK}"])
    w.writerow([f"Account holder: {s.holder}"])
    w.writerow([f"BSB {s.bsb}  Account {s.account}"])
    w.writerow([])
    if s.csv_layout == "amount":            # dd/mm/yyyy, signed amount
        w.writerow(["Date", "Description", "Amount", "Balance"])
        for r in s.rows:
            w.writerow([r["date"].strftime("%d/%m/%Y"), r["description"], f"{r['amount']:.2f}", f"{r['balance']:.2f}"])
    elif s.csv_layout == "debit_credit":    # ISO dates, separate positive debit/credit columns
        w.writerow(["Transaction Date", "Narrative", "Debit", "Credit", "Balance"])
        for r in s.rows:
            debit = f"{-r['amount']:.2f}" if r["amount"] < 0 else ""
            credit = f"{r['amount']:.2f}" if r["amount"] > 0 else ""
            w.writerow([r["date"].isoformat(), r["description"], debit, credit, f"{r['balance']:.2f}"])
    else:                                   # "01 Jul 2026", $-formatted signed amounts
        w.writerow(["Posted", "Details", "Amount", "Running Balance"])
        for r in s.rows:
            amount = f"-${-r['amount']:,.2f}" if r["amount"] < 0 else f"${r['amount']:,.2f}"
            w.writerow([r["date"].strftime("%d %b %Y"), r["description"], amount, f"{r['balance']:.2f}"])
    return out.getvalue().encode("utf-8")


def write_pdf(s: Statement) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=True)  # invariant: identical bytes every run
    width, height = A4
    rows_per_page = 45

    def header(page: int) -> float:
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, height - 40, f"{BANK} — Transaction statement")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, height - 58, SAMPLE_MARK)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(40, height - 74, f"{s.holder}, {s.address}")
        pdf.drawString(40, height - 86, f"BSB {s.bsb}  Account number {s.account}  Page {page}")
        pdf.drawString(40, height - 98, f"Statement period 01 Jul 2026 to 30 Sep 2026")
        y = height - 122
        pdf.setFont("Helvetica-Bold", 8)
        for x, label in ((40, "Date"), (100, "Description"), (390, "Debit"), (450, "Credit"), (520, "Balance")):
            pdf.drawString(x, y, label)
        return y - 14

    y = header(1)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(100, y, "OPENING BALANCE")
    pdf.drawRightString(560, y, money(s.opening_balance))
    y -= 12
    for i, r in enumerate(s.rows):
        if i and i % rows_per_page == 0:
            pdf.showPage()
            y = header(i // rows_per_page + 1)
            pdf.setFont("Helvetica", 8)
        pdf.drawString(40, y, r["date"].strftime("%d %b %Y"))
        pdf.drawString(100, y, r["description"][:58])
        if r["amount"] < 0:
            pdf.drawRightString(425, y, money(-r["amount"]))
        else:
            pdf.drawRightString(490, y, money(r["amount"]))
        pdf.drawRightString(560, y, money(r["balance"]))
        y -= 12
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def write_truth(s: Statement) -> str:
    truth = {
        "note": SAMPLE_MARK,
        "transactions": len(s.rows),
        "start": START.isoformat(),
        "end": max(r["date"] for r in s.rows).isoformat(),
        "first_date": min(r["date"] for r in s.rows).isoformat(),
        "categories": [r["category"] for r in s.rows],
        "amounts": [r["amount"] for r in s.rows],
        **s.truth,
    }
    return json.dumps(truth, indent=2, ensure_ascii=False) + "\n"


PERSONAS = (make_alex, make_sam_jordan, make_riley)


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for make in PERSONAS:
        s = make()
        (SAMPLES / f"{s.key}.csv").write_bytes(write_csv(s))
        (SAMPLES / f"{s.key}.pdf").write_bytes(write_pdf(s))
        (SAMPLES / f"{s.key}_truth.json").write_text(write_truth(s), encoding="utf-8")
        print(f"{s.key}: {len(s.rows)} transactions")
    if "--report" in sys.argv:
        from engine.statements.accuracy import accuracy_report
        for line in accuracy_report(SAMPLES):
            print(line)


if __name__ == "__main__":
    main()

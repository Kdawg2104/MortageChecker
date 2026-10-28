"""Read bank statements (CSV or text-based PDF) from in-memory bytes into one clean table.

Output columns: date, description (redacted), amount (+credit / -debit), balance (optional).
Header lines (account holder, address, account numbers) are never kept, and nothing is
written to disk: files are read from bytes, never saved.
"""

import csv
import io
import re
from dataclasses import dataclass

import pandas as pd

from engine.statements.pdf_text import extract_pdf_text
from engine.statements.redact import redact

MIN_DAYS = 85   # about 3 months; less than this and results are less reliable

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d-%m-%Y", "%d/%m/%y", "%d %B %Y", "%d-%b-%Y")
COLUMN_NAMES = {
    "date": ("date", "transaction date", "posted", "posting date", "value date", "effective date"),
    "description": ("description", "narrative", "details", "transaction details", "particulars", "transaction", "memo"),
    "amount": ("amount", "transaction amount", "value"),
    "debit": ("debit", "debits", "withdrawal", "withdrawals", "money out", "paid out"),
    "credit": ("credit", "credits", "deposit", "deposits", "money in", "paid in"),
    "balance": ("balance", "running balance", "closing balance"),
}
COLUMNS = ["date", "description", "amount", "balance"]


class NeedsColumnMapping(Exception):
    """The CSV layout wasn't recognised; the user needs to say which column is which."""

    def __init__(self, columns: list[str], preview: list[list[str]]):
        super().__init__("Couldn't recognise the CSV columns")
        self.columns = columns
        self.preview = preview


class ScannedPdfError(Exception):
    """The PDF has no text layer (probably scanned), so it can't be read without OCR."""


@dataclass(frozen=True)
class ColumnMapping:
    """Which column holds what. Either `amount`, or `debit` and/or `credit`."""

    date: str
    description: str
    amount: str | None = None
    debit: str | None = None
    credit: str | None = None
    balance: str | None = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def parse_money(text) -> float | None:
    """'$1,234.50', '-$12.00', '(12.00)', '12.00 DR', '12.00 CR' -> float. Blank -> None."""
    if text is None:
        return None
    s = str(text).strip().upper().replace("$", "").replace(",", "").replace(" ", "")
    if not s or s in ("-", "NAN"):
        return None
    sign = 1
    if s.endswith("DR"):
        sign, s = -1, s[:-2]
    elif s.endswith("CR"):
        s = s[:-2]
    if s.startswith("(") and s.endswith(")"):
        sign, s = -sign, s[1:-1]
    try:
        return sign * float(s)
    except ValueError:
        return None


def detect_date_format(values: list[str]) -> str | None:
    """The first known date format that every value matches."""
    values = [v.strip() for v in values if v and v.strip()]
    for fmt in DATE_FORMATS:
        try:
            pd.to_datetime(values, format=fmt)
            return fmt
        except (ValueError, TypeError):
            continue
    return None


def _find(header: list[str], kind: str) -> str | None:
    lowered = {h.strip().lower(): h for h in header}
    return next((lowered[name] for name in COLUMN_NAMES[kind] if name in lowered), None)


def detect_mapping(header: list[str]) -> ColumnMapping | None:
    """Guess which column is which from the header names."""
    date_col, desc_col = _find(header, "date"), _find(header, "description")
    amount, debit, credit = _find(header, "amount"), _find(header, "debit"), _find(header, "credit")
    if not date_col or not desc_col or not (amount or debit or credit):
        return None
    return ColumnMapping(date_col, desc_col, amount, debit, credit, _find(header, "balance"))


def _finish(frame: pd.DataFrame) -> pd.DataFrame:
    """Redact descriptions, keep the standard columns and sort by date (keeping file order)."""
    frame["description"] = frame["description"].map(redact)
    frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
    return frame[COLUMNS]


def signs_from_balance(frame: pd.DataFrame, opening: float | None = None) -> pd.DataFrame:
    """Use the running balance to decide whether each amount was money in or out.

    Handles unsigned amounts (debits and credits both positive) and files where debits are
    positive and credits negative. A row is only changed when the balance moved by exactly
    its amount. The first row has no previous balance unless `opening` is given; it follows
    whatever convention the other rows turned out to use.
    """
    if frame["balance"].isna().any() or len(frame) < 2:
        return frame
    previous = frame["balance"].shift(1)
    if opening is not None:
        previous.iloc[0] = opening
    change = frame["balance"] - previous
    size = frame["amount"].abs()
    known = (change.abs() - size).abs() < 0.01
    signed = size.where(change > 0, -size)
    corrected = frame["amount"].where(~known, signed)
    if pd.isna(previous.iloc[0]):
        others = known.iloc[1:]
        flipped = (corrected.iloc[1:][others] != frame["amount"].iloc[1:][others]).mean() if others.any() else 0
        if flipped > 0.5:
            corrected.iloc[0] = -frame["amount"].iloc[0] if (frame["amount"] < 0).any() else -size.iloc[0]
    frame = frame.copy()
    frame["amount"] = corrected
    return frame


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def read_csv_rows(data: bytes) -> list[list[str]]:
    text = data.decode("utf-8-sig", errors="replace")
    return [row for row in csv.reader(io.StringIO(text))]


def parse_csv(data: bytes, mapping: ColumnMapping | None = None) -> pd.DataFrame:
    """Parse a CSV export. Raises NeedsColumnMapping if the layout isn't recognised."""
    rows = read_csv_rows(data)
    header_index, header = None, None
    for i, row in enumerate(rows[:30]):
        if mapping is None and detect_mapping(row):
            header_index, header, mapping = i, row, detect_mapping(row)
            break
        if mapping is not None and mapping.date in row and mapping.description in row:
            header_index, header = i, row
            break

    if header is None:
        if mapping is None:
            widest = max((len(r) for r in rows), default=0)
            columns = [f"Column {i + 1}" for i in range(widest)]
            raise NeedsColumnMapping(columns, [r for r in rows if len(r) == widest][:5])
        # Headerless file with a user mapping on "Column N" names
        widest = max(len(r) for r in rows)
        header, header_index = [f"Column {i + 1}" for i in range(widest)], -1

    body = [r + [""] * (len(header) - len(r)) for r in rows[header_index + 1:] if any(cell.strip() for cell in r)]
    table = pd.DataFrame(body, columns=header)
    fmt = detect_date_format(table[mapping.date].tolist())
    if fmt is None:
        # Drop non-date rows (e.g. a closing-balance line) and try again
        table = table[table[mapping.date].str.match(r"^\s*\d")]
        fmt = detect_date_format(table[mapping.date].tolist())
    if fmt is None:
        raise NeedsColumnMapping(header, body[:5])

    frame = pd.DataFrame({
        "date": pd.to_datetime(table[mapping.date].str.strip(), format=fmt),
        "description": table[mapping.description].astype(str),
    })
    if mapping.amount:
        frame["amount"] = table[mapping.amount].map(parse_money)
    else:
        debit = table[mapping.debit].map(parse_money).fillna(0).abs() if mapping.debit else 0
        credit = table[mapping.credit].map(parse_money).fillna(0).abs() if mapping.credit else 0
        frame["amount"] = credit - debit
    frame["balance"] = table[mapping.balance].map(parse_money) if mapping.balance else float("nan")
    frame = frame.dropna(subset=["amount"])
    if mapping.amount:
        frame = signs_from_balance(frame.reset_index(drop=True))
    return _finish(frame)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
MONEY = r"-?\$?[\d,]+\.\d{2}(?:\s?(?:CR|DR))?"
LINE = re.compile(
    rf"^(?P<date>\d{{1,2}}[ /-](?:[A-Za-z]{{3,9}}|\d{{1,2}})[ /-]\d{{2,4}})\s+(?P<desc>.+?)\s+"
    rf"(?P<amount>{MONEY})(?:\s+(?P<balance>{MONEY}))?$"
)
OPENING = re.compile(rf"OPENING BALANCE\s+(?P<balance>{MONEY})", re.IGNORECASE)


def parse_pdf(data: bytes, backend: str | None = None) -> pd.DataFrame:
    """Parse a text-based PDF statement. Raises ScannedPdfError if there's no text to read.

    backend picks how the text is read (see pdf_text.py); by default whichever is installed.
    """
    text = extract_pdf_text(data, backend)
    if not text.strip():
        raise ScannedPdfError("No text found in this PDF")

    opening = None
    records = []
    for line in text.splitlines():
        line = line.strip()
        if opening is None and (m := OPENING.search(line)):
            opening = parse_money(m.group("balance"))
            continue
        m = LINE.match(line)
        if m:
            records.append((m.group("date"), m.group("desc"), parse_money(m.group("amount")), parse_money(m.group("balance"))))
    if not records:
        raise ScannedPdfError("No transactions found in this PDF's text")

    fmt = detect_date_format([r[0] for r in records])
    frame = pd.DataFrame(records, columns=["date", "description", "amount", "balance"])
    frame["date"] = pd.to_datetime(frame["date"], format=fmt) if fmt else pd.to_datetime(frame["date"], dayfirst=True)

    # PDFs usually show debits and credits as positive numbers in separate columns:
    # the change in running balance tells us which way each one went.
    frame = signs_from_balance(frame, opening)
    return _finish(frame)


# ---------------------------------------------------------------------------
# Several files
# ---------------------------------------------------------------------------
def parse_file(name: str, data: bytes, mapping: ColumnMapping | None = None) -> pd.DataFrame:
    """Parse one file by its extension."""
    if name.lower().endswith(".pdf"):
        return parse_pdf(data)
    return parse_csv(data, mapping)


def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Join several statements, dropping transactions that appear in more than one file.

    Genuine repeats within one file (two identical coffees on the same day) are kept: rows are
    matched across files by (date, description, amount) plus how many times they've occurred.
    """
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    keyed = []
    for frame in frames:
        frame = frame.copy()
        frame["_occurrence"] = frame.groupby(["date", "description", "amount"]).cumcount()
        keyed.append(frame)
    joined = pd.concat(keyed, ignore_index=True)
    joined = joined.drop_duplicates(subset=["date", "description", "amount", "_occurrence"])
    return joined.drop(columns="_occurrence").sort_values("date", kind="stable").reset_index(drop=True)


def statement_balances(frame: pd.DataFrame) -> tuple[float, float] | None:
    """(opening, closing) balance from the running balance, or None if the file had no balances."""
    if frame.empty or frame["balance"].isna().any():
        return None
    opening = frame["balance"].iloc[0] - frame["amount"].iloc[0]
    return round(float(opening), 2), round(float(frame["balance"].iloc[-1]), 2)


def coverage_days(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    return int((frame["date"].max() - frame["date"].min()).days) + 1


def coverage_warning(frame: pd.DataFrame) -> str | None:
    """A warning if the statements cover less than about 3 months."""
    if coverage_days(frame) < MIN_DAYS:
        return "Less than 3 months detected — results will be less reliable."
    return None

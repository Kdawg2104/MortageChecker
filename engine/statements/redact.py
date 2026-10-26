"""Remove sensitive details from transaction descriptions straight after parsing.

Regex-based, applied in order. Business names (e.g. an employer "... PTY LTD") are kept,
because they're needed to recognise income; personal names in transfers are removed.
"""

import re

BUSINESS_WORDS = ("PTY", "LTD", "LIMITED", "INC", "CORP", "GROUP", "SERVICES", "COUNCIL", "UNIVERSITY", "SAVINGS",
                  "OFFSET", "ACCT", "ACCOUNT", "LOAN", "CARD", "BV")

# Order matters: card numbers before generic account numbers, BSB before account numbers.
PATTERNS = (
    # Card numbers, full or masked: 4321XXXXXXXX1234, 4321 **** **** 1234, xx1234
    (re.compile(r"\b\d{4}[\sX*]{4,14}\d{4}\b", re.IGNORECASE), "[card]"),
    (re.compile(r"\b(?:X{2,}|\*{2,})\d{4}\b", re.IGNORECASE), "[card]"),
    (re.compile(r"\b\d{4}(?:[ -]\d{4}){3}\b"), "[card]"),
    # BSB: 062-000 or 062 000 (followed by space/end so it isn't part of a longer number)
    (re.compile(r"\bBSB\s*:?\s*\d{3}[- ]?\d{3}\b", re.IGNORECASE), "[bsb]"),
    (re.compile(r"\b\d{3}-\d{3}\b"), "[bsb]"),
    # Reference / receipt / invoice numbers
    (re.compile(r"\b(?:REF(?:ERENCE)?|RECEIPT|RCPT|INV(?:OICE)?|TXN|ID|NO)\b\.?\s*:?\s*#?[A-Z0-9-]*\d[A-Z0-9-]*", re.IGNORECASE), "[ref]"),
    # Account numbers and any other long digit runs
    (re.compile(r"\b\d{6,}\b"), "[account]"),
)

# "TRANSFER TO J CITIZEN", "FROM M MORGAN", "PAYMENT TO JANE DOE": up to three name-like words
NAME_AFTER = re.compile(
    r"\b(TO|FROM)\s+((?:\[\w+\]\s+)*)((?:[A-Z]\.?\s+)?[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)", re.IGNORECASE
)


def _redact_name(match: re.Match) -> str:
    """Replace a personal name after TO/FROM, skipping placeholders like [bsb]; keep businesses."""
    words = match.group(3).upper().split()
    if any(w.strip(".") in BUSINESS_WORDS for w in words):
        return match.group(0)
    return f"{match.group(1)} {match.group(2)}[name]"


def redact(text: str) -> str:
    """Description with card numbers, BSBs, account and reference numbers and personal names removed."""
    text = str(text)
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    text = NAME_AFTER.sub(_redact_name, text)
    return re.sub(r"\s{2,}", " ", text).strip()

"""Statement Analyser tests. Synthetic sample data only (data/samples/, made by scripts/make_samples.py)."""

import io
import json
from pathlib import Path

import pandas as pd
import pytest

from engine.statements.accuracy import SAMPLE_KEYS, persona_accuracy
from engine.statements.analyse import (
    estimate_gross,
    household_income_split,
    lender_flags,
    summarise,
    to_calculator_inputs,
)
from engine.statements.categorise import TRANSFER, categorise, detect_income, earners
from engine.statements.parse import (
    ColumnMapping,
    NeedsColumnMapping,
    ScannedPdfError,
    combine,
    coverage_days,
    coverage_warning,
    parse_csv,
    parse_file,
    parse_pdf,
)
from engine.statements.redact import redact
from engine.tax import take_home

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
MIN_ACCURACY = 0.90


def truth(key: str) -> dict:
    return json.loads((SAMPLES / f"{key}_truth.json").read_text(encoding="utf-8"))


def load(key: str, extension: str = "csv") -> pd.DataFrame:
    return parse_file(f"{key}.{extension}", (SAMPLES / f"{key}.{extension}").read_bytes())


# ---------------- Parsing ----------------
@pytest.mark.parametrize("key", SAMPLE_KEYS)
@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_samples_parse_to_expected_rows_and_dates(key, extension):
    t = truth(key)
    frame = load(key, extension)
    assert len(frame) == t["transactions"]
    assert str(frame["date"].min().date()) == t["first_date"]
    assert str(frame["date"].max().date()) == t["end"]
    assert frame["amount"].tolist() == pytest.approx(t["amounts"])


@pytest.mark.parametrize("key", SAMPLE_KEYS)
def test_combining_csv_and_pdf_removes_duplicates(key):
    assert len(combine([load(key, "csv"), load(key, "pdf")])) == truth(key)["transactions"]


def test_combine_keeps_genuine_repeats_within_one_file():
    day = pd.Timestamp("2026-07-01")
    one = pd.DataFrame({"date": [day, day], "description": ["COFFEE", "COFFEE"], "amount": [-5.0, -5.0], "balance": [None, None]})
    assert len(combine([one])) == 2
    assert len(combine([one, one])) == 2


def test_debit_credit_columns_and_iso_dates():
    data = b"Transaction Date,Narrative,Debit,Credit,Balance\n2026-07-01,COLES,50.00,,950.00\n2026-07-02,SALARY X PTY LTD,,2000.00,2950.00\n"
    frame = parse_csv(data)
    assert frame["amount"].tolist() == [-50.0, 2000.0]


def test_positive_debits_are_flipped_using_balance():
    data = b"Date,Description,Amount,Balance\n01/07/2026,COLES,50.00,950.00\n02/07/2026,KMART,20.00,930.00\n03/07/2026,SALARY,100.00,1030.00\n"
    # Debits written as positive numbers: the balance shows they're money out
    frame = parse_csv(data)
    assert frame["amount"].iloc[1] == -20.0


def test_unknown_layout_needs_column_mapping_then_works():
    data = b"01/07/2026,-50.00,COLES SYDNEY,950.00\n02/07/2026,-20.00,KMART,930.00\n"
    with pytest.raises(NeedsColumnMapping) as error:
        parse_csv(data)
    assert error.value.columns == ["Column 1", "Column 2", "Column 3", "Column 4"]
    mapping = ColumnMapping(date="Column 1", description="Column 3", amount="Column 2", balance="Column 4")
    frame = parse_csv(data, mapping)
    assert frame["amount"].tolist() == [-50.0, -20.0]
    assert frame["description"].tolist() == ["COLES SYDNEY", "KMART"]


def test_pdf_without_text_is_reported_as_scanned():
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.rect(100, 100, 200, 200, fill=1)   # a drawing, but no text: like a scanned page
    page.showPage()
    page.save()
    with pytest.raises(ScannedPdfError):
        parse_pdf(buffer.getvalue())


def test_short_period_warning():
    full = load("alex")
    assert coverage_warning(full) is None
    month = full[full["date"] < "2026-08-01"]
    assert coverage_days(month) < 85
    assert "Less than 3 months" in coverage_warning(month)


def test_raw_headers_are_not_kept():
    frame = load("alex", "pdf")
    text = " ".join(frame["description"])
    for secret in ("Alex Taylor", "Example Street", "999-001", "11223344", "Account number"):
        assert secret not in text


# ---------------- Redaction ----------------
@pytest.mark.parametrize(
    "raw, must_not_contain",
    [
        ("WOOLWORTHS 1234 SYDNEY CARD 4954XXXXXXXX6217", "4954XXXXXXXX6217"),
        ("PAYMENT CARD 4321 **** **** 9876", "9876"),
        ("TFR TO 062-000 12345678", "062-000"),
        ("TFR TO 062-000 12345678", "12345678"),
        ("BSB 062 000 ACC 1234567", "062 000"),
        ("RENT HARBOURSIDE REALTY REF 990298", "990298"),
        ("BILLER RECEIPT NO 55KX9921", "55KX9921"),
        ("TRANSFER TO J CITIZEN DINNER", "CITIZEN"),
        ("PAYMENT FROM JANE DOE", "JANE"),
        ("PAYMENT TO 062-000 98765432 JANE DOE", "DOE"),
    ],
)
def test_redaction_removes_sensitive_details(raw, must_not_contain):
    assert must_not_contain not in redact(raw)


def test_redaction_keeps_business_payers():
    assert "WATTLE LOGISTICS PTY LTD" in redact("SALARY WATTLE LOGISTICS PTY LTD REF 12345678")
    assert redact("TRANSFER TO SAVINGS ACCT 12345678") == "TRANSFER TO SAVINGS ACCT [account]"


# ---------------- Categorisation ----------------
@pytest.mark.parametrize("key", SAMPLE_KEYS)
@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_categorisation_accuracy(key, extension):
    by_value, by_count = persona_accuracy(SAMPLES, key, extension)
    print(f"{key} {extension}: {by_value:.1%} by value, {by_count:.1%} by count")
    assert by_value >= MIN_ACCURACY


def test_specific_merchant_beats_generic_keyword():
    frame = categorise(pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"]),
        "description": ["YOUTUBE PREMIUM", "SHELL COLES EXPRESS", "COFFEE SHOP"],
        "amount": [-16.99, -70.0, -5.0],
        "balance": [None, None, None],
    }))
    assert frame["category"].tolist() == ["Subscriptions", "Transport/fuel", "Shopping"]


def test_unknown_items_are_low_confidence():
    frame = categorise(pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01"]), "description": ["ZZXQ HOLDINGS"], "amount": [-10.0], "balance": [None],
    }))
    assert frame.loc[0, "category"] == "Other"
    assert frame.loc[0, "confidence"] == "low"


# ---------------- Income ----------------
def months_of(frame):
    return coverage_days(frame) / (365.25 / 12)


def test_alex_income_detected():
    frame = categorise(load("alex"))
    found = earners(detect_income(frame, months_of(frame)))
    expected = truth("alex")["earners"][0]
    assert len(found) == 1
    assert found[0].frequency == "fortnightly"
    assert found[0].typical_amount == pytest.approx(expected["net_pay"])
    assert "WATTLE LOGISTICS" in found[0].payer


def test_sam_and_jordan_both_earners_detected():
    frame = categorise(load("sam_jordan", "pdf"))
    found = {e.frequency: e for e in earners(detect_income(frame, months_of(frame)))}
    for expected in truth("sam_jordan")["earners"]:
        source = found[expected["frequency"]]
        assert expected["payer"] in source.payer
        assert source.typical_amount == pytest.approx(expected["net_pay"])


def test_riley_income_is_irregular():
    frame = categorise(load("riley"))
    sources = detect_income(frame, months_of(frame))
    assert earners(sources) == []
    assert all(not s.regular for s in sources)
    assert any(f.title == "Irregular income" for f in lender_flags(frame, summarise(frame)))


@pytest.mark.parametrize("key", SAMPLE_KEYS)
def test_own_transfers_excluded_from_income_and_spending(key):
    frame = categorise(load(key))
    summary = summarise(frame)
    assert TRANSFER not in summary.by_category
    transfers_in = frame[(frame["category"] == TRANSFER) & (frame["amount"] > 0)]
    assert not any(src.payer in set(transfers_in["merchant"]) for src in summary.income_sources)
    # Turning transfers into spending would change the totals: check they really were left out
    spending_without = summary.spending
    frame.loc[frame["category"] == TRANSFER, "category"] = "Other"
    assert summarise(frame).spending >= spending_without


def test_alex_transfers_found():
    frame = categorise(load("alex"))
    assert (frame["category"] == TRANSFER).sum() == sum(c == TRANSFER for c in truth("alex")["categories"])


# ---------------- Gross income ----------------
@pytest.mark.parametrize("gross", [25_000, 45_000, 70_000, 85_000, 130_000, 200_000])
@pytest.mark.parametrize("has_help", [False, True])
def test_gross_inversion_round_trips(gross, has_help):
    monthly_net = take_home(gross, has_help).net / 12
    estimate = estimate_gross(monthly_net, has_help)
    assert take_home(estimate, has_help).net / 12 == pytest.approx(monthly_net, abs=1.0)


@pytest.mark.parametrize("key, helps", [("alex", [True]), ("sam_jordan", [False, False])])
def test_true_salaries_recovered_from_samples(key, helps):
    summary = summarise(categorise(load(key)))
    estimates = [estimate_gross(n, h) for n, h in zip(household_income_split(summary), helps)]
    assert estimates == pytest.approx([e["gross"] for e in truth(key)["earners"]], abs=100)


def test_regular_payments_use_their_frequency():
    summary = summarise(categorise(load("alex")))
    assert summary.housing == pytest.approx(620 * 52 / 12, abs=0.01)


def test_calculator_inputs_exclude_rent_and_include_debts():
    summary = summarise(categorise(load("sam_jordan")))
    inputs = to_calculator_inputs(summary, [110_000, 75_000], [False, False])
    assert inputs["borrowers"] == 2
    assert inputs["expenses"] == round(summary.essentials + summary.discretionary)
    assert inputs["other_debts"] == round(summary.debt_total)
    assert inputs["income_1"] == 75_000


# ---------------- Lender flags ----------------
def test_riley_flags():
    frame = categorise(load("riley", "pdf"))
    titles = {f.title for f in lender_flags(frame, summarise(frame))}
    assert {"Buy now, pay later", "Gambling transactions", "Account overdrawn", "Dishonour or overdraft fees"} <= titles


def test_sam_and_jordan_have_no_gambling_or_overdrawn_flags():
    frame = categorise(load("sam_jordan"))
    titles = {f.title for f in lender_flags(frame, summarise(frame))}
    assert not titles & {"Gambling transactions", "Account overdrawn", "Dishonour or overdraft fees"}

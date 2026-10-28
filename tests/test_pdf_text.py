"""Both PDF backends (pdfplumber locally, pdfminer.six in the browser) must read statements identically."""

import pandas as pd
import pytest

from engine.statements.parse import parse_pdf, statement_balances
from engine.statements.pdf_text import BACKENDS, available_backend, extract_pdf_text
from tests.test_privacy import SAMPLES

SAMPLE_PDFS = sorted(SAMPLES.glob("*.pdf"))


def test_pdfplumber_used_when_installed():
    assert available_backend() == "pdfplumber"


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        extract_pdf_text(b"", backend="nope")


@pytest.mark.parametrize("path", SAMPLE_PDFS, ids=lambda p: p.name)
def test_backends_give_identical_transactions(path):
    frames = [parse_pdf(path.read_bytes(), backend=backend) for backend in BACKENDS]
    pd.testing.assert_frame_equal(frames[0], frames[1])


@pytest.mark.parametrize("backend", BACKENDS)
def test_jamie_sample_with_each_backend(backend):
    frame = parse_pdf((SAMPLES / "sample_jamie_statement.pdf").read_bytes(), backend=backend)
    assert len(frame) == 88
    assert frame["date"].min() == pd.Timestamp("2026-07-01")
    assert frame["date"].max() == pd.Timestamp("2026-09-30")
    opening, closing = statement_balances(frame)
    assert opening == pytest.approx(40_000.00)
    assert closing == pytest.approx(49_322.77)

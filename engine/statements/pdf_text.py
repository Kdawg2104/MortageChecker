"""Text from a PDF statement, with two interchangeable backends.

- "pdfplumber" is used when it's installed (normal Python).
- "pdfminer" (pdfminer.six, pure Python) is the fallback. pdfplumber can't run in the browser
  build because it imports pypdfium2, a C extension with no WebAssembly version.

pdfplumber is itself built on pdfminer.six. With the layout settings below, pdfminer joins each
statement row into one line just as pdfplumber does, so both give identical transactions
(tests/test_pdf_text.py checks this on every sample PDF).
"""

import io

BACKENDS = ("pdfplumber", "pdfminer")


def available_backend() -> str:
    """The backend to use here: pdfplumber if it can be imported, otherwise pdfminer."""
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        return "pdfminer"
    return "pdfplumber"


def _pdfplumber_text(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _pdfminer_text(data: bytes) -> str:
    from pdfminer.high_level import extract_text
    from pdfminer.layout import LAParams

    # line_margin: keep rows that sit close together as separate lines.
    # char_margin: treat a whole row (date ... balance) as one line, however wide the column gaps.
    # boxes_flow=None: keep the page's top-to-bottom order instead of guessing a reading order.
    layout = LAParams(line_margin=0.1, char_margin=200, boxes_flow=None)
    return extract_text(io.BytesIO(data), laparams=layout)


def extract_pdf_text(data: bytes, backend: str | None = None) -> str:
    """All the text in a PDF (given as bytes, never a file), one statement row per line."""
    backend = backend or available_backend()
    if backend == "pdfplumber":
        return _pdfplumber_text(data)
    if backend == "pdfminer":
        return _pdfminer_text(data)
    raise ValueError(f"Unknown PDF backend {backend!r}; choose from {BACKENDS}")

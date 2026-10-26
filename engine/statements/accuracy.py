"""Categorisation accuracy against the synthetic samples' ground truth (for tests and reports)."""

import csv
import io
import json
from pathlib import Path

from engine.statements.categorise import categorise, value_accuracy
from engine.statements.parse import parse_file

SAMPLE_KEYS = ("alex", "sam_jordan", "riley")
JAMIE_FILES = ("sample_jamie_statement.csv", "sample_jamie_statement.pdf")
JAMIE_TRUTH = "sample_jamie_ground_truth.csv"


def persona_accuracy(samples: Path, key: str, extension: str = "csv") -> tuple[float, float]:
    """(accuracy by value, accuracy by count) for one persona's sample file."""
    truth = json.loads((samples / f"{key}_truth.json").read_text(encoding="utf-8"))
    frame = categorise(parse_file(f"{key}.{extension}", (samples / f"{key}.{extension}").read_bytes()))
    predicted = frame["category"].tolist()
    by_count = sum(p == t for p, t in zip(predicted, truth["categories"])) / len(predicted)
    return value_accuracy(predicted, truth["categories"], truth["amounts"]), by_count


def jamie_truth(samples: Path) -> list[dict]:
    """Jamie's ground truth: one row per transaction (date, description, amount, category)."""
    text = (samples / JAMIE_TRUTH).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def jamie_accuracy(samples: Path, filename: str) -> tuple[float, float]:
    """(accuracy by value, accuracy by count) for one of Jamie's statement files."""
    truth = jamie_truth(samples)
    frame = categorise(parse_file(filename, (samples / filename).read_bytes()))
    predicted = frame["category"].tolist()
    expected = [row["category"] for row in truth]
    by_count = sum(p == t for p, t in zip(predicted, expected)) / len(predicted)
    return value_accuracy(predicted, expected, [float(row["amount"]) for row in truth]), by_count


def accuracy_report(samples: Path) -> list[str]:
    lines = []
    for key in SAMPLE_KEYS:
        for extension in ("csv", "pdf"):
            by_value, by_count = persona_accuracy(samples, key, extension)
            lines.append(f"{key:11} {extension}: {by_value:.1%} by value, {by_count:.1%} by count")
    for filename in JAMIE_FILES:
        by_value, by_count = jamie_accuracy(samples, filename)
        lines.append(f"jamie       {filename.rsplit('.', 1)[1]}: {by_value:.1%} by value, {by_count:.1%} by count")
    return lines

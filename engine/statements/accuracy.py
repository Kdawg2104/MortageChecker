"""Categorisation accuracy against the synthetic samples' ground truth (for tests and reports)."""

import json
from pathlib import Path

from engine.statements.categorise import categorise, value_accuracy
from engine.statements.parse import parse_file

SAMPLE_KEYS = ("alex", "sam_jordan", "riley")


def persona_accuracy(samples: Path, key: str, extension: str = "csv") -> tuple[float, float]:
    """(accuracy by value, accuracy by count) for one persona's sample file."""
    truth = json.loads((samples / f"{key}_truth.json").read_text(encoding="utf-8"))
    frame = categorise(parse_file(f"{key}.{extension}", (samples / f"{key}.{extension}").read_bytes()))
    predicted = frame["category"].tolist()
    by_count = sum(p == t for p, t in zip(predicted, truth["categories"])) / len(predicted)
    return value_accuracy(predicted, truth["categories"], truth["amounts"]), by_count


def accuracy_report(samples: Path) -> list[str]:
    lines = []
    for key in SAMPLE_KEYS:
        for extension in ("csv", "pdf"):
            by_value, by_count = persona_accuracy(samples, key, extension)
            lines.append(f"{key:11} {extension}: {by_value:.1%} by value, {by_count:.1%} by count")
    return lines

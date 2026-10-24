"""Loads the market figures in data/market_snapshot.json.

The JSON file is the single source for every market figure the app displays.
This module only reads and validates it; it has no UI code.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "market_snapshot.json"
REQUIRED_FIELDS = ("id", "name", "value", "unit", "as_at", "source", "url", "notes")


@dataclass(frozen=True)
class MarketFigure:
    """One published figure, with where and when it came from."""

    id: str
    name: str
    value: float | list
    unit: str
    as_at: str
    source: str
    url: str
    notes: str
    category: str = "Other"
    decimals: int = 0


@dataclass(frozen=True)
class MarketSnapshot:
    """All market figures plus the date the file was last checked."""

    last_updated: str
    figures: tuple[MarketFigure, ...]

    def get(self, figure_id: str) -> MarketFigure:
        """Look up a figure by its id, e.g. "cash_rate". Raises KeyError if missing."""
        for figure in self.figures:
            if figure.id == figure_id:
                return figure
        raise KeyError(f"No market figure with id '{figure_id}'")

    def by_category(self) -> dict[str, list[MarketFigure]]:
        """Group figures by category, keeping the order they appear in the file."""
        groups: dict[str, list[MarketFigure]] = {}
        for figure in self.figures:
            groups.setdefault(figure.category, []).append(figure)
        return groups


def load_snapshot(path: Path = DEFAULT_PATH) -> MarketSnapshot:
    """Read and validate the snapshot file. Raises ValueError if an entry is incomplete."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    figures = []
    for entry in raw["figures"]:
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"Figure '{entry.get('id', '?')}' is missing: {', '.join(missing)}")
        figures.append(MarketFigure(**entry))
    return MarketSnapshot(last_updated=raw["last_updated"], figures=tuple(figures))

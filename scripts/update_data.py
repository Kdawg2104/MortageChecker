"""Download official RBA and ABS data and build the monthly history the Risk Simulator uses.

Run it by hand when new data is released:
    .venv/bin/python scripts/update_data.py

Original files go to data/raw/, clean monthly CSVs to data/processed/, and the download date
and series details to data/processed/metadata.json. The app never downloads anything itself;
it only reads data/processed/.
"""

import csv
import json
import re
import ssl
import urllib.request
from datetime import date
from pathlib import Path

import certifi
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

ABS = "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation"
RBA = "https://www.rba.gov.au/statistics/tables/csv"

# Official sources. ABS "latest-release" pages are searched for the current spreadsheet link.
SOURCES = {
    # A2 lists every cash rate decision with its effective date (F1.1 only has monthly averages)
    "rba_a2.csv": {"url": f"{RBA}/a2-data.csv", "series": {"ARBAMPCNCRT": "New cash rate target (decisions)"}},
    "rba_f5.csv": {"url": f"{RBA}/f5-data.csv", "series": {"FILRHLBVS": "Standard variable housing rate, owner-occupier"}},
    "rba_f6.csv": {"url": f"{RBA}/f6-data.csv", "series": {"FLRHOFVA": "Variable rate, new owner-occupier loans"}},
    # The ABS replaced the quarterly CPI with a monthly CPI; Sep quarter 2025 was the final quarterly release.
    "abs_cpi_quarterly_640101.xlsx": {
        "url": f"{ABS}/consumer-price-index-australia/sep-quarter-2025/640101.xlsx",
        "series": {"A2325846C": "CPI all groups, Australia (quarterly)"},
    },
    "abs_cpi_monthly_640101.xlsx": {
        "release_page": f"{ABS}/consumer-price-index-australia/latest-release",
        "file": "640101.xlsx",
        "series": {"A130393720C": "CPI all groups, Australia (monthly)"},
    },
    "abs_wpi_634501.xlsx": {
        "release_page": f"{ABS}/wage-price-index-australia/latest-release",
        "file": "634501.xlsx",
        "series": {"A2603609J": "Wage Price Index, hourly rates excl. bonuses, private and public, all industries"},
    },
}

# First month taken from the monthly CPI instead of the quarterly CPI
CPI_MONTHLY_FROM = pd.Period("2025-10", freq="M")


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------
def fetch(url: str) -> bytes:
    """Download a URL with certificate checking on.

    Uses certifi's certificate bundle, because the python.org build of Python on macOS
    doesn't ship one by default.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MortgageRealityCheck data update)"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=60, context=context) as response:
        return response.read()


def latest_file_url(release_page: str, filename: str) -> str:
    """Find the link to `filename` on an ABS latest-release page."""
    html = fetch(release_page).decode("utf-8", errors="ignore")
    match = re.search(rf'href="([^"]+/{re.escape(filename)})"', html)
    if not match:
        raise RuntimeError(f"Could not find {filename} on {release_page}")
    return "https://www.abs.gov.au" + match.group(1)


def download_all() -> dict:
    """Save every source file to data/raw/ and return the URL each came from."""
    RAW.mkdir(parents=True, exist_ok=True)
    used = {}
    for name, source in SOURCES.items():
        url = source.get("url") or latest_file_url(source["release_page"], source["file"])
        (RAW / name).write_bytes(fetch(url))
        used[name] = url
        print(f"Downloaded {name} from {url}")
    return used


# ---------------------------------------------------------------------------
# Reading the official file formats
# ---------------------------------------------------------------------------
def parse_rba_number(text: str) -> float:
    """A number from an RBA CSV cell. Early-1990 cash rate targets were ranges such as
    "17.00 to 17.50"; those are read as the midpoint (they're before the simulation history)."""
    if " to " in text:
        low, high = text.split(" to ")
        return (float(low) + float(high)) / 2
    return float(text)


def read_rba_csv(path: Path, series_id: str) -> pd.Series:
    """One series from an RBA statistical table CSV, indexed by month.

    RBA CSVs start with title rows of different widths, so they're read with the csv module.
    """
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    id_row = next(i for i, row in enumerate(rows) if row and row[0] == "Series ID")
    column = rows[id_row].index(series_id)
    pairs = [(row[0], row[column]) for row in rows[id_row + 1:] if len(row) > column and row[0] and row[column].strip()]
    dates = pd.to_datetime([d for d, _ in pairs], dayfirst=True, format="mixed")
    return pd.Series([parse_rba_number(v) for _, v in pairs], index=dates.to_period("M"), name=series_id)


def read_abs_series(path: Path, series_id: str) -> pd.Series:
    """One series from an ABS time-series spreadsheet (sheet Data1), indexed by month."""
    raw = pd.read_excel(path, sheet_name="Data1", header=None)
    column = raw.columns[raw.iloc[9] == series_id][0]
    data = raw.iloc[10:, [0, column]].dropna()
    dates = pd.to_datetime(data[0])
    return pd.Series(pd.to_numeric(data[column]).values, index=dates.dt.to_period("M"), name=series_id)


# ---------------------------------------------------------------------------
# Processing (pure functions, unit-tested in tests/test_update_data.py)
# ---------------------------------------------------------------------------
def quarterly_to_monthly(index: pd.Series) -> pd.Series:
    """Turn a quarterly index (dated by the quarter's last month) into monthly growth rates.

    Each quarter's change is spread evenly across its three months: a quarterly rise g
    becomes (1 + g)^(1/3) - 1 in each month, so the three months compound back to g exactly.
    """
    quarterly_growth = index.sort_index().pct_change().dropna()
    months, values = [], []
    for quarter_end, growth in quarterly_growth.items():
        monthly = (1 + growth) ** (1 / 3) - 1
        for offset in (2, 1, 0):
            months.append(quarter_end - offset)
            values.append(monthly)
    return pd.Series(values, index=pd.PeriodIndex(months, freq="M"))


def monthly_growth(index: pd.Series) -> pd.Series:
    """Month-on-month growth of a monthly index."""
    return index.sort_index().pct_change().dropna()


def cash_rate_month_end(decisions: pd.Series, end: pd.Period) -> pd.Series:
    """Cash rate target in force at the end of each month, from the list of decisions.

    `decisions` is the new target, indexed by the month each decision took effect.
    Months with no decision keep the previous target.
    """
    latest_per_month = decisions.groupby(level=0).last()
    months = pd.period_range(latest_per_month.index.min(), end, freq="M")
    return latest_per_month.reindex(months).ffill()


def cash_rate_changes(cash_rate: pd.Series) -> pd.Series:
    """Change in the month-end cash rate target from the previous month, in percentage points."""
    return cash_rate.sort_index().diff().dropna()


def splice_cpi(quarterly_derived: pd.Series, monthly: pd.Series, switch: pd.Period = CPI_MONTHLY_FROM) -> pd.Series:
    """Quarterly-derived monthly CPI growth before `switch`, actual monthly CPI growth from it."""
    return pd.concat([quarterly_derived[quarterly_derived.index < switch], monthly[monthly.index >= switch]])


def build_history(cash_rate: pd.Series, cpi_growth: pd.Series, wage_growth: pd.Series) -> pd.DataFrame:
    """Months where all three series exist, side by side."""
    frame = pd.DataFrame({
        "cash_rate": cash_rate,
        "cash_rate_change": cash_rate_changes(cash_rate),
        "cpi_growth": cpi_growth,
        "wage_growth": wage_growth,
    }).dropna()
    frame.index.name = "month"
    return frame


def describe(series: pd.Series) -> dict:
    return {"start": str(series.index.min()), "end": str(series.index.max()), "months": int(series.size)}


def main() -> None:
    urls = download_all()

    last_full_month = pd.Period(date.today(), freq="M") - 1
    cash_rate = cash_rate_month_end(read_rba_csv(RAW / "rba_a2.csv", "ARBAMPCNCRT"), last_full_month)
    standard_variable = read_rba_csv(RAW / "rba_f5.csv", "FILRHLBVS")
    new_loans_variable = read_rba_csv(RAW / "rba_f6.csv", "FLRHOFVA")
    cpi_quarterly = read_abs_series(RAW / "abs_cpi_quarterly_640101.xlsx", "A2325846C")
    cpi_monthly = read_abs_series(RAW / "abs_cpi_monthly_640101.xlsx", "A130393720C")
    wpi = read_abs_series(RAW / "abs_wpi_634501.xlsx", "A2603609J")

    cpi_growth = splice_cpi(quarterly_to_monthly(cpi_quarterly), monthly_growth(cpi_monthly))
    wage_growth = quarterly_to_monthly(wpi)
    history = build_history(cash_rate, cpi_growth, wage_growth)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    cash_rate.rename("cash_rate").rename_axis("month").to_csv(PROCESSED / "cash_rate.csv")
    cpi_growth.rename("cpi_growth").rename_axis("month").to_csv(PROCESSED / "cpi.csv")
    wage_growth.rename("wage_growth").rename_axis("month").to_csv(PROCESSED / "wages.csv")
    pd.DataFrame({"standard_variable": standard_variable, "new_loans_variable": new_loans_variable}) \
        .rename_axis("month").to_csv(PROCESSED / "housing_rates.csv")
    history.to_csv(PROCESSED / "history.csv")

    metadata = {
        "downloaded": date.today().isoformat(),
        "sources": {name: {"url": urls[name], "series": source["series"]} for name, source in SOURCES.items()},
        "series": {
            "cash_rate": describe(cash_rate),
            "cpi_quarterly_index": describe(cpi_quarterly),
            "cpi_monthly_index": describe(cpi_monthly),
            "cpi_growth": describe(cpi_growth),
            "wage_price_index": describe(wpi),
            "wage_growth": describe(wage_growth),
            "standard_variable_rate": describe(standard_variable),
            "new_loans_variable_rate": describe(new_loans_variable),
        },
        "history": describe(history["cash_rate"]),
        "notes": [
            "Quarterly series are spread evenly across their three months: (1 + g)^(1/3) - 1 per month.",
            f"CPI uses the final quarterly CPI (to Sep 2025) and the monthly CPI from {CPI_MONTHLY_FROM}.",
            "history.csv covers only months where cash rate, CPI and wages all exist.",
        ],
    }
    (PROCESSED / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    for key, info in metadata["series"].items():
        print(f"{key:26} {info['start']} to {info['end']} ({info['months']} months)")
    print(f"{'history (aligned)':26} {metadata['history']['start']} to {metadata['history']['end']} "
          f"({metadata['history']['months']} months)")


if __name__ == "__main__":
    main()

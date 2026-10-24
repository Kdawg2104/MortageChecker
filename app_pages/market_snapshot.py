"""Market Snapshot page: every figure in data/market_snapshot.json, with dates and sources."""

import streamlit as st

from ui.components import figure_card, get_snapshot, md_safe

CARDS_PER_ROW = 3

# Where readers can check for newer figures. Links only; no figures here.
OFFICIAL_SOURCES = [
    ("RBA: cash rate", "https://www.rba.gov.au/statistics/cash-rate/"),
    ("RBA: statistical tables (F6 housing lending rates)", "https://www.rba.gov.au/statistics/tables/"),
    ("ABS: Consumer Price Index", "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release"),
    ("ABS: Average Weekly Earnings", "https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/average-weekly-earnings-australia/latest-release"),
    ("APRA: news and publications", "https://www.apra.gov.au/news-and-publications"),
    ("ATO: resident tax rates", "https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents"),
    ("ATO: HECS/HELP repayment thresholds", "https://www.ato.gov.au/tax-rates-and-codes/study-and-training-support-loans-rates-and-repayment-thresholds"),
    ("Cotality: home value indices", "https://www.cotality.com/au/our-data/indices"),
    ("Moneysmart: home loans", "https://moneysmart.gov.au/home-loans"),
]


def bracket_table(brackets: list[dict]) -> str:
    """Markdown table of tax brackets, from the JSON list of {"over", "rate"}."""
    rows = ["| Taxable income | Rate |", "|---|---|"]
    for i, bracket in enumerate(brackets):
        lower = bracket["over"]
        upper = brackets[i + 1]["over"] if i + 1 < len(brackets) else None
        span = f"${lower:,} – ${upper:,}" if upper else f"Over ${lower:,}"
        rate = "Nil" if bracket["rate"] == 0 else f"{bracket['rate']}%"
        rows.append(f"| {span} | {rate} |")
    return "\n".join(rows)


snapshot = get_snapshot()

st.title("Market Snapshot")
st.info(f"Figures last updated: {snapshot.last_updated}", icon=":material/update:")
st.write(
    "The key numbers behind the calculator, each with its date and official source. "
    "These go out of date, so check the links below for the latest releases."
)

for category, figures in snapshot.by_category().items():
    st.subheader(category)
    for start in range(0, len(figures), CARDS_PER_ROW):
        row = figures[start:start + CARDS_PER_ROW]
        for column, figure in zip(st.columns(CARDS_PER_ROW), row):
            with column:
                if figure.unit == "brackets":
                    st.markdown(f"**{figure.name}**")
                    st.markdown(md_safe(bracket_table(figure.value)))
                    st.caption(md_safe(f"As at {figure.as_at}. {figure.notes} Source: [{figure.source}]({figure.url})"))
                else:
                    figure_card(figure)

st.subheader("Where to find the latest figures")
for name, url in OFFICIAL_SOURCES:
    st.markdown(f"- [{name}]({url})")

"""Home page: hero, what the app does, market headlines and the disclaimer."""

import streamlit as st

from ui.components import disclaimer_box, figure_card, get_snapshot, hero_container, info_card

# Fill in once assets/hero.jpg is added, e.g. "Photo by Jane Smith on Unsplash".
HERO_PHOTO_CREDIT = "Photo: [photographer name] on [Unsplash/Pexels]"

# Figures shown in the "Market at a glance" strip, by id in data/market_snapshot.json.
GLANCE_FIGURES = ("cash_rate", "avg_variable_rate_new", "median_national", "cpi_annual")

with hero_container():
    st.title("Headroom")
    st.markdown('<p class="mrc-subtitle">Your mortgage reality check</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="mrc-tagline">Find out if a mortgage really fits your income, your lifestyle '
        "and the risk of rate rises, before a lender tells you.</p>",
        unsafe_allow_html=True,
    )
    col_main, col_alt = st.columns([1, 1], gap="small", width=420)
    if col_main.button("Analyse your statements", type="primary", icon=":material/receipt_long:"):
        st.switch_page("app_pages/statement_analyser.py")
    if col_alt.button("Or use the calculator", icon=":material/calculate:"):
        st.switch_page("app_pages/calculator.py")
st.markdown(f'<p class="mrc-photo-credit">{HERO_PHOTO_CREDIT}</p>', unsafe_allow_html=True)

st.header("What this app does")
col1, col2, col3 = st.columns(3)
with col1:
    info_card(
        "Know your real budget",
        "Work out your take-home pay after tax, Medicare and HECS/HELP, then see what's left "
        "after living costs and repayments.",
    )
with col2:
    info_card(
        "Test rate rises",
        "See how your monthly budget changes if interest rates go up by 1, 2 or 3 percentage points.",
    )
with col3:
    info_card(
        "Understand your borrowing power",
        "Estimate how much a lender might lend when it tests your repayments at a higher rate.",
    )

snapshot = get_snapshot()
st.header("Market at a glance")
for column, figure_id in zip(st.columns(len(GLANCE_FIGURES)), GLANCE_FIGURES):
    with column:
        figure_card(snapshot.get(figure_id), show_details=False)
st.page_link("app_pages/market_snapshot.py", label="See all figures and sources", icon=":material/arrow_forward:")

st.write("")
disclaimer_box()

"""About & Disclaimer page: full disclaimer, key assumptions and project background."""

import streamlit as st

from ui.disclaimer import FULL_DISCLAIMER, KEY_ASSUMPTIONS

st.title("About & Disclaimer")

st.header("Disclaimer")
for point in FULL_DISCLAIMER:
    st.markdown(f"- {point}")

st.header("Key assumptions")
st.write("The calculator simplifies a lot. In particular:")
for point in KEY_ASSUMPTIONS:
    st.markdown(f"- {point}")

st.header("About this project")
st.markdown(
    """
Mortgage Reality Check is an independent personal portfolio project. It aims to show Australians
whether a mortgage is realistic for their income and lifestyle, and how exposed they'd be to rate
rises, in plain English.

The calculations use published Australian tax rates and lending rules. Market figures come from the
RBA, ABS, APRA, ATO and Cotality, with dates and sources on the **Market Snapshot** page.

For free, independent guidance, see [Moneysmart](https://moneysmart.gov.au/home-loans), run by
ASIC. To find a licensed adviser, see
[Moneysmart: choosing a financial adviser](https://moneysmart.gov.au/financial-advice/choosing-a-financial-adviser).
"""
)

"""About & Disclaimer page: full disclaimer, key assumptions and project background."""

import streamlit as st

from engine.runtime import IS_BROWSER
from ui.disclaimer import FULL_DISCLAIMER, KEY_ASSUMPTIONS

st.title("About & Disclaimer")

st.header("Disclaimer")
for point in FULL_DISCLAIMER:
    st.markdown(f"- {point}")

st.header("Key assumptions")
st.write("The calculator simplifies a lot. In particular:")
for point in KEY_ASSUMPTIONS:
    st.markdown(f"- {point}")

st.header("Your privacy")
if not IS_BROWSER:
    st.markdown(
        "This copy of Headroom runs on a server, so uploading your own statements is switched off unless you run it "
        "on your own computer. The browser version of Headroom (linked from the project's GitHub page) reads "
        "statements inside your web browser instead, so they never reach a server."
    )
st.markdown(
    """
**In the browser version, Headroom runs inside your web browser.** The site sends your browser the app's code, and a copy of
Python (Pyodide) runs it on your device. Statements you upload are read there and never sent to any server,
because there is no server to send them to. You can check this: open your browser's developer tools, choose the
Network tab, and upload a statement. No request is sent.

- Statement data is held in memory only and deleted after 10 minutes of inactivity, when you click
  "Clear my data", or when you close or refresh the tab.
- The page's security policy only lets it load code from this site and the code library site that hosts Python
  for the web (cdn.jsdelivr.net). There are no analytics or trackers.
- Account numbers, card numbers, names and reference numbers are removed as soon as a file is read.

**Honest limits:** this rests on the published code, which is open on GitHub for anyone to check, and on those
two sites serving it unchanged. Deleting data frees the memory, but the browser may not overwrite it straight away.
"""
)

st.header("About this project")
st.markdown(
    """
Headroom is an independent personal portfolio project. It aims to show Australians
whether a mortgage is realistic for their income and lifestyle, and how exposed they'd be to rate
rises, in plain English.

The calculations use published Australian tax rates and lending rules. Market figures come from the
RBA, ABS, APRA, ATO and Cotality, with dates and sources on the **Market Snapshot** page.

For free, independent guidance, see [Moneysmart](https://moneysmart.gov.au/home-loans), run by
ASIC. To find a licensed adviser, see
[Moneysmart: choosing a financial adviser](https://moneysmart.gov.au/financial-advice/choosing-a-financial-adviser).
"""
)

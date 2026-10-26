"""Learn the Basics page: short, plain-English explainers with official sources."""

import streamlit as st

from ui.components import get_snapshot, md_safe

snapshot = get_snapshot()
buffer = snapshot.get("apra_buffer")
fhb_exempt = snapshot.get("nsw_fhbas_exempt_limit")
fhb_concession = snapshot.get("nsw_fhbas_concession_limit")
cap_sydney = snapshot.get("scheme_cap_sydney")
cap_rest = snapshot.get("scheme_cap_rest_nsw")

st.title("Learn the Basics")
st.write("Short explanations of the terms the calculator uses. Each one links to an official source.")

with st.expander("What is the cash rate and how does it affect my mortgage?", icon=":material/percent:"):
    st.markdown(
        """
The **cash rate** is the interest rate banks charge each other for overnight loans. The Reserve
Bank of Australia (RBA) sets a target for it to keep inflation under control.

When the cash rate goes up, it costs lenders more to fund loans, so they usually raise their
**variable** home loan rates soon after. Your repayments then go up. Lenders don't always pass on
the full change, or do it straight away. A **fixed** rate doesn't change until its fixed period ends.

**Sources:** [RBA: cash rate target overview](https://www.rba.gov.au/cash-rate-target-overview.html) ·
[RBA: how monetary policy works](https://www.rba.gov.au/education/resources/explainers/the-transmission-of-monetary-policy.html)
"""
    )

with st.expander("What is the serviceability buffer and why do banks test at a higher rate?", icon=":material/shield:"):
    st.markdown(
        f"""
When you apply for a loan, lenders check that you could still afford the repayments if your
interest rate were **{buffer.value:g} percentage points higher** than the rate you'll actually pay.
This is the **serviceability buffer**, set by the Australian Prudential Regulation Authority (APRA).

It protects you and the lender if rates rise or your circumstances change. It's also why your
borrowing power is usually lower than the loan you could afford at today's rate. A 6% loan is
tested as if it were {6 + buffer.value:g}%.

**Source:** [APRA, {buffer.as_at}]({buffer.url})
"""
    )

with st.expander("What is LVR and lenders mortgage insurance (LMI)?", icon=":material/pie_chart:"):
    st.markdown(
        """
**LVR (loan-to-value ratio)** is how much you borrow compared with the property's value. A \\$600,000
loan on a \\$750,000 home is an LVR of 80%. The bigger your deposit, the lower your LVR.

If your LVR is **above 80%**, lenders usually charge **lenders mortgage insurance (LMI)**. It's a
one-off cost, often added to the loan. It protects the **lender**, not you, if you can't repay.
Some government schemes let eligible buyers with a smaller deposit avoid LMI.

**Sources:** [Moneysmart: LVR](https://moneysmart.gov.au/glossary/loan-to-value-ratio-lvr) ·
[Moneysmart: LMI](https://moneysmart.gov.au/glossary/lenders-mortgage-insurance-lmi)
"""
    )

with st.expander('What is "mortgage stress" and why the 30% rule is only a rule of thumb', icon=":material/warning:"):
    st.markdown(
        """
A household is often described as being in **mortgage stress** when repayments take more than
**30% of gross (before-tax) income**. Over 40% is sometimes called severe stress.

It's a quick check, not a rule lenders use, and it can mislead:
- It ignores **living costs**. A family with three children and a single person on the same income
  have very different budgets.
- It ignores **other debts** like car loans and credit cards.
- It uses **gross** income, but you pay your mortgage from take-home pay after tax and HECS/HELP.
- On a high income, 35% might be comfortable. On a low income, 25% might be a struggle.

That's why the calculator also shows how much you'd **actually have left** each month.

**Source:** [Moneysmart: problems paying your mortgage](https://moneysmart.gov.au/home-loans/problems-paying-your-mortgage)
"""
    )

with st.expander("How HECS/HELP affects take-home pay and borrowing", icon=":material/school:"):
    st.markdown(
        """
Once your income is above the **minimum repayment threshold**, a compulsory HECS/HELP repayment is
taken from your pay through the tax system. Since 2025-26 it's charged only on income **above** the
threshold, rather than on your whole income.

That lowers your **take-home pay**. Lenders also count it as a regular expense when working out
how much you can borrow. Paying off a HELP debt can lift your borrowing power.

**Source:** [ATO: study and training loan repayment thresholds and rates](https://www.ato.gov.au/tax-rates-and-codes/study-and-training-support-loans-rates-and-repayment-thresholds)
"""
    )

with st.expander("Fixed vs variable rates", icon=":material/compare_arrows:"):
    st.markdown(
        """
- **Variable rate:** moves up and down when your lender changes it, often after a cash rate
  change. Usually more flexible, with extra repayments and offset or redraw accounts often allowed.
- **Fixed rate:** stays the same for a set period, usually 1 to 5 years, so repayments are
  predictable. You miss out if rates fall, and you may pay a break fee to leave early.
- **Split loan:** part fixed, part variable, to balance certainty and flexibility.

When a fixed period ends, the loan usually moves to the lender's variable rate, which may be
much higher. Plan for that.

**Source:** [Moneysmart: fixed vs variable home loan interest rates](https://moneysmart.gov.au/home-loans/fixed-vs-variable-home-loan-interest-rates)
"""
    )

with st.expander("Upfront costs: stamp duty, LMI and fees", icon=":material/payments:"):
    st.markdown(
        """
Your deposit isn't the only money you need on the day. Common upfront costs include:
- **Stamp duty:** a state or territory tax on buying property. The amount depends on where you buy,
  the price and your circumstances. First home buyers may get a concession or exemption.
- **LMI:** if your LVR is above 80% (see above).
- **Legal or conveyancing fees**, **building and pest inspections**, and **lender fees**
  such as application or settlement fees.
- **Moving costs**, insurance and council or water rates adjustments.

These can add tens of thousands of dollars. The Calculator works them out for NSW in
"4. Upfront costs & savings"; other states are coming later.

**Source:** [Moneysmart: buying a house](https://moneysmart.gov.au/home-loans/buying-a-house)
"""
    )

with st.expander("NSW stamp duty concessions for first home buyers", icon=":material/key:"):
    st.markdown(
        md_safe(
            f"""
Under the **First Home Buyers Assistance Scheme**, eligible first home buyers of a home in NSW pay:
- **no stamp duty** if the price is **${fhb_exempt.value:,.0f} or less**
- **reduced stamp duty** between ${fhb_exempt.value:,.0f} and ${fhb_concession.value:,.0f}. The saving
  shrinks steadily as the price rises.
- **full stamp duty** from ${fhb_concession.value:,.0f}

You must never have owned residential property in Australia, and you need to move in within 12 months
and live there for at least 12 months in a row. Thresholds are as at {fhb_exempt.as_at}.

**Source:** [Revenue NSW: First Home Buyers Assistance Scheme]({fhb_exempt.url})
"""
        )
    )

with st.expander("How much does LMI cost?", icon=":material/shield_person:"):
    st.markdown(
        """
Lenders mortgage insurance (LMI) is usually charged when you borrow more than 80% of the property's
value. It's priced as a percentage of the loan, and that percentage jumps as your LVR rises: borrowing
95% can cost several times more than borrowing 85%.

**No insurer or regulator publishes LMI prices.** Each lender gets its own rates from its insurer. The
Calculator uses an **indicative estimate** from a broker-published table; your lender can give you
an exact quote. Remember, LMI protects the lender, not you.

**Sources:** [Moneysmart: lenders mortgage insurance](https://moneysmart.gov.au/glossary/lenders-mortgage-insurance-lmi) ·
[Moneysmart: save for a house deposit](https://moneysmart.gov.au/saving/save-for-a-house-deposit)
"""
    )

with st.expander("The Australian Government 5% Deposit Scheme", icon=":material/account_balance:"):
    st.markdown(
        md_safe(
            f"""
Eligible first home buyers can buy with a **5% deposit** (single parents or legal guardians: **2%**)
and **pay no LMI**. The government guarantees part of the loan instead. You apply through a
participating lender.

The property price must be under a cap for its location. In NSW that's:
- **${cap_sydney.value:,.0f}** in Sydney and NSW regional centres (Central Coast, Coffs Harbour–Grafton,
  Illawarra, Mid North Coast, Richmond–Tweed, Newcastle and Lake Macquarie)
- **${cap_rest.value:,.0f}** in the rest of NSW

A smaller deposit means a bigger loan and higher repayments, so check the Calculator's repayments and
stress test too.

**Source:** [Housing Australia: 5% Deposit Scheme property price caps]({cap_sydney.url})
"""
        )
    )

with st.expander("What is a Monte Carlo simulation?", icon=":material/casino:"):
    st.markdown(
        """
A **Monte Carlo simulation** answers "what are the chances?" by playing out thousands of possible futures
instead of one guess.

The Risk Simulator builds each future from **real Australian history**: it picks random 12-month stretches of
past cash rate changes, inflation and wage growth and joins them together. Keeping each stretch's months together
keeps their real relationships, like rate rises tending to come with high inflation. Then it runs your budget
through every future and counts how often things go wrong, e.g. "savings run out in 1 in 8 futures".

It shows a **range of outcomes and how likely they are**, not a prediction. The future can always do something
history hasn't.

**Sources for the data:** [RBA: cash rate decisions](https://www.rba.gov.au/statistics/cash-rate/) ·
[ABS: Consumer Price Index](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release) ·
[ABS: Wage Price Index](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/wage-price-index-australia/latest-release)
"""
    )

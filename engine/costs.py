"""Upfront costs of buying a home: transfer (stamp) duty, LMI, the 5% Deposit Scheme and fees.

NSW only for now. Other states are listed so they can be added later.
Not included: foreign purchaser surcharge duty, and stamp duty on the LMI premium.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
# Official duty calculators, so users in other states know where to go.
STATES = {
    "NSW": {"supported": True, "calculator": "https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty/understanding-transfer-duty/calculate-transfer-duty"},
    "VIC": {"supported": False, "calculator": "https://www.sro.vic.gov.au/buying-property/land-transfer-stamp-duty/land-transfer-stamp-duty-calculator"},
    "QLD": {"supported": False, "calculator": "https://qro.qld.gov.au/duties/transfer-duty/calculate/"},
    "WA": {"supported": False, "calculator": "https://www.wa.gov.au/organisation/department-of-finance/transfer-duty-assessment"},
    "SA": {"supported": False, "calculator": "https://www.revenuesa.sa.gov.au/stamp-duty-land/calculate-stamp-duty"},
    "TAS": {"supported": False, "calculator": "https://www.sro.tas.gov.au/property-transfer-duties"},
    "ACT": {"supported": False, "calculator": "https://www.revenue.act.gov.au/duties/conveyance-duty"},
    "NT": {"supported": False, "calculator": "https://treasury.nt.gov.au/dtf/territory-revenue-office/stamp-duty"},
}

# ---------------------------------------------------------------------------
# NSW transfer duty, 1 July 2026 to 30 June 2027
# Source: Revenue NSW, "How to calculate transfer duty". Thresholds are CPI-indexed each 1 July.
# Each tuple is (threshold, base duty at threshold, rate per $100 above threshold).
# ---------------------------------------------------------------------------
NSW_DUTY_YEAR = "2026-27"
NSW_DUTY_BRACKETS = (
    (0, 0, 1.25),
    (18_000, 225, 1.50),
    (38_000, 525, 1.75),
    (103_000, 1_662, 3.50),
    (387_000, 11_602, 4.50),
    (1_290_000, 52_237, 5.50),
)
NSW_MINIMUM_DUTY = 20
# Premium property duty (residential), Revenue NSW 2026-27
NSW_PREMIUM_THRESHOLD = 3_870_000
NSW_PREMIUM_BASE = 194_137
NSW_PREMIUM_RATE = 7.00

# First Home Buyers Assistance Scheme (homes), Revenue NSW, contracts from 1 July 2023.
# Full exemption up to $800,000; concessional duty above that and below $1,000,000.
FHBAS_EXEMPT_LIMIT = 800_000
FHBAS_CONCESSION_LIMIT = 1_000_000

# ---------------------------------------------------------------------------
# Australian Government 5% Deposit Scheme (Housing Australia, firsthomebuyers.gov.au, 2026-27)
# NSW regional centres: Central Coast, Coffs Harbour-Grafton, Illawarra, Mid North Coast,
# Richmond-Tweed, Newcastle and Lake Macquarie.
# ---------------------------------------------------------------------------
SCHEME_PRICE_CAPS = {
    "Sydney or NSW regional centre": 1_500_000,
    "Rest of NSW": 800_000,
}
SCHEME_MIN_DEPOSIT = 0.05
SCHEME_MIN_DEPOSIT_SINGLE_PARENT = 0.02

# ---------------------------------------------------------------------------
# Lenders mortgage insurance: INDICATIVE ONLY.
# No insurer or regulator publishes premiums. Rates are % of the loan from a broker-published
# table (Home Loan Experts, "LMI rates", updated 18 May 2026, one lender, full-doc loans).
# For each 5% LVR band we use the table's middle row (82-83%, 87-88%, 92-93%).
# Loans over $1M use the $750k-$1M column, the largest the table covers.
# ---------------------------------------------------------------------------
LMI_FREE_LVR = 80.0
LMI_MAX_LVR = 95.0
LMI_LOAN_BANDS = (300_000, 500_000, 600_000, 750_000, float("inf"))  # upper limit of each column
LMI_RATES = {  # upper LVR of band -> % of loan for each loan-size column
    85.0: (0.596, 0.699, 0.932, 1.090, 1.109),
    90.0: (1.062, 1.305, 1.463, 1.631, 1.752),
    95.0: (2.330, 3.028, 3.802, 4.081, 4.156),
}

# ---------------------------------------------------------------------------
# Other upfront costs
# ---------------------------------------------------------------------------
# NSW Land Registry Services fees from 1 July 2026, incl. GST (NSW LRS 2026/27 Fees Update)
NSW_LRS_TRANSFER_FEE = 182.73
NSW_LRS_MORTGAGE_FEE = 182.73

DEFAULT_OTHER_COSTS = {
    "Conveyancing / legal": 2_000,          # PLACEHOLDER estimate
    "Building & pest inspection": 600,      # PLACEHOLDER estimate
    "Land Registry: transfer fee": NSW_LRS_TRANSFER_FEE,
    "Land Registry: mortgage registration": NSW_LRS_MORTGAGE_FEE,
    "Lender application / establishment": 600,  # PLACEHOLDER estimate
    "Moving costs": 1_500,                  # PLACEHOLDER estimate
}


def nsw_transfer_duty(value: float) -> float:
    """General NSW transfer duty on a dutiable value, including premium property duty."""
    if value <= 0:
        return 0.0
    if value > NSW_PREMIUM_THRESHOLD:
        return NSW_PREMIUM_BASE + (value - NSW_PREMIUM_THRESHOLD) * NSW_PREMIUM_RATE / 100
    for threshold, base, rate in reversed(NSW_DUTY_BRACKETS):
        if value > threshold:
            return max(NSW_MINIMUM_DUTY, base + (value - threshold) * rate / 100)
    return 0.0


def nsw_first_home_duty(value: float) -> float:
    """Duty for an eligible first home buyer of a home under the FHBAS.

    $0 up to $800,000. Between $800,000 and $1,000,000 the concession phases out in a
    straight line, from $0 to the full duty at $1,000,000 (this matches every example in
    the official 2026-27 table). Full duty from $1,000,000.
    """
    if value <= FHBAS_EXEMPT_LIMIT:
        return 0.0
    if value < FHBAS_CONCESSION_LIMIT:
        share = (value - FHBAS_EXEMPT_LIMIT) / (FHBAS_CONCESSION_LIMIT - FHBAS_EXEMPT_LIMIT)
        return nsw_transfer_duty(FHBAS_CONCESSION_LIMIT) * share
    return nsw_transfer_duty(value)


def transfer_duty(state: str, value: float, first_home_buyer: bool = False) -> float:
    """Transfer duty for a supported state. Raises NotImplementedError for other states."""
    if not STATES.get(state, {}).get("supported"):
        raise NotImplementedError(f"Transfer duty for {state} is not supported yet")
    return nsw_first_home_duty(value) if first_home_buyer else nsw_transfer_duty(value)


def lmi_premium(loan: float, lvr: float) -> float | None:
    """Indicative LMI premium. $0 at or below 80% LVR; None above 95% (not insurable)."""
    if loan <= 0 or lvr <= LMI_FREE_LVR:
        return 0.0
    if lvr > LMI_MAX_LVR:
        return None
    band = next(upper for upper in LMI_RATES if lvr <= upper)
    column = next(i for i, limit in enumerate(LMI_LOAN_BANDS) if loan <= limit)
    return loan * LMI_RATES[band][column] / 100


@dataclass(frozen=True)
class SchemeCheck:
    """Whether the 5% Deposit Scheme can be used for this purchase, and why."""

    applies: bool
    min_deposit: float
    message: str


def deposit_scheme_check(price: float, deposit: float, location: str, single_parent: bool) -> SchemeCheck:
    """Check the price cap and minimum deposit for the 5% Deposit Scheme."""
    cap = SCHEME_PRICE_CAPS[location]
    min_share = SCHEME_MIN_DEPOSIT_SINGLE_PARENT if single_parent else SCHEME_MIN_DEPOSIT
    min_deposit = price * min_share
    if price > cap:
        return SchemeCheck(False, min_deposit, f"The price is above the ${cap:,.0f} cap for {location}, so the scheme won't apply.")
    if deposit < min_deposit:
        return SchemeCheck(False, min_deposit, f"The scheme needs a deposit of at least {min_share:.0%} (${min_deposit:,.0f}).")
    return SchemeCheck(True, min_deposit, f"The scheme applies: no LMI, with at least a {min_share:.0%} deposit.")


@dataclass(frozen=True)
class PurchaseSummary:
    """Everything about the cash needed to buy."""

    price: float
    deposit: float
    duty: float | None         # None means duty for this state isn't supported yet
    lmi: float | None          # None means the LVR is too high to insure
    lmi_capitalised: bool
    other_costs: float
    upfront_costs: float       # duty + other costs (+ LMI if paid upfront)
    loan: float                # price - deposit (+ LMI if added to the loan)
    lvr: float                 # loan / price, as a percentage
    savings: float
    savings_left: float        # starting buffer after settlement; negative means a shortfall
    scheme: SchemeCheck | None = None
    other_cost_items: dict = field(default_factory=dict)

    @property
    def shortfall(self) -> float:
        return max(0.0, -self.savings_left)


def purchase_summary(
    price: float,
    deposit: float,
    savings: float,
    state: str = "NSW",
    first_home_buyer: bool = False,
    use_scheme: bool = False,
    scheme_location: str = "Sydney or NSW regional centre",
    single_parent: bool = False,
    capitalise_lmi: bool = True,
    other_costs: dict | None = None,
) -> PurchaseSummary:
    """Work out duty, LMI, fees, the loan and the savings left after buying."""
    other_costs = DEFAULT_OTHER_COSTS if other_costs is None else other_costs
    deposit = min(deposit, price)
    base_loan = price - deposit
    base_lvr = base_loan / price * 100 if price > 0 else 0.0

    supported = STATES.get(state, {}).get("supported", False)
    duty = transfer_duty(state, price, first_home_buyer) if supported else None
    scheme = deposit_scheme_check(price, deposit, scheme_location, single_parent) if use_scheme else None
    lmi = 0.0 if scheme and scheme.applies else lmi_premium(base_loan, base_lvr)

    fees = sum(other_costs.values())
    lmi_cash = 0.0 if (lmi is None or capitalise_lmi) else lmi
    loan = base_loan + (lmi if (lmi and capitalise_lmi) else 0.0)
    upfront = (duty or 0.0) + fees + lmi_cash

    return PurchaseSummary(
        price=price,
        deposit=deposit,
        duty=duty,
        lmi=lmi,
        lmi_capitalised=capitalise_lmi,
        other_costs=fees,
        upfront_costs=upfront,
        loan=loan,
        lvr=loan / price * 100 if price > 0 else 0.0,
        savings=savings,
        savings_left=savings - deposit - upfront,
        scheme=scheme,
        other_cost_items=dict(other_costs),
    )

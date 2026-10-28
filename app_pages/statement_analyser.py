"""Statement Analyser page: read 3 months of transactions, review them, and use the figures in the Calculator.

Privacy (see CLAUDE.md): statement data lives only in the st.session_state["statement"] namespace
and "stmtw_" widgets, in memory, and is wiped by ui/session_guard.py after inactivity or on request.
Nothing here caches, saves or sends it anywhere. All maths comes from engine/statements/.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.budget import living_costs
from engine.runtime import IS_BROWSER
from engine.statements.analyse import (
    estimate_gross,
    household_income_split,
    lender_flags,
    monthly_cash_flow,
    payer_name,
    summarise,
    to_calculator_inputs,
)
from engine.statements.categorise import LOW, categorise, category_groups, load_rules
from engine.statements.parse import (
    ColumnMapping,
    NeedsColumnMapping,
    ScannedPdfError,
    combine,
    coverage_warning,
    parse_csv,
    parse_file,
    statement_balances,
)
from ui import session_guard as guard
from ui.calculator_state import effective_inputs
from ui.charts import TEMPLATE, TEAL, CORAL
from ui.components import md_safe, money, what_this_means
from ui.privacy import UPLOAD_DISABLED_NOTE, VERIFY_STEPS, clear_statement_data, upload_notice, uploads_allowed
from ui.session_guard import UPLOADER_VERSION, WIDGET_PREFIX

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
# key: (name, description, icon, sample PDF file)
PERSONAS = {
    "alex": ("Alex", "Single renter on about \\$85k, paid fortnightly. HECS/HELP, buy now pay later, subscriptions.",
             ":material/person:", "alex.pdf"),
    "sam_jordan": ("Sam & Jordan", "Couple on about \\$110k and \\$75k. Childcare, a car loan, credit card and insurance.",
                   ":material/group:", "sam_jordan.pdf"),
    "riley": ("Riley", "Casual and gig work with irregular pay. Higher spending, a dishonour fee and some betting.",
              ":material/directions_car:", "riley.pdf"),
    "jamie": ("Jamie", "Single professional on about \\$140k, paid monthly, saving regularly. A steady budget.",
              ":material/savings:", "sample_jamie_statement.pdf"),
}
CATEGORIES = [rule.name for rule in load_rules()]
GROUPS = category_groups()
NOT_SPENDING = {"income", "transfer"}


def fresh_namespace() -> dict:
    """Start a new statement session, wiping any previous statement data first."""
    if guard.has_data():
        guard.wipe(reason="replaced")
    return guard.start()


def store(frame: pd.DataFrame, source: str, warnings: list[str]) -> None:
    """Keep the categorised transactions in the statement namespace (memory only) for this tab."""
    ns = fresh_namespace()
    ns.update(frame=categorise(frame), source=source, warnings=warnings, editor_version=0)


def load_sample(key: str) -> None:
    filename = PERSONAS[key][3]
    store(parse_file(filename, (SAMPLES / filename).read_bytes()), f"sample:{key}", [])


def analyse_uploads(files) -> None:
    """Parse uploaded files from memory. Unreadable files produce friendly messages, not errors."""
    frames, warnings, pending = [], [], None
    for file in files:
        data = file.getvalue()   # in-memory bytes; never written to disk
        try:
            frames.append(parse_file(file.name, data))
        except ScannedPdfError:
            warnings.append(f"**{file.name}** looks like a scanned PDF with no readable text. Try downloading a CSV "
                            "export from your online banking instead.")
        except NeedsColumnMapping as needs:
            pending = (file.name, data, needs.columns, needs.preview)
    if frames:
        store(combine(frames), "upload", warnings)
    else:
        ns = fresh_namespace()
        ns["warnings"] = warnings
    if pending:
        guard.namespace()["pending_mapping"] = pending


def apply_editor_changes(view_index: list) -> None:
    """Copy edits from the review table back into the stored transactions."""
    ns = guard.namespace()
    frame = ns["frame"]
    key = f"{WIDGET_PREFIX}editor_{ns['editor_version']}"
    for position, changes in st.session_state[key]["edited_rows"].items():
        row = view_index[int(position)]
        if "Category" in changes:
            frame.loc[row, "category"] = changes["Category"]
            frame.loc[row, "confidence"] = "high"   # the user decided, so it no longer needs checking
        if "Include" in changes:
            frame.loc[row, "include"] = bool(changes["Include"])
    del st.session_state[key]   # the old editor's copy of the edits isn't needed any more
    ns["editor_version"] += 1


st.title("Statement Analyser")
st.write(
    "Skip the long form: give the app 3 months of bank transactions and it works out your income, spending and "
    "debts. You review everything before it's used."
)

# ---------------- Step 1: choose ----------------
st.subheader("1. Choose your statements")
cols = st.columns(2)
for i, (key, (name, description, icon, _)) in enumerate(PERSONAS.items()):
    column = cols[i % 2]
    with column.container(border=True):
        st.markdown(f"{icon} **{name}**")
        st.caption(description)
        if st.button("Try this sample", key=f"sample_{key}", width="stretch"):
            load_sample(key)
            st.rerun()   # redraw from the top so the status chip appears straight away
st.caption("Samples are synthetic statements from the fictional \"Sample Bank\": invented people, made-up transactions.")

if uploads_allowed():
    with st.container(border=True):
        st.markdown("**Or upload your own statements** (CSV or text-based PDF, ideally 3 months)")
        st.info(upload_notice(), icon=":material/lock:")
        if IS_BROWSER:
            with st.expander("How to verify this yourself", icon=":material/policy:"):
                st.markdown(VERIFY_STEPS)
        files = st.file_uploader(
            "Statement files", type=["csv", "pdf"], accept_multiple_files=True,
            key=f"{WIDGET_PREFIX}upload_{st.session_state.get(UPLOADER_VERSION, 0)}", label_visibility="collapsed",
        )
        if files and st.button("Analyse these files", type="primary", icon=":material/search:"):
            analyse_uploads(files)
            st.rerun()
else:
    st.info(UPLOAD_DISABLED_NOTE, icon=":material/lock:")

st.page_link("app_pages/calculator.py", label="Prefer to type it in? Use the calculator", icon=":material/calculate:")

ns = guard.namespace() or {}

# Column mapping for a CSV whose layout wasn't recognised
pending = ns.get("pending_mapping")
if pending:
    name, data, columns, preview = pending
    with st.form(f"{WIDGET_PREFIX}mapping"):
        st.markdown(f"**We couldn't recognise the columns in {name}.** Tell us which is which:")
        st.dataframe(pd.DataFrame(preview, columns=columns[:len(preview[0])] if preview else columns), hide_index=True)
        c1, c2 = st.columns(2)
        date_col = c1.selectbox("Date", columns)
        desc_col = c2.selectbox("Description", columns, index=min(1, len(columns) - 1))
        c3, c4 = st.columns(2)
        amount_col = c3.selectbox("Amount (money in +, money out −)", columns, index=min(2, len(columns) - 1))
        balance_col = c4.selectbox("Balance (optional)", ["(none)", *columns])
        if st.form_submit_button("Read the file"):
            mapping = ColumnMapping(date_col, desc_col, amount=amount_col,
                                    balance=None if balance_col == "(none)" else balance_col)
            try:
                store(parse_csv(data, mapping), "upload", ns.get("warnings", []))
                st.rerun()
            except NeedsColumnMapping:
                st.error("That still didn't work: check the date column contains dates.")

for warning in ns.get("warnings", []):
    st.warning(warning, icon=":material/warning:")

frame = ns.get("frame")
if frame is None:
    with st.expander("How we read your statements", icon=":material/help:"):
        st.markdown(
            "We read the transaction rows only, remove account numbers, BSBs, card numbers, names and reference "
            "numbers, then sort each transaction into a category using keyword rules. Everything happens in this "
            "browser session and is never stored."
        )
    st.stop()

# ---------------- Step 2: summary ----------------
summary = summarise(frame)
source = ns.get("source", "")
st.subheader("2. What we found")
label = f"sample statements for {PERSONAS[source.split(':')[1]][0]}" if source.startswith("sample:") else "your statements"
st.caption(
    f"From {label}: {summary.start:%d %b %Y} to {summary.end:%d %b %Y} ({summary.days} days), "
    f"{summary.transactions} transactions."
)
if balances := statement_balances(frame):
    st.caption(md_safe(f"Opening balance {money(balances[0])} · closing balance {money(balances[1])}."))
if warning := coverage_warning(frame):
    st.warning(warning, icon=":material/schedule:")

c1, c2, c3 = st.columns(3)
c1.metric("Income (take-home)", money(summary.monthly_income) + "/mo", border=True)
c2.metric("Rent / mortgage", money(summary.housing) + "/mo", border=True)
c3.metric("Essential living costs", money(summary.essentials) + "/mo", border=True)
c4, c5, c6 = st.columns(3)
c4.metric("Discretionary spending", money(summary.discretionary) + "/mo", border=True)
c5.metric("Debt repayments", money(summary.debt_total) + "/mo", border=True)
c6.metric("Money left over", money(summary.left_over) + "/mo", border=True)

if summary.income_sources:
    lines = []
    for s in summary.income_sources:
        how = f"{s.frequency}, about {money(s.typical_amount)} each time" if s.regular else f"irregular, {s.payments} payments"
        lines.append(f"- **{payer_name(s)}**: {money(s.monthly_net)}/month ({how})")
    st.markdown(md_safe("**Income found**\n" + "\n".join(lines)))
if summary.transfers_excluded:
    st.caption(md_safe(f"{money(summary.transfers_excluded)}/month of transfers between your own accounts was left out."))

# ---------------- Step 3: review ----------------
st.subheader("3. Review the categories")
st.write("Check anything marked ⚠. Change a category, or untick **Include** to leave a transaction out. Totals update as you go.")
to_check = int((frame["confidence"] == LOW).sum())
show = st.selectbox(
    "Show", ["All transactions", f"Only items to check ({to_check})", *sorted(frame["category"].unique())],
    key=f"{WIDGET_PREFIX}filter",
)
if show.startswith("Only items"):
    view = frame[frame["confidence"] == LOW]
elif show == "All transactions":
    view = frame
else:
    view = frame[frame["category"] == show]
view = view.sort_values(["category", "date"], kind="stable")
table = pd.DataFrame({
    "Check": view["confidence"].map(lambda c: "⚠" if c == LOW else ""),
    "Date": view["date"].dt.date,
    "Description": view["description"],
    "Amount": view["amount"],
    "Category": view["category"],
    "Include": view["include"],
})
st.data_editor(
    table,
    key=f"{WIDGET_PREFIX}editor_{ns['editor_version']}",
    hide_index=True,
    width="stretch",
    height=380,
    disabled=["Check", "Date", "Description", "Amount"],
    column_config={
        "Check": st.column_config.TextColumn(width="small", help="⚠ = we're not sure about this one"),
        "Amount": st.column_config.NumberColumn(format="$%.2f"),
        "Category": st.column_config.SelectboxColumn(options=CATEGORIES, required=True, width="medium"),
        "Include": st.column_config.CheckboxColumn(help="Untick to leave this transaction out"),
    },
    on_change=apply_editor_changes,
    args=(list(view.index),),
)

# ---------------- Step 4: charts ----------------
st.subheader("4. Where the money goes")
spend = {c: v for c, v in summary.by_category.items() if GROUPS.get(c) not in NOT_SPENDING}
tab_spend, tab_flow = st.tabs(["Spending by category", "Money in vs out"])
with tab_spend:
    ordered = sorted(spend.items(), key=lambda kv: kv[1])
    fig = go.Figure(go.Bar(
        x=[v for _, v in ordered], y=[c for c, _ in ordered], orientation="h", marker_color=TEAL,
        text=[money(v) for _, v in ordered], textposition="outside",
        hovertemplate="%{y}: $%{x:,.0f} a month<extra></extra>",
    ))
    largest = max((v for _, v in ordered), default=0)
    fig.update_layout(template=TEMPLATE, title=dict(text="Average per month", y=0.99, yanchor="top"),
                      xaxis_tickformat="$,.0f", xaxis_range=[0, largest * 1.3 or 1],   # room for the $ labels
                      height=max(320, 28 * len(ordered) + 100), margin=dict(t=60))
    st.plotly_chart(fig, width="stretch")
with tab_flow:
    flow = monthly_cash_flow(frame)
    fig = go.Figure([
        go.Bar(name="Money in", x=flow.index, y=flow["money_in"], marker_color=TEAL),
        go.Bar(name="Money out", x=flow.index, y=flow["money_out"], marker_color=CORAL),
    ])
    fig.update_layout(template=TEMPLATE, barmode="group", title="Each calendar month (transfers excluded)",
                      yaxis_tickformat="$,.0f", xaxis_type="category", height=360)
    st.plotly_chart(fig, width="stretch")

# ---------------- Step 5: lender view ----------------
st.subheader("5. What a lender may look at")
st.caption("General information about what lenders commonly ask about. This is not a credit assessment and doesn't "
           "reflect any particular lender's rules.")
flags = lender_flags(frame, summary)
if not flags:
    st.success("Nothing in these statements stands out from the things lenders commonly ask about.")
for flag in flags:
    with st.container(border=True):
        st.markdown(md_safe(f"**{flag.title}**: {flag.detail}"))
        st.caption(flag.explanation)

# ---------------- Step 6: confirm ----------------
st.subheader("6. Use these numbers")
split = household_income_split(summary)
regular = summary.regular_earners
if len(regular) > 2:
    st.caption("More than two regular payers were found; the two largest are treated as the earners.")
st.write("Gross (before-tax) income is estimated from take-home pay using 2026-27 tax rules. Check it and adjust if needed.")
grosses, helps = [], []
for i, monthly_net in enumerate(split[:2]):
    who = payer_name(regular[i]) if i < len(regular) else "All income (irregular)"
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 2], vertical_alignment="bottom")
        c1.metric(f"Earner {i + 1}: {who} (take-home)", money(monthly_net) + "/mo")
        has_help = c2.checkbox("Has HECS/HELP", key=f"{WIDGET_PREFIX}help_{i}",
                               help="HELP repayments come out of pay before it reaches your account, so we can't see them.")
        gross = c3.number_input("Estimated gross income ($/year)", min_value=0, step=1_000,
                                value=int(round(estimate_gross(monthly_net, has_help))),
                                key=f"{WIDGET_PREFIX}gross_{i}_{has_help}")
        grosses.append(gross)
        helps.append(has_help)

if st.button("Use these numbers", type="primary", icon=":material/check:"):
    # The figures stay inside the statement namespace, so they're wiped with it
    ns["prefill"] = to_calculator_inputs(summary, grosses, helps)
    inputs = effective_inputs()
    # Tell the Calculator these are deliberate figures, so its lifestyle preset doesn't overwrite them
    st.session_state["calc_last_suggested"] = living_costs(inputs["preset"], inputs["borrowers"], inputs["dependants"])

if ns.get("prefill"):
    st.success(
        md_safe(f"Done. The Calculator now uses {len(grosses)} earner(s), living costs of "
                f"{money(summary.essentials + summary.discretionary)}/month (rent excluded) and debts of "
                f"{money(summary.debt_total)}/month."),
        icon=":material/check_circle:",
    )
    c1, c2, c3 = st.columns(3)
    c1.page_link("app_pages/calculator.py", label="Open the Calculator", icon=":material/calculate:")
    c2.page_link("app_pages/stress_scenarios.py", label="Stress Scenarios", icon=":material/thunderstorm:")
    c3.page_link("app_pages/risk_simulator.py", label="Risk Simulator", icon=":material/casino:")

what_this_means(
    "these are averages from a short period. Check that big yearly costs (car registration, insurance renewals, "
    "holidays) are included, since 3 months of statements can miss them."
)

if st.button("Clear my data", key=f"{WIDGET_PREFIX}clear_page", icon=":material/delete:",
             help="Removes every statement figure from this session straight away"):
    clear_statement_data()
    st.rerun()

with st.expander("How we read your statements", icon=":material/help:"):
    st.markdown(
        f"""
1. **Read**: only the transaction rows are read. Headers with names, addresses and account details are skipped.
2. **Remove private details**: account numbers, BSBs, card numbers, personal names and reference numbers are
   removed from descriptions as soon as a file is read.
3. **Categorise**: each transaction is matched against keyword rules (`data/categories.yaml`). Known merchants are
   matched first, then general words. Anything we can't match is marked ⚠ for you to check.
4. **Find patterns**: payments from the same payer at regular gaps are treated as pay, and moves between your own
   accounts are left out of income and spending.
5. **Work out monthly figures**: regular payments use their amount and frequency; everything else is averaged
   over the period.

**Limitations**
- Keyword rules can be wrong, so review the table before using the numbers.
- 3 months can miss annual or occasional costs.
- Credit card spending only shows as the card repayment, not what was bought.
- This is not a credit assessment.

**Privacy**: processed in memory on the computer running the app. Nothing is saved, logged or sent anywhere.
Everything is deleted after {guard.timeout_text()} of inactivity (a check runs every 15 seconds, even if you've walked away),
when you click **Clear my data**, or within about a minute of closing the tab. Deleting releases the memory;
like any program, Python can't promise the old bytes are overwritten straight away.
"""
    )
st.caption(f"Statement data is held only in this browser session and is deleted after {guard.timeout_text()} of "
           "inactivity or when you close the tab.")

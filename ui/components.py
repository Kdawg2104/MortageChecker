"""Reusable display pieces shared by every page."""

import base64
from html import escape
from pathlib import Path

import streamlit as st

from engine.market import MarketFigure, MarketSnapshot, load_snapshot
from ui.disclaimer import FULL_DISCLAIMER, SHORT_DISCLAIMER

ROOT = Path(__file__).resolve().parent.parent
STYLE_PATH = ROOT / "assets" / "style.css"
HERO_IMAGE_PATH = ROOT / "assets" / "hero.jpg"
ABOUT_PAGE = "app_pages/about.py"


def money(value: float) -> str:
    """Format a number as whole dollars, e.g. -$1,234."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def md_safe(text: str) -> str:
    """Escape $ for st.markdown, which otherwise treats text between two $ signs as maths."""
    return text.replace("$", r"\$")


def html_safe(text: str) -> str:
    """Escape text for HTML cards, including $ (see md_safe)."""
    return escape(text).replace("$", "&#36;")


def what_this_means(text: str) -> None:
    """The plain-English sentence shown under each calculator result."""
    st.markdown(f"**What this means:** {md_safe(text)}")


@st.cache_data
def get_snapshot() -> MarketSnapshot:
    """Market figures, read from disk once and then cached."""
    return load_snapshot()


def load_css() -> None:
    """Apply assets/style.css, the one place all custom styling lives."""
    st.markdown(f"<style>{STYLE_PATH.read_text()}</style>", unsafe_allow_html=True)


def format_value(figure: MarketFigure) -> str:
    """Display a figure's value with its unit, e.g. "4.60%" or "$899,236"."""
    if figure.unit == "%":
        return f"{figure.value:.{figure.decimals}f}%"
    if figure.unit.startswith("$"):
        suffix = figure.unit[1:].strip()
        return f"${figure.value:,.{figure.decimals}f}" + (f" {suffix}" if suffix else "")
    if figure.unit == "brackets":
        return f"{len(figure.value)} brackets"
    return f"{figure.value:g} {figure.unit}"


def figure_card(figure: MarketFigure, show_details: bool = True) -> None:
    """A card showing one market figure, its "as at" date and a source link."""
    details = ""
    if show_details:
        details = (
            f'<p class="mrc-card-notes">{html_safe(figure.notes)}</p>'
            f'<p class="mrc-card-source">Source: <a href="{escape(figure.url)}" target="_blank">'
            f"{html_safe(figure.source)}</a></p>"
        )
    st.markdown(
        f"""<div class="mrc-card">
<p class="mrc-card-label">{html_safe(figure.name)}</p>
<p class="mrc-card-value">{html_safe(format_value(figure))}</p>
<p class="mrc-card-date">As at {html_safe(figure.as_at)}</p>
{details}
</div>""",
        unsafe_allow_html=True,
    )


def info_card(title: str, body: str) -> None:
    """A simple text card with a heading."""
    st.markdown(
        f'<div class="mrc-card"><p class="mrc-card-title">{html_safe(title)}</p>'
        f'<p class="mrc-card-body">{html_safe(body)}</p></div>',
        unsafe_allow_html=True,
    )


@st.cache_data
def _hero_image_data_uri() -> str | None:
    """The hero photo as a data URI (Streamlit can't serve local files to CSS), or None."""
    if not HERO_IMAGE_PATH.exists():
        return None
    encoded = base64.b64encode(HERO_IMAGE_PATH.read_bytes()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def hero_container():
    """A full-width container styled as the hero (see .st-key-hero in style.css).

    If assets/hero.jpg exists it is passed to the stylesheet as a CSS variable;
    otherwise the stylesheet's plain gradient is used.
    """
    image = _hero_image_data_uri()
    if image:
        st.markdown(
            f"<style>.st-key-hero {{ --hero-image: url('{image}'); }}</style>",
            unsafe_allow_html=True,
        )
    return st.container(key="hero")


def disclaimer_box() -> None:
    """A visible box with the key disclaimer points."""
    st.markdown(
        '<div class="mrc-disclaimer"><strong>Important:</strong> this app gives general '
        "information only. It doesn't consider your objectives, financial situation or needs, "
        "and it isn't financial advice, credit advice or a loan approval. Results are estimates. "
        'Talk to a licensed professional and see <a href="https://moneysmart.gov.au" '
        'target="_blank">moneysmart.gov.au</a> before deciding.</div>',
        unsafe_allow_html=True,
    )
    # st.page_link switches page inside the app; a plain <a href> would reload it,
    # starting a new session (losing inputs and showing the disclaimer again).
    st.page_link(ABOUT_PAGE, label="Read the full disclaimer", icon=":material/info:")


def footer() -> None:
    """One-line disclaimer shown at the bottom of every page."""
    with st.container(key="footer"):
        st.caption(SHORT_DISCLAIMER)
        st.page_link(ABOUT_PAGE, label="See About & Disclaimer", icon=":material/info:")


@st.dialog("Before you start", width="medium", dismissible=False)
def disclaimer_dialog() -> None:
    """Full disclaimer shown once per visit; closes when the user accepts it."""
    for point in FULL_DISCLAIMER:
        st.markdown(f"- {point}")
    if st.button("I understand", type="primary", width="stretch"):
        st.session_state["disclaimer_accepted"] = True
        st.rerun()

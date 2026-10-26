"""The app's Plotly chart template, so charts match the Streamlit theme (.streamlit/config.toml)."""

import plotly.graph_objects as go
import plotly.io as pio

TEAL = "#0e7c7b"
NAVY = "#12324a"
GOLD = "#d9a21b"
CORAL = "#d64545"
COLOURS = [TEAL, NAVY, GOLD, "#e07b39", "#5b5fc7", "#3e9c5f", CORAL, "#8a94a6"]

pio.templates["mrc"] = go.layout.Template(
    layout=dict(
        font=dict(family="sans-serif", color="#1f2933", size=13),
        colorway=COLOURS,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#e3e8ee", zeroline=False, linecolor="#c9d2dc"),
        yaxis=dict(gridcolor="#e3e8ee", zeroline=False, linecolor="#c9d2dc"),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=50, b=10, l=10, r=10),
        hoverlabel=dict(font_family="sans-serif"),
    )
)
TEMPLATE = "plotly_white+mrc"

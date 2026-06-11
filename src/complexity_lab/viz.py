"""Shared visualization toolkit: lab plotly template, policy-event annotation,
choropleths and band charts.

Design rules (docs/blueprint §10): one accent colour for the primary signal,
muted neutrals elsewhere; whitespace over chrome; the most important number
biggest. Every time-series chart can overlay the policy events timeline so a
chart explains *why*, not just *what*.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

ACCENT = "#E4572E"        # primary signal
ACCENT_2 = "#17A398"      # secondary signal (use sparingly)
NEUTRALS = ["#33658A", "#86BBD8", "#758E4F", "#B8B8B8", "#5C5D8D", "#C49991",
            "#9DB4C0", "#A37871", "#6B705C", "#CB997E"]

LAB_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font={"family": "Segoe UI, system-ui, sans-serif", "size": 13},
        title={"x": 0.0, "xanchor": "left", "font": {"size": 17}},
        colorway=[ACCENT, *NEUTRALS],
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"gridcolor": "#EEEEEE", "zeroline": False},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
    )
)
pio.templates["lab"] = LAB_TEMPLATE
pio.templates.default = "plotly_white+lab"

EVENT_COLORS = {
    "policy": "#33658A",
    "regulation": "#33658A",
    "demand_shock": "#A4243B",
    "supply_shock": "#A4243B",
    "data_break": "#999999",
    "fuel": "#758E4F",
}


def load_events(con, tiers: tuple[int, ...] = (1,)) -> pd.DataFrame:
    """Policy/structural events from the DB, ready for chart annotation."""
    df = con.execute("SELECT * FROM events").df()
    if "tier" in df.columns and tiers:
        df = df[df["tier"].isin(tiers)]
    df["event_date"] = pd.to_datetime(df["date"], format="%Y-%m", errors="coerce")
    return df.dropna(subset=["event_date"])


def add_event_markers(fig: go.Figure, events: pd.DataFrame, max_labels: int = 10) -> go.Figure:
    """Overlay vertical dashed lines + hover labels for events on a time-series fig."""
    shown = events.sort_values("event_date").head(max_labels)
    for _, ev in shown.iterrows():
        color = EVENT_COLORS.get(str(ev.get("type", "")), "#888888")
        fig.add_vline(x=ev["event_date"], line_dash="dot", line_width=1, line_color=color)
        fig.add_annotation(
            x=ev["event_date"], yref="paper", y=1.0, yanchor="bottom",
            text=str(ev.get("label", ""))[:28], showarrow=False,
            font={"size": 9, "color": color}, textangle=-30,
        )
    return fig


def kpi_value(value: float, kind: str = "int") -> str:
    """Indian-market friendly formatting: lakh/crore for volumes."""
    if pd.isna(value):
        return "—"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "pp":
        return f"{value:+.1f} pp"
    if abs(value) >= 1e7:
        return f"{value / 1e7:.2f} Cr"
    if abs(value) >= 1e5:
        return f"{value / 1e5:.2f} L"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.1f} K"
    return f"{value:,.0f}"


def choropleth(df: pd.DataFrame, geojson_path, value_col: str, name_col: str = "geojson_name",
               title: str = "", color_scale: str = "YlOrRd", **kwargs) -> go.Figure:
    """India state choropleth keyed on the GeoJSON ST_NM property."""
    with open(geojson_path, encoding="utf-8") as f:
        geo = json.load(f)
    fig = px.choropleth(
        df, geojson=geo, locations=name_col, featureidkey="properties.ST_NM",
        color=value_col, color_continuous_scale=color_scale, title=title, **kwargs,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"l": 0, "r": 0, "t": 50, "b": 0}, height=520)
    return fig


def ratio_band_chart(df: pd.DataFrame, x: str, y: str,
                     bands: tuple[float, float] = (0.9, 1.2), title: str = "") -> go.Figure:
    """Line with green/orange/red zones — the channel-health convention:
    below bands[0] = depletion, between = healthy, above = stock build-up."""
    lo, hi = bands
    fig = go.Figure()
    y_max = max(float(df[y].max()) * 1.1, hi * 1.2)
    fig.add_hrect(y0=0, y1=lo, fillcolor="#A4243B", opacity=0.07, line_width=0)
    fig.add_hrect(y0=lo, y1=hi, fillcolor="#758E4F", opacity=0.08, line_width=0)
    fig.add_hrect(y0=hi, y1=y_max, fillcolor="#E4572E", opacity=0.08, line_width=0)
    fig.add_trace(go.Scatter(x=df[x], y=df[y], mode="lines", line={"color": ACCENT, "width": 2.2}, name=y))
    fig.add_hline(y=1.0, line_dash="dash", line_width=1, line_color="#888888")
    fig.update_layout(title=title, yaxis_range=[min(float(df[y].min()) * 0.9, lo * 0.9), y_max],
                      showlegend=False)
    return fig


def diverging_bar(df: pd.DataFrame, category_col: str, value_col: str, title: str = "") -> go.Figure:
    """Gainers up / losers down — the share-shift convention."""
    d = df.sort_values(value_col, ascending=True)
    colors = [ACCENT_2 if v >= 0 else "#A4243B" for v in d[value_col]]
    fig = go.Figure(go.Bar(x=d[value_col], y=d[category_col], orientation="h",
                           marker_color=colors))
    fig.add_vline(x=0, line_width=1, line_color="#555555")
    fig.update_layout(title=title, height=200 + 24 * len(d), margin={"l": 10})
    return fig

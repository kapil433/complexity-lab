"""Shared visualization toolkit: lab plotly template, policy-event annotation,
choropleths and band charts.

Design rules (docs/blueprint §10): one accent colour for the primary signal,
muted neutrals elsewhere; whitespace over chrome; the most important number
biggest. Every time-series chart can overlay the policy events timeline so a
chart explains *why*, not just *what*.
"""

from __future__ import annotations

import json

import numpy as np
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
        # Transparent backgrounds: charts inherit the page colour, so the same
        # figure works in the app's light AND dark themes.
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"gridcolor": "rgba(128,128,128,0.25)", "zeroline": False},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
        hoverlabel={"namelength": 24},
    )
)
pio.templates["lab"] = LAB_TEMPLATE
pio.templates.default = "plotly_white+lab"


def use_lab_theme() -> None:
    """Make the lab template the plotly default (idempotent; call from app entry)."""
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
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    table = "ref_policy_events_canonical" if "ref_policy_events_canonical" in tables else "events"
    df = con.execute(f"SELECT * FROM {table}").df()
    if "tier" in df.columns and tiers:
        df = df[df["tier"].isin(tiers)]
    df["event_date"] = pd.to_datetime(df["date"], format="%Y-%m", errors="coerce")
    return df.dropna(subset=["event_date"])


def add_event_markers(fig: go.Figure, events: pd.DataFrame, max_labels: int = 10) -> go.Figure:
    """Overlay vertical dashed lines + labels for events on a time-series fig.

    Events are clipped to the figure's plotted date range (so a 2021+ chart
    doesn't get 2013 lines pushed off-canvas), then thinned evenly to
    ``max_labels`` across the range.
    """
    ev = events.dropna(subset=["event_date"]).sort_values("event_date")
    xs = []
    for tr in fig.data:
        x = getattr(tr, "x", None)
        if x is not None and len(x):
            xs.extend([pd.Timestamp(x[0]), pd.Timestamp(x[-1])])
    if xs:
        lo, hi = min(xs), max(xs)
        ev = ev[(ev["event_date"] >= lo) & (ev["event_date"] <= hi)]
    if len(ev) > max_labels:
        idx = np.linspace(0, len(ev) - 1, max_labels).round().astype(int)
        ev = ev.iloc[sorted(set(idx))]
    for _, e in ev.iterrows():
        color = EVENT_COLORS.get(str(e.get("type", "")), "#888888")
        fig.add_vline(x=e["event_date"], line_dash="dot", line_width=1, line_color=color)
        fig.add_annotation(
            x=e["event_date"], yref="paper", y=1.0, yanchor="bottom",
            text=str(e.get("label", ""))[:28], showarrow=False,
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


def indian_axis(fig: go.Figure, axis: str = "y", max_value: float | None = None) -> go.Figure:
    """Format an axis in Indian units (K / L / Cr) instead of SI (k/M).

    Plotly has no native lakh/crore notation, so we compute explicit ticks.
    Pass ``max_value`` when the figure's range isn't known from its traces.
    """
    if max_value is None:
        vals = []
        for tr in fig.data:
            v = getattr(tr, axis, None)
            if v is not None and len(v):
                arr = pd.to_numeric(pd.Series(v), errors="coerce").dropna()
                if len(arr):
                    vals.append(float(arr.max()))
        if not vals:
            return fig
        max_value = max(vals)
    if max_value <= 0:
        return fig
    step = 10 ** np.floor(np.log10(max_value / 4))
    step = step * (2 if max_value / step > 8 else 1)
    ticks = np.arange(0, max_value * 1.15, step)
    fig.update_layout(
        {f"{axis}axis": {"tickvals": ticks, "ticktext": [kpi_value(t) for t in ticks]}}
    )
    return fig


def pct_axis(fig: go.Figure, axis: str = "y", decimals: int = 1) -> go.Figure:
    """Percent notation on an axis holding 0-1 shares."""
    fig.update_layout({f"{axis}axis": {"tickformat": f".{decimals}%"}})
    return fig


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


def diverging_bar(df: pd.DataFrame, category_col: str, value_col: str, title: str = "",
                  unit: str = " pp") -> go.Figure:
    """Gainers up / losers down — the share-shift convention."""
    d = df.sort_values(value_col, ascending=True)
    colors = [ACCENT_2 if v >= 0 else "#A4243B" for v in d[value_col]]
    fig = go.Figure(go.Bar(
        x=d[value_col], y=d[category_col], orientation="h", marker_color=colors,
        text=[f"{v:+.1f}{unit}" for v in d[value_col]], textposition="outside",
    ))
    fig.add_vline(x=0, line_width=1, line_color="#555555")
    fig.update_layout(title=title, height=200 + 24 * len(d), margin={"l": 10},
                      xaxis_ticksuffix=unit)
    return fig

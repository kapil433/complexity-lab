"""Diffusion Lab: Bass fits per state + forward scenarios with policy levers."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_card

from complexity_lab.simulation.diffusion import (
    bass_cumulative,
    fit_bass,
    prepare_adoption_series,
    project_bass,
)

st.set_page_config(page_title="Diffusion Lab", layout="wide")
st.title("Diffusion Lab — Bass model")
render_card("ev-diffusion-states")
st.caption(
    "Series are prepared before fitting: the last 2 months are dropped (VAHAN reporting "
    "lag) and each series starts at adoption onset — fitting through years of zeros or a "
    "partial tail silently distorts p, m and the implied peak."
)

fuel = st.radio("Technology", ["EV", "CNG"], horizontal=True)
col = "ev_regs" if fuel == "EV" else "cng_regs"

panel = query(
    f"""SELECT state_code, state_name, year, month, date, {col} AS adopt
        FROM panel_state_month ORDER BY state_code, year, month"""
)
state = st.selectbox(
    "State", sorted(panel["state_name"].unique()),
    index=sorted(panel["state_name"].unique()).index("All India"),
)
series = panel[panel["state_name"] == state].reset_index(drop=True)
cum = prepare_adoption_series(series["adopt"], drop_last=2, onset_units=50)
if cum.empty:
    st.warning(f"{state} has not reached adoption onset for {fuel}.")
    st.stop()
dates = series["date"].iloc[len(series) - 2 - len(cum): len(series) - 2].reset_index(drop=True)

fit = fit_bass(cum)
m_at_bound = bool(np.isfinite(fit.get("m", np.nan)) and fit["m"] >= 0.95 * cum.iloc[-1] * 50)
c1, c2, c3, c4 = st.columns(4)
c1.metric("p (innovation)", f"{fit['p']:.4f}" if pd.notna(fit["p"]) else "—")
c2.metric("q (imitation)", f"{fit['q']:.3f}" if pd.notna(fit["q"]) else "—")
c3.metric("m (potential)", f"{fit['m']:,.0f}" if pd.notna(fit["m"]) else "—",
          "at bound — distrust" if m_at_bound else None)
c4.metric("R²", f"{fit['r2']:.4f}" if pd.notna(fit["r2"]) else "—")
if m_at_bound:
    st.warning(
        "The fitted market potential sits at the optimiser's bound: this S-curve hasn't "
        "bent yet, so m (and any projection) is an extrapolation, not an estimate."
    )

st.subheader("Scenario levers")
s1, s2, s3, s4 = st.columns(4)
q_mult = s1.slider("Imitation ×", 0.5, 2.0, 1.0, 0.05, help="Social contagion strength (visibility, word of mouth)")
p_mult = s2.slider("Innovation ×", 0.5, 3.0, 1.0, 0.05, help="Early-adopter pull (launches, incentives)")
m_mult = s3.slider("Market potential ×", 0.5, 3.0, 1.0, 0.1, help="Eventual addressable market (infra, price parity)")
horizon = s4.slider("Horizon (months)", 24, 120, 60, 12)

if pd.notna(fit["p"]):
    t_hist = np.arange(len(cum), dtype=float)
    proj = project_bass(fit, horizon=len(cum) + horizon, p_mult=p_mult, q_mult=q_mult, m_mult=m_mult)
    fitted = bass_cumulative(t_hist, fit["p"], fit["q"], fit["m"])
    future_dates = pd.date_range(dates.iloc[0], periods=len(proj), freq="MS")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=cum, name="Observed (cumulative)", mode="lines",
                             line={"width": 3}))
    fig.add_trace(go.Scatter(x=dates, y=fitted, name="Bass fit", mode="lines",
                             line={"dash": "dot"}))
    fig.add_trace(go.Scatter(x=future_dates, y=proj["cumulative"], name="Scenario",
                             mode="lines"))
    fig.add_vline(x=dates.iloc[-1], line_dash="dash", line_color="#888", opacity=0.5)
    fig.update_layout(height=440, yaxis_title=f"Cumulative {fuel} registrations",
                      title=f"{state}: observed vs fit vs scenario (levers reshape the whole curve)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Could not fit Bass model for this series (too small / degenerate).")

st.subheader(f"Cross-state Bass parameters ({fuel})")


@st.cache_data(ttl=3600, show_spinner="Fitting all states…")
def _fit_all(value_col: str) -> pd.DataFrame:
    from complexity_lab.simulation.diffusion import fit_bass_by_state

    p = query(
        f"""SELECT state_code, year, month, {value_col}
            FROM panel_state_month WHERE state_code <> 'ALL'
            ORDER BY state_code, year, month"""
    )
    fits = fit_bass_by_state(p, value_col=value_col, min_total=1000).reset_index()
    names = query("SELECT state_code, state_name FROM dim_state")
    return fits.merge(names, on="state_code")

if st.toggle("Fit all states", value=False):
    fits = _fit_all(col)
    ok = fits.dropna(subset=["p", "q"])
    solid = ok[~ok["m_at_bound"]]
    st.caption(
        f"{len(ok)} states fit; {int(ok['m_at_bound'].sum())} have m at the bound "
        "(early-curve — shown hollow, their m is not interpretable)."
    )
    figp = px.scatter(
        solid, x="p", y="q", text="state_code", hover_name="state_name", size="m",
        title="Innovation (p) vs imitation (q) by state — size = market potential",
    )
    bound = ok[ok["m_at_bound"]]
    if not bound.empty:
        figp.add_scatter(x=bound["p"], y=bound["q"], mode="markers+text",
                         text=bound["state_code"], textposition="top center",
                         marker={"symbol": "circle-open", "size": 10, "color": "#999"},
                         name="m at bound")
    figp.update_traces(textposition="top center")
    st.plotly_chart(figp, use_container_width=True)
    st.dataframe(
        fits.set_index("state_code")[["state_name", "p", "q", "m", "m_at_bound",
                                      "r2", "peak_time", "n_months_fit"]].round(4),
        use_container_width=True,
    )

"""Diffusion Lab: Bass fits per state + forward scenarios with policy levers."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_card

from complexity_lab.simulation.diffusion import bass_cumulative, fit_bass, project_bass

st.set_page_config(page_title="Diffusion Lab", layout="wide")
st.title("Diffusion Lab — Bass model")
render_card("ev-diffusion-states")

fuel = st.radio("Technology", ["EV", "CNG"], horizontal=True)
col = "ev_regs" if fuel == "EV" else "cng_regs"

panel = query(
    f"""SELECT state_code, state_name, year, month, {col} AS adopt
        FROM panel_state_month ORDER BY state_code, year, month"""
)
state = st.selectbox(
    "State", sorted(panel["state_name"].unique()), index=sorted(panel["state_name"].unique()).index("All India")
)
series = panel[panel["state_name"] == state].reset_index(drop=True)
cum = series["adopt"].fillna(0).cumsum()

fit = fit_bass(cum)
c1, c2, c3, c4 = st.columns(4)
c1.metric("p (innovation)", f"{fit['p']:.4f}" if pd.notna(fit["p"]) else "—")
c2.metric("q (imitation)", f"{fit['q']:.3f}" if pd.notna(fit["q"]) else "—")
c3.metric("m (potential)", f"{fit['m']:,.0f}" if pd.notna(fit["m"]) else "—")
c4.metric("R²", f"{fit['r2']:.4f}" if pd.notna(fit["r2"]) else "—")

st.subheader("Scenario levers")
s1, s2, s3, s4 = st.columns(4)
q_mult = s1.slider("Imitation ×", 0.5, 2.0, 1.0, 0.05, help="Social contagion strength (visibility, word of mouth)")
p_mult = s2.slider("Innovation ×", 0.5, 3.0, 1.0, 0.05, help="Early-adopter pull (launches, incentives)")
m_mult = s3.slider("Market potential ×", 0.5, 3.0, 1.0, 0.1, help="Eventual addressable market (infra, price parity)")
horizon = s4.slider("Horizon (months)", 24, 120, 60, 12)

if pd.notna(fit["p"]):
    import numpy as np

    t_hist = np.arange(len(cum), dtype=float)
    proj = project_bass(fit, horizon=len(cum) + horizon, p_mult=p_mult, q_mult=q_mult, m_mult=m_mult)
    fitted = bass_cumulative(t_hist, fit["p"], fit["q"], fit["m"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=cum, name="Observed (cumulative)", mode="lines"))
    fig.add_trace(go.Scatter(y=fitted, name="Bass fit", mode="lines", line=dict(dash="dot")))
    fig.add_trace(go.Scatter(x=proj["t"], y=proj["cumulative"], name="Scenario", mode="lines"))
    fig.update_layout(height=420, xaxis_title="Months since series start", yaxis_title=f"Cumulative {fuel}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Could not fit Bass model for this series (too small / degenerate).")

st.subheader(f"Cross-state Bass parameters ({fuel})")
run_all = st.button("Fit all states")
if run_all:
    from complexity_lab.simulation.diffusion import fit_bass_by_state

    fits = fit_bass_by_state(
        panel.rename(columns={"adopt": col}), value_col=col, state_col="state_code", min_total=1000
    ).reset_index()
    names = query("SELECT state_code, state_name FROM dim_state")
    fits = fits.merge(names, on="state_code")
    st.plotly_chart(
        px.scatter(fits.dropna(subset=["p", "q"]), x="p", y="q", text="state_code",
                   hover_name="state_name", size="m", title="Innovation vs imitation by state"),
        use_container_width=True,
    )
    st.dataframe(fits, use_container_width=True)

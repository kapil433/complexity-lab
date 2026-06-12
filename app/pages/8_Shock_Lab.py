"""Shock Lab: demand & supply shock simulation on the factory→dealer→retail channel."""

import sys
from pathlib import Path

import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import render_card

from complexity_lab.simulation.shocks import (
    ShockConfig,
    ShockWindow,
    run_shock_sim,
    shock_summary,
)

st.set_page_config(page_title="Shock Lab", layout="wide")
st.title("Shock Lab — demand & supply shocks in the sales channel")
render_card("shock-lab")

with st.sidebar:
    st.header("Scenario")
    n_months = st.slider("Simulation length (months)", 24, 120, 60)
    st.subheader("Demand shock")
    d_mult = st.slider("Demand multiplier", 0.0, 2.0, 0.5, 0.05,
                       help="<1 = collapse (COVID ≈ 0.1–0.5); >1 = boom (festive pull ≈ 1.2)")
    d_start = st.slider("Demand shock start (month)", 0, 100, 24)
    d_len = st.slider("Demand shock length", 1, 24, 3)
    st.subheader("Supply shock")
    s_mult = st.slider("Supply multiplier", 0.0, 1.5, 1.0, 0.05,
                       help="<1 = production cut (chip shortage ≈ 0.6–0.8); 1 = none")
    s_start = st.slider("Supply shock start (month)", 0, 100, 24)
    s_len = st.slider("Supply shock length", 1, 24, 6)
    st.subheader("Channel behaviour")
    target_cover = st.slider("Target stock cover (months)", 0.5, 3.0, 1.1, 0.1)
    adj_lag = st.slider("Production adjustment lag (months)", 1.0, 12.0, 3.0, 0.5)

cfg = ShockConfig(
    n_months=n_months,
    target_cover=target_cover,
    adjustment_lag=adj_lag,
    demand_shocks=[ShockWindow(d_start, d_start + d_len, d_mult)] if d_mult != 1.0 else [],
    supply_shocks=[ShockWindow(s_start, s_start + s_len, s_mult)] if s_mult != 1.0 else [],
)
baseline = run_shock_sim(ShockConfig(n_months=n_months, target_cover=target_cover, adjustment_lag=adj_lag))
result = run_shock_sim(cfg)
summary = shock_summary(result, baseline)

k = st.columns(5)
k[0].metric("Lost sales (units)", f"{summary['total_lost_sales']:,}")
k[1].metric("Retail gap vs baseline", f"{summary['retail_vs_baseline_gap']:,}")
k[2].metric("Trough month", summary["trough_month"],
            f"{(summary['trough_retail_vs_baseline'] - 1):+.0%} vs baseline")
k[3].metric("Recovery month", summary["recovery_month"] if summary["recovery_month"] else "—")
k[4].metric("Bullwhip (prod var / retail var)", summary["bullwhip_ratio"])

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.4, 0.3, 0.3],
                    subplot_titles=["Demand, retail & production", "Dealer inventory (months of cover)",
                                    "Wholesale/retail ratio"])
m = result["month"]
fig.add_scatter(x=m, y=result["demand"], name="latent demand", line={"dash": "dot", "color": "#888"}, row=1, col=1)
fig.add_scatter(x=m, y=result["retail"], name="retail", line={"color": "#1f77b4"}, row=1, col=1)
fig.add_scatter(x=m, y=result["production"], name="production (wholesale)", line={"color": "#ff7f0e"}, row=1, col=1)
fig.add_scatter(x=m, y=baseline["retail"], name="baseline retail", line={"color": "#1f77b4", "width": 1, "dash": "dash"},
                opacity=0.4, row=1, col=1)
fig.add_scatter(x=m, y=result["inventory_cover_months"], name="stock cover", line={"color": "#2ca02c"}, row=2, col=1)
fig.add_hline(y=target_cover, line={"dash": "dot", "color": "#2ca02c"}, opacity=0.5, row=2, col=1)
fig.add_scatter(x=m, y=result["ws_retail_ratio"], name="ws/retail", line={"color": "#d62728"}, row=3, col=1)
fig.add_hrect(y0=0.9, y1=1.2, fillcolor="green", opacity=0.07, line_width=0, row=3, col=1)

for w, color in [(cfg.demand_shocks, "rgba(31,119,180,0.12)"), (cfg.supply_shocks, "rgba(214,39,40,0.12)")]:
    for win in w:
        for r in (1, 2, 3):
            fig.add_vrect(x0=win.start, x1=win.end, fillcolor=color, line_width=0, row=r, col=1)

fig.update_layout(height=750, margin={"t": 60}, hovermode="x unified",
                  legend={"orientation": "h", "y": 1.06})
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Blue band = demand shock window, red band = supply shock window. Compare scenarios: "
    "a pure demand collapse builds inventory (ws/retail spikes >1.2) with no lost sales; "
    "a pure supply cut drains inventory and loses sales only once stock runs out — "
    "the channel buffer is why short supply shocks barely dent retail."
)

with st.expander("Replay history: presets"):
    st.markdown(
        "- **COVID wave 1** — demand 0.15 for 3 months, supply 0.2 for 2 months (overlapping).\n"
        "- **Chip shortage 2021-22** — supply 0.7 for 12 months, demand 1.0.\n"
        "- **BS6 transition** — demand 1.3 for 2 months (pre-buy), then 0.6 for 3 (pull-forward payback).\n"
        "Set the sliders to these values and compare the ws/retail trace with the real one on the "
        "Wholesale page — the simulator reproduces the qualitative signatures."
    )

"""Complexity Lab — interactive entry point."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from common import query

st.set_page_config(page_title="Complexity Lab", page_icon="🧪", layout="wide")

st.title("🧪 Complexity Lab")
st.caption(
    "India's PV market as a complex system — VAHAN registrations × state covariates. "
    "Source: Vahan Intelligence (vahanintelligence.in), based on VAHAN/Parivahan public data."
)

totals = query(
    """SELECT year, SUM(total_regs) AS regs, SUM(ev_regs) AS ev
       FROM panel_state_year WHERE state_code = 'ALL' GROUP BY year ORDER BY year"""
)
latest_full = totals[totals["year"] < totals["year"].max()].iloc[-1]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest full year", int(latest_full["year"]))
c2.metric("PV registrations", f"{latest_full['regs'] / 1e6:.2f} M")
c3.metric("EV share", f"{latest_full['ev'] / latest_full['regs']:.1%}")
n_exp = query("SELECT 1").shape[0]  # placeholder to keep cache warm
c4.metric("States tracked", query("SELECT COUNT(*) c FROM dim_state WHERE state_code <> 'ALL'")["c"][0])

st.line_chart(totals.set_index("year")["regs"], height=260)

st.markdown(
    """
**Pages**

- **Explorer** — registrations, fuel mix and concentration by state, with choropleth.
- **Networks** — the OEM–state bipartite network, communities and centrality over time.
- **Diffusion Lab** — Bass-model fits of EV/CNG adoption and what-if scenario sliders.
- **Hypothesis Tester** — pick variables from the panel, get correlations, panel regressions and changepoints.

Run scripted, reproducible versions of these analyses with `uv run lab run <experiment>`;
write new ones in `experiments/` (see docs/lab-guide.md).
"""
)

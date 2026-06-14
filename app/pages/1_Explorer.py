"""Explorer: state-level registrations, fuel mix, concentration, choropleth."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import load_geojson, query, render_app_shell, render_card

from complexity_lab.viz import indian_axis, pct_axis

st.set_page_config(page_title="Compare and Explore | Complexity Lab", layout="wide")
page = render_app_shell(
    "Compare and Explore",
    section="Observe",
    description="Compare states across registrations, fuel adoption, concentration, and context.",
    limitations=(
        "Maps show association and distribution, not causal effects.",
        "Population metrics use the quality and denominator named in the metric label.",
    ),
)
render_card("descriptive-baseline")

METRICS = {
    "total_regs": ("Total registrations", "indian"),
    "ev_share": ("EV share", "pct"),
    "cng_share": ("CNG share", "pct"),
    "diesel_share": ("Diesel share", "pct"),
    "petrol_share": ("Petrol share", "pct"),
    "hhi_oem": ("OEM concentration (HHI, 0–10,000)", "raw"),
    "entropy_oem": ("OEM entropy (nats)", "raw"),
    "yoy_growth": ("YoY growth", "pct"),
    "regs_per_1000_population_2024": (
        "Registrations per 1,000 people (fixed 2024 population basis)",
        "raw",
    ),
    "regs_per_1000_population": (
        "Registrations per 1,000 people (estimated annual population)",
        "raw",
    ),
    "real_pc_income_inr": (
        "Per-capita income, constant 2011-12 prices (₹)",
        "indian",
    ),
    "real_gsdp_growth_pct": ("Real GSDP growth", "pct"),
    "broad_credit_per_capita_inr": ("Broad credit per capita (₹)", "indian"),
}

panel = query("SELECT * FROM experiment_state_year")
y0, y1 = page.filters.year_start, page.filters.year_end
metric = st.selectbox(
    "Metric", list(METRICS), format_func=lambda m: METRICS[m][0],
)
metric_label, metric_kind = METRICS[metric]

# Independent bounds: tying this slider to the range slider above resets it
# whenever the range moves (a "stuck slider" in practice).
data_lo, data_hi = int(panel["year"].min()), int(panel["year"].max())
snap_year = st.slider("Choropleth year", data_lo, data_hi, min(data_hi - 1, y1))
snap = panel[panel["year"] == snap_year]
if page.filters.states:
    snap = snap[snap["state_code"].isin(page.filters.states)]
snap = snap.merge(
    query("SELECT state_code, geojson_name FROM dim_state"), on="state_code", how="left"
)

fig = px.choropleth(
    snap,
    geojson=load_geojson(),
    locations="geojson_name",
    featureidkey="properties.ST_NM",
    color=metric,
    color_continuous_scale="Viridis",
    hover_name="state_name",
    hover_data={"total_regs": ":,", "ev_share": ":.2%", "geojson_name": False},
    title=f"{metric_label} — {snap_year}",
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(height=560, margin=dict(l=0, r=0, t=40, b=0),
                  coloraxis_colorbar_title=None)
if metric_kind == "pct":
    fig.update_layout(coloraxis_colorbar_tickformat=".1%")
st.plotly_chart(fig, width="stretch")

st.subheader("Time series")
default_states = panel.loc[
    panel["state_code"].isin(page.filters.states), "state_name"
].drop_duplicates().tolist()
states = st.multiselect(
    "States",
    sorted(panel["state_name"].unique()),
    default=default_states or ["Maharashtra", "Karnataka", "Uttar Pradesh"],
)
sel = panel[(panel["state_name"].isin(states)) & panel["year"].between(y0, y1)]
fig2 = px.line(sel, x="year", y=metric, color="state_name", markers=True)
fig2.update_layout(height=380, yaxis_title=metric_label)
if metric_kind == "pct":
    pct_axis(fig2)
elif metric_kind == "indian":
    indian_axis(fig2)
st.plotly_chart(fig2, width="stretch")

st.subheader("Fuel mix (All India)")
mix = query(
    """SELECT year, petrol_regs AS Petrol, diesel_regs AS Diesel, cng_regs AS CNG,
              ev_regs AS EV, hybrid_regs AS "Strong Hybrid"
       FROM panel_state_year WHERE state_code = 'ALL' ORDER BY year"""
)
mix_long = mix.melt(id_vars="year", var_name="fuel", value_name="regs")
mix_long = mix_long[mix_long["year"].between(y0, y1)]
st.plotly_chart(
    px.area(mix_long, x="year", y="regs", color="fuel", groupnorm="percent"),
    width="stretch",
)

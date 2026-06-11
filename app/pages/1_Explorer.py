"""Explorer: state-level registrations, fuel mix, concentration, choropleth."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import load_geojson, query, render_card, year_range_slider

st.set_page_config(page_title="Explorer", layout="wide")
st.title("Explorer")
render_card("descriptive-baseline")

panel = query("SELECT * FROM panel_state_year WHERE state_code <> 'ALL'")
y0, y1 = year_range_slider(panel)
metric = st.selectbox(
    "Metric",
    ["total_regs", "ev_share", "cng_share", "hhi_oem", "entropy_oem", "yoy_growth", "pc_income_inr"],
)

snap_year = st.slider("Choropleth year", y0, y1, y1)
snap = panel[panel["year"] == snap_year].merge(
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
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Time series")
states = st.multiselect(
    "States", sorted(panel["state_name"].unique()), default=["Maharashtra", "Karnataka", "Uttar Pradesh"]
)
sel = panel[(panel["state_name"].isin(states)) & panel["year"].between(y0, y1)]
fig2 = px.line(sel, x="year", y=metric, color="state_name", markers=True)
fig2.update_layout(height=380)
st.plotly_chart(fig2, use_container_width=True)

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
    use_container_width=True,
)

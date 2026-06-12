"""Macro Dashboard: the market at a glance — KPIs, share shifts, fuel penetration,
channel health. Blueprint §7.6 P0 page."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, load_geojson, query, render_card

from complexity_lab.viz import (
    add_event_markers,
    diverging_bar,
    indian_axis,
    kpi_value,
    load_events,
    ratio_band_chart,
)

st.set_page_config(page_title="Macro Dashboard", layout="wide")
st.title("Macro Dashboard")
render_card("descriptive-baseline")

national = query("SELECT * FROM panel_state_year WHERE state_code = 'ALL' ORDER BY year")
latest = int(national["year"].max()) - 1  # last full year
row = national[national["year"] == latest].iloc[0]
prev = national[national["year"] == latest - 1].iloc[0]

# ---- KPI strip -------------------------------------------------------------
st.subheader(f"India 4W PV — {latest} (last full year)")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Registrations", kpi_value(row["total_regs"]),
          f"{row['yoy_growth']:+.1%} YoY")
c2.metric("EV penetration", kpi_value(row["ev_share"], "pct"),
          kpi_value(row["ev_share_chg_pp"], "pp"))
c3.metric("CNG penetration", kpi_value(row["cng_share"], "pct"),
          kpi_value(row["cng_share_chg_pp"], "pp"))
c4.metric("Diesel penetration", kpi_value(row["diesel_share"], "pct"),
          kpi_value(row["diesel_share_chg_pp"], "pp"))
c5.metric("OEM concentration (HHI)", f"{row['hhi_oem']:,.0f}",
          f"{row['hhi_oem'] - prev['hhi_oem']:+,.0f}")

# ---- national trend with policy events ------------------------------------
monthly = query("SELECT * FROM panel_state_month WHERE state_code = 'ALL' ORDER BY date")
fig = px.area(monthly, x="date",
              y=["petrol_regs", "diesel_regs", "cng_regs", "ev_regs", "hybrid_regs"],
              title="Monthly registrations by fuel — the structural story",
              labels={"value": "registrations", "variable": "fuel"})
fig.for_each_trace(lambda t: t.update(name=t.name.replace("_regs", "").replace("hybrid", "strong hybrid").title()))
indian_axis(fig, max_value=float(monthly["total_regs"].max()))
if st.checkbox("Show policy events", value=True):
    fig = add_event_markers(fig, load_events(get_connection()), max_labels=12)
st.plotly_chart(fig, use_container_width=True)

# ---- market share shift ----------------------------------------------------
st.subheader("OEM market share & shift")
col_a, col_b = st.columns([1, 1])
ms = query(f"SELECT * FROM maker_state_share WHERE state_code = 'ALL' AND year = {latest} "
           "ORDER BY share DESC")
with col_a:
    top = ms.head(12).copy()
    top["share_pct"] = top["share"] * 100
    st.plotly_chart(
        diverging_bar(top, "maker", "share_chg_pp",
                      title=f"Share change {latest - 1} → {latest} (pp)"),
        use_container_width=True,
    )
with col_b:
    ms_hist = query(
        "SELECT year, maker, share FROM maker_state_share WHERE state_code = 'ALL' "
        f"AND maker IN (SELECT maker FROM maker_state_share WHERE state_code='ALL' "
        f"AND year={latest} ORDER BY share DESC LIMIT 6) AND year <= {latest} ORDER BY year"
    )
    figms = px.line(ms_hist, x="year", y="share", color="maker",
                    title="Top-6 OEM market share")
    figms.update_yaxes(tickformat=".0%")
    st.plotly_chart(figms, use_container_width=True)

# ---- fuel penetration across states ---------------------------------------
st.subheader("Fuel penetration across states")
fuel_choice = st.selectbox("Fuel", ["ev_share", "cng_share", "diesel_share",
                                    "petrol_share", "hybrid_share"])
mode = st.radio("Show", ["level (%)", "change (pp, YoY)"], horizontal=True)
col_map_field = fuel_choice if mode.startswith("level") else fuel_choice.replace("_share", "_share_chg_pp")

snap = query(f"SELECT * FROM panel_state_year WHERE year = {latest} AND state_code <> 'ALL'").merge(
    query("SELECT state_code, geojson_name, zone FROM dim_state"), on="state_code", how="left"
)
figc = px.choropleth(
    snap, geojson=load_geojson(), locations="geojson_name",
    featureidkey="properties.ST_NM", color=col_map_field,
    color_continuous_scale="YlOrRd" if mode.startswith("level") else "RdBu_r",
    title=f"{fuel_choice.replace('_', ' ')} — {mode}, {latest}",
)
figc.update_geos(fitbounds="locations", visible=False)
figc.update_layout(height=520, margin={"l": 0, "r": 0, "t": 50, "b": 0})
st.plotly_chart(figc, use_container_width=True)

# heatmap: state × year EV penetration, zone-sorted (blueprint §3.1)
hm = query("SELECT state_code, year, ev_share FROM panel_state_year "
           f"WHERE state_code <> 'ALL' AND year BETWEEN 2016 AND {latest}").merge(
    query("SELECT state_code, zone FROM dim_state"), on="state_code")
hm = hm.sort_values(["zone", "state_code"])
pivot = hm.pivot_table(index="state_code", columns="year", values="ev_share")
pivot = pivot.reindex(hm["state_code"].unique())
fig_hm = px.imshow(pivot * 100, aspect="auto", color_continuous_scale="Viridis",
                   title="EV penetration % — state × year (grouped by zone)",
                   labels={"color": "EV %"})
fig_hm.update_layout(height=720)
st.plotly_chart(fig_hm, use_container_width=True)

# ---- channel health (local wholesale data) ---------------------------------
tables = {r[0] for r in get_connection().execute("SHOW TABLES").fetchall()}
if "wholesale" in tables:
    st.subheader("Channel health (wholesale / retail)")
    rw = query("SELECT * FROM retail_wholesale_month ORDER BY date")
    st.plotly_chart(
        ratio_band_chart(rw, "date", "ws_retail_ratio",
                         title="Wholesale/retail ratio — green band = healthy channel"),
        use_container_width=True,
    )
else:
    st.caption("Channel health needs the local wholesale data — `uv run lab wholesale`.")

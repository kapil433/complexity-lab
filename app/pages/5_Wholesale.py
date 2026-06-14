"""Wholesale: model-level explorer + retail-vs-wholesale nowcast view."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query, render_app_shell, render_card

from complexity_lab.viz import indian_axis

st.set_page_config(page_title="Wholesale and Channel | Complexity Lab", layout="wide")
page = render_app_shell(
    "Wholesale and Channel",
    section="Observe",
    description="Inspect dispatches, models, segments, cities, and the wholesale-retail channel.",
    limitations=(
        "Wholesale has no fuel cut.",
        "April 2017-March 2022 is a panel-city sample; national claims use April 2022 onward.",
        "Proprietary wholesale rows remain local and are never published.",
    ),
)
render_card("wholesale-retail-nowcast")

tables = {r[0] for r in get_connection().execute("SHOW TABLES").fetchall()}
if "wholesale" not in tables:
    st.warning("Wholesale data not ingested on this machine — run `uv run lab wholesale`.")
    st.stop()

st.caption(
    "Proprietary source (local only, not in the repo). Full industry coverage from "
    "2022-04; earlier rows are a ~50-city sample — views below use the full era."
)

tab_now, tab_models, tab_seg, tab_ev, tab_city = st.tabs(
    ["Nowcast", "Models", "Segments", "Model metadata (no fuel cut)", "Cities"]
)

with tab_now:
    rw = query("SELECT * FROM retail_wholesale_month ORDER BY date")
    fig_rw = px.line(rw, x="date", y=["retail", "wholesale"],
                     title="National retail vs wholesale (units/month)",
                     labels={"value": "units", "variable": ""})
    st.plotly_chart(indian_axis(fig_rw), width="stretch")
    st.plotly_chart(
        px.line(rw, x="date", y="ws_retail_ratio", title="Wholesale / retail (channel stock build >1)"),
        width="stretch",
    )
    if st.button("Run 12-month out-of-sample nowcast"):
        from complexity_lab.analysis.nowcast import nowcast_eval

        res = nowcast_eval(rw, test_months=12)
        c1, c2 = st.columns(2)
        c1.metric("Nowcast MAPE", f"{res['mape_nowcast']:.1%}")
        c2.metric("Seasonal baseline MAPE", f"{res['mape_baseline']:.1%}")
        st.plotly_chart(
            px.line(res["predictions"], x="date", y=["actual", "nowcast", "baseline"], markers=True),
            width="stretch",
        )

with tab_models:
    yr = st.slider("Year", 2022, 2026, 2025, key="m_yr")
    top_n = st.slider("Top N models", 5, 40, 20)
    models = query(
        f"""SELECT model, maker, SUM(wholesale) AS units FROM ws_model_month
            WHERE year = {yr} GROUP BY model, maker ORDER BY units DESC LIMIT {top_n}"""
    )
    fig_m = px.bar(models, x="units", y="model", color="maker", orientation="h",
                   height=200 + 22 * top_n, title=f"Top models by dispatches, {yr}")
    st.plotly_chart(indian_axis(fig_m, axis="x"), width="stretch")
    pick = st.selectbox("Model trajectory", sorted(query(
        "SELECT DISTINCT model FROM ws_model_month WHERE year >= 2022")["model"]))
    traj = query(
        f"SELECT date, SUM(wholesale) units FROM ws_model_month WHERE model = '{pick}' "
        "AND year >= 2022 GROUP BY date ORDER BY date"
    )
    st.plotly_chart(px.line(traj, x="date", y="units", title=pick), width="stretch")

with tab_seg:
    seg = query(
        """SELECT segment5, date, SUM(wholesale) AS units FROM ws_segment_month
           WHERE year >= 2022 GROUP BY segment5, date ORDER BY date"""
    )
    st.plotly_chart(
        px.area(seg, x="date", y="units", color="segment5", groupnorm="percent",
                title="Segment share of wholesale"),
        width="stretch",
    )

with tab_ev:
    st.warning(
        "Wholesale has no fuel cut: the source has no fuel/powertrain field and "
        "does not split a model's quantity by Petrol, Diesel, CNG, EV, or Hybrid."
    )
    st.caption(
        "The EV-only view is a model subset, not an EV fuel cut. EV variants of "
        "Nexon/Punch/Tiago remain inseparable from other powertrains. The primary-fuel "
        "chart below is legacy external model metadata and must not be read as observed "
        "wholesale fuel mix, share, or volume."
    )
    ev = query(
        "SELECT date, maker, SUM(wholesale) AS units FROM ws_ev_month "
        "WHERE year >= 2022 GROUP BY date, maker ORDER BY date"
    )
    fig_ev = px.area(ev, x="date", y="units", color="maker",
                     title="EV-only nameplate dispatches by OEM (units/month)")
    st.plotly_chart(indian_axis(fig_ev, max_value=float(ev.groupby("date")["units"].sum().max())),
                    width="stretch")
    fuel = query(
        "SELECT date, fuel, SUM(wholesale) AS units FROM ws_fuel_month "
        "WHERE year >= 2022 GROUP BY date, fuel ORDER BY date"
    )
    st.plotly_chart(
        px.area(fuel, x="date", y="units", color="fuel", groupnorm="percent",
                title="Legacy primary-fuel model proxy — NOT a wholesale fuel cut"),
        width="stretch",
    )
    ev_states = query(
        "SELECT state_code, SUM(wholesale) AS units FROM ws_ev_month "
        "WHERE state_code IS NOT NULL AND year >= 2024 GROUP BY state_code "
        "ORDER BY units DESC LIMIT 15"
    )
    st.plotly_chart(
        px.bar(ev_states, x="units", y="state_code", orientation="h",
               title="EV-only dispatches by state, 2024+"),
        width="stretch",
    )

with tab_city:
    yr2 = st.slider("Year", 2022, 2026, 2025, key="c_yr")
    cities = query(
        f"""SELECT city, state_code, SUM(qty) AS units FROM wholesale
            WHERE year = {yr2} GROUP BY city, state_code ORDER BY units DESC LIMIT 30"""
    )
    st.plotly_chart(
        px.bar(cities, x="units", y="city", color="state_code", orientation="h", height=800),
        width="stretch",
    )

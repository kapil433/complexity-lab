"""Wholesale: model-level explorer + retail-vs-wholesale nowcast view."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query

st.set_page_config(page_title="Wholesale", layout="wide")
st.title("Wholesale — dispatches, models, nowcast")

tables = {r[0] for r in get_connection().execute("SHOW TABLES").fetchall()}
if "wholesale" not in tables:
    st.warning("Wholesale data not ingested on this machine — run `uv run lab wholesale`.")
    st.stop()

st.caption(
    "Proprietary source (local only, not in the repo). Full industry coverage from "
    "2022-04; earlier rows are a ~50-city sample — views below use the full era."
)

tab_now, tab_models, tab_seg, tab_city = st.tabs(
    ["Nowcast", "Models", "Segments", "Cities"]
)

with tab_now:
    rw = query("SELECT * FROM retail_wholesale_month ORDER BY date")
    st.plotly_chart(px.line(rw, x="date", y=["retail", "wholesale"]), use_container_width=True)
    st.plotly_chart(
        px.line(rw, x="date", y="ws_retail_ratio", title="Wholesale / retail (channel stock build >1)"),
        use_container_width=True,
    )
    if st.button("Run 12-month out-of-sample nowcast"):
        from complexity_lab.analysis.nowcast import nowcast_eval

        res = nowcast_eval(rw, test_months=12)
        c1, c2 = st.columns(2)
        c1.metric("Nowcast MAPE", f"{res['mape_nowcast']:.1%}")
        c2.metric("Seasonal baseline MAPE", f"{res['mape_baseline']:.1%}")
        st.plotly_chart(
            px.line(res["predictions"], x="date", y=["actual", "nowcast", "baseline"], markers=True),
            use_container_width=True,
        )

with tab_models:
    yr = st.slider("Year", 2022, 2026, 2025, key="m_yr")
    top_n = st.slider("Top N models", 5, 40, 20)
    models = query(
        f"""SELECT model, maker, SUM(wholesale) AS units FROM ws_model_month
            WHERE year = {yr} GROUP BY model, maker ORDER BY units DESC LIMIT {top_n}"""
    )
    st.plotly_chart(
        px.bar(models, x="units", y="model", color="maker", orientation="h",
               height=200 + 22 * top_n),
        use_container_width=True,
    )
    pick = st.selectbox("Model trajectory", sorted(query(
        "SELECT DISTINCT model FROM ws_model_month WHERE year >= 2022")["model"]))
    traj = query(
        f"SELECT date, SUM(wholesale) units FROM ws_model_month WHERE model = '{pick}' "
        "AND year >= 2022 GROUP BY date ORDER BY date"
    )
    st.plotly_chart(px.line(traj, x="date", y="units", title=pick), use_container_width=True)

with tab_seg:
    seg = query(
        """SELECT segment5, date, SUM(wholesale) AS units FROM ws_segment_month
           WHERE year >= 2022 GROUP BY segment5, date ORDER BY date"""
    )
    st.plotly_chart(
        px.area(seg, x="date", y="units", color="segment5", groupnorm="percent",
                title="Segment share of wholesale"),
        use_container_width=True,
    )

with tab_city:
    yr2 = st.slider("Year", 2022, 2026, 2025, key="c_yr")
    cities = query(
        f"""SELECT city, state_code, SUM(qty) AS units FROM wholesale
            WHERE year = {yr2} GROUP BY city, state_code ORDER BY units DESC LIMIT 30"""
    )
    st.plotly_chart(
        px.bar(cities, x="units", y="city", color="state_code", orientation="h", height=800),
        use_container_width=True,
    )

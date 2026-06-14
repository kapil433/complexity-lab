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

mapping = query(
    """
    SELECT SUM(qty) AS units,
           SUM(qty) FILTER (WHERE state_code IS NOT NULL) AS mapped_units,
           100 * SUM(qty) FILTER (WHERE state_code IS NOT NULL) / SUM(qty) AS mapped_pct
    FROM wholesale
    WHERE coverage = 'full'
    """
).iloc[0]
st.info(
    f"Coverage regime: full industry from April 2022. City-to-state mapping covers "
    f"{mapping['mapped_pct']:.2f}% of full-era volume; "
    f"{mapping['units'] - mapping['mapped_units']:,.0f} units remain unmapped."
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
    rw["gap"] = rw["wholesale"] - rw["retail"]
    rw["rolling_stock_build"] = rw["gap"].rolling(6, min_periods=1).sum()
    st.plotly_chart(
        px.line(
            rw,
            x="date",
            y=["gap", "rolling_stock_build"],
            title="Channel cockpit: monthly gap and six-month stock-build estimate",
        ),
        width="stretch",
    )
    episodes = rw.assign(
        episode=rw["ws_retail_ratio"].map(
            lambda value: "inventory build" if value > 1.08 else "depletion" if value < 0.92 else "balanced"
        )
    )
    st.dataframe(
        episodes[episodes["episode"] != "balanced"][
            ["date", "retail", "wholesale", "ws_retail_ratio", "episode"]
        ].tail(18),
        hide_index=True,
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
        f"""SELECT model, maker, segment5, SUM(qty) AS units FROM wholesale
            WHERE year = {yr} AND coverage = 'full'
            GROUP BY model, maker, segment5 ORDER BY units DESC LIMIT {top_n}"""
    )
    fig_m = px.bar(models, x="units", y="model", color="maker", orientation="h",
                   height=200 + 22 * top_n, title=f"Top models by dispatches, {yr}")
    st.plotly_chart(indian_axis(fig_m, axis="x"), width="stretch")
    st.plotly_chart(
        px.treemap(
            models,
            path=["maker", "segment5", "model"],
            values="units",
            title=f"OEM/model portfolio, {yr}",
        ),
        width="stretch",
    )
    pick = st.selectbox("Model trajectory", sorted(query(
        "SELECT DISTINCT model FROM wholesale WHERE coverage = 'full'")["model"]))
    traj = query(
        f"SELECT date, SUM(qty) units FROM wholesale WHERE model = '{pick}' "
        "AND coverage = 'full' GROUP BY date ORDER BY date"
    )
    st.plotly_chart(px.line(traj, x="date", y="units", title=pick), width="stretch")
    if not traj.empty:
        peak = traj.loc[traj["units"].idxmax()]
        st.caption(
            f"Lifecycle peak: {peak['date']} at {peak['units']:,.0f} dispatches. "
            "This is a descriptive peak, not a declared product discontinuation."
        )

with tab_seg:
    seg = query(
        """SELECT segment5, date, SUM(qty) AS units FROM wholesale
           WHERE coverage = 'full' GROUP BY segment5, date ORDER BY date"""
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
        "mixed-fuel nameplates remain inseparable from other powertrains."
    )
    ev = query(
        "SELECT date, maker, SUM(wholesale) AS units FROM ws_ev_month "
        "WHERE date >= '2022-04-01' GROUP BY date, maker ORDER BY date"
    )
    fig_ev = px.area(ev, x="date", y="units", color="maker",
                     title="EV-only nameplate dispatches by OEM (units/month)")
    st.plotly_chart(indian_axis(fig_ev, max_value=float(ev.groupby("date")["units"].sum().max())),
                    width="stretch")
    tiers = query(
        """
        SELECT CASE
                 WHEN ev_only = 1 THEN 'EV-only nameplate'
                 WHEN fuel_variants IS NULL THEN 'unclassified'
                 ELSE 'mixed-fuel / quantity unknown'
               END AS metadata_tier,
               COUNT(DISTINCT model) AS models,
               SUM(qty) AS dispatches
        FROM wholesale
        WHERE coverage = 'full'
        GROUP BY metadata_tier
        ORDER BY dispatches DESC
        """
    )
    st.dataframe(tiers, hide_index=True, width="stretch")
    ev_states = query(
        "SELECT state_code, SUM(wholesale) AS units FROM ws_ev_month "
        "WHERE state_code IS NOT NULL AND date >= '2024-01-01' GROUP BY state_code "
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
            WHERE year = {yr2} AND coverage = 'full'
            GROUP BY city, state_code ORDER BY units DESC LIMIT 30"""
    )
    st.plotly_chart(
        px.bar(cities, x="units", y="city", color="state_code", orientation="h", height=800),
        width="stretch",
    )
    unmapped = query(
        f"""
        SELECT city, SUM(qty) AS units
        FROM wholesale
        WHERE year = {yr2} AND coverage = 'full' AND state_code IS NULL
        GROUP BY city
        ORDER BY units DESC
        LIMIT 20
        """
    )
    st.markdown("#### Largest unmapped cities")
    st.dataframe(unmapped, hide_index=True, width="stretch")

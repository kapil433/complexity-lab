"""Macro Dashboard: the market at a glance — KPIs, share shifts, fuel penetration,
channel health. Blueprint §7.6 P0 page."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, load_geojson, query, render_app_shell, render_card

from complexity_lab.viz import (
    add_event_markers,
    diverging_bar,
    indian_axis,
    kpi_value,
    load_events,
    ratio_band_chart,
)

st.set_page_config(page_title="Market Pulse | Complexity Lab", layout="wide")
page = render_app_shell(
    "Market Pulse",
    section="Observe",
    description="National scale, fuel transition, OEM concentration, and state divergence.",
    limitations=(
        "State reference variables may be estimated, proxied, or available only as snapshots.",
        "Channel health appears only when proprietary wholesale data is present locally.",
    ),
)
render_card("descriptive-baseline")
st.info(
    f"Completeness: Vahan is observed through {page.cutoff.latest_period}; "
    f"{page.cutoff.latest_complete_year} is the latest complete calendar year. "
    "Partial 2026 observations are excluded from full-year comparisons."
)

national = query("SELECT * FROM panel_state_year WHERE state_code = 'ALL' ORDER BY year")
latest = min(page.filters.year_end, page.cutoff.latest_complete_year)
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
period_mode, display_mode = st.columns(2)
period = period_mode.selectbox(
    "Period mode",
    ["Month", "Rolling quarter", "YTD", "Rolling 12 months", "Calendar year", "Financial year"],
)
display = display_mode.radio("Display", ["Absolute units", "Share"], horizontal=True)
fuel_columns = ["petrol_regs", "diesel_regs", "cng_regs", "ev_regs", "hybrid_regs"]
trend = monthly[["date", "year", "month", "fy", "total_regs", *fuel_columns]].copy()
if period == "Rolling quarter":
    trend[fuel_columns + ["total_regs"]] = trend[fuel_columns + ["total_regs"]].rolling(
        3, min_periods=3
    ).sum()
elif period == "Rolling 12 months":
    trend[fuel_columns + ["total_regs"]] = trend[fuel_columns + ["total_regs"]].rolling(
        12, min_periods=12
    ).sum()
elif period == "YTD":
    trend[fuel_columns + ["total_regs"]] = trend.groupby("year")[
        fuel_columns + ["total_regs"]
    ].cumsum()
elif period == "Calendar year":
    trend = trend.groupby("year", as_index=False)[fuel_columns + ["total_regs"]].sum()
    trend["date"] = pd.to_datetime(trend["year"].astype(str) + "-12-01")
elif period == "Financial year":
    trend = trend.groupby("fy", as_index=False)[fuel_columns + ["total_regs"]].sum()
    trend["date"] = pd.to_datetime(trend["fy"].str[:4] + "-04-01")
trend["other_unclassified"] = trend["total_regs"] - trend[fuel_columns].sum(axis=1)
plot_columns = [*fuel_columns, "other_unclassified"]
if display == "Share":
    trend[plot_columns] = trend[plot_columns].div(trend["total_regs"], axis=0)
fig = px.area(
    trend,
    x="date",
    y=plot_columns,
    groupnorm=None,
    title=f"{period}: observed fuel structure ({display.lower()})",
    labels={"value": "share" if display == "Share" else "registrations", "variable": "fuel"},
)
fig.for_each_trace(lambda t: t.update(name=t.name.replace("_regs", "").replace("hybrid", "strong hybrid").title()))
if display == "Share":
    fig.update_yaxes(tickformat=".0%")
else:
    indian_axis(fig, max_value=float(trend["total_regs"].max()))
if st.checkbox("Show policy events", value=True):
    fig = add_event_markers(fig, load_events(get_connection()), max_labels=12)
st.plotly_chart(fig, width="stretch")

seasonal = monthly.copy()
seasonal["month_factor"] = seasonal.groupby("month")["total_regs"].transform("mean")
seasonal["seasonally_adjusted"] = (
    seasonal["total_regs"] / seasonal["month_factor"] * seasonal["total_regs"].mean()
)
st.plotly_chart(
    px.line(
        seasonal,
        x="date",
        y=["total_regs", "seasonally_adjusted"],
        title="Observed and simple month-factor seasonally adjusted registrations",
    ),
    width="stretch",
)

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
        width="stretch",
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
    st.plotly_chart(figms, width="stretch")

st.subheader("Contribution to growth")
contribution_tabs = st.tabs(["States", "OEMs", "Fuels"])
with contribution_tabs[0]:
    state_contrib = get_connection().execute(
        """
        WITH annual AS (
            SELECT state_code, state_name, year, total_regs
            FROM panel_state_year
            WHERE state_code <> 'ALL' AND year IN (?, ?)
        )
        SELECT state_code, MAX(state_name) AS state_name,
               MAX(total_regs) FILTER (WHERE year = ?) -
               MAX(total_regs) FILTER (WHERE year = ?) AS contribution
        FROM annual
        GROUP BY state_code
        ORDER BY ABS(contribution) DESC
        LIMIT 15
        """,
        [latest - 1, latest, latest, latest - 1],
    ).df()
    st.plotly_chart(
        px.bar(
            state_contrib.sort_values("contribution"),
            x="contribution",
            y="state_name",
            orientation="h",
            color="contribution",
            color_continuous_scale="RdBu",
            title=f"State contribution to national volume change, {latest - 1} to {latest}",
        ),
        width="stretch",
    )
with contribution_tabs[1]:
    oem_contrib = get_connection().execute(
        """
        WITH annual AS (
            SELECT maker, year, SUM("count") AS regs
            FROM registrations
            WHERE state_code = 'ALL' AND year IN (?, ?)
            GROUP BY maker, year
        )
        SELECT maker,
               MAX(regs) FILTER (WHERE year = ?) -
               MAX(regs) FILTER (WHERE year = ?) AS contribution
        FROM annual
        GROUP BY maker
        ORDER BY ABS(contribution) DESC
        LIMIT 15
        """,
        [latest - 1, latest, latest, latest - 1],
    ).df()
    st.plotly_chart(
        px.bar(
            oem_contrib.sort_values("contribution"),
            x="contribution",
            y="maker",
            orientation="h",
            color="contribution",
            color_continuous_scale="RdBu",
            title="OEM contribution to growth",
        ),
        width="stretch",
    )
with contribution_tabs[2]:
    fuel_contrib = pd.DataFrame(
        {
            "fuel": fuel_columns,
            "contribution": [row[column] - prev[column] for column in fuel_columns],
        }
    )
    st.plotly_chart(
        px.bar(
            fuel_contrib.sort_values("contribution"),
            x="contribution",
            y="fuel",
            orientation="h",
            color="contribution",
            color_continuous_scale="RdBu",
            title="Fuel contribution to growth",
        ),
        width="stretch",
    )

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
st.plotly_chart(figc, width="stretch")

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
st.plotly_chart(fig_hm, width="stretch")

# ---- channel health (local wholesale data) ---------------------------------
tables = {r[0] for r in get_connection().execute("SHOW TABLES").fetchall()}
if "wholesale" in tables:
    st.subheader("Channel health (wholesale / retail)")
    rw = query("SELECT * FROM retail_wholesale_month ORDER BY date")
    st.plotly_chart(
        ratio_band_chart(rw, "date", "ws_retail_ratio",
                         title="Wholesale/retail ratio — green band = healthy channel"),
        width="stretch",
    )
    rw["gap"] = rw["wholesale"] - rw["retail"]
    rw["episode"] = rw["ws_retail_ratio"].map(
        lambda value: "build" if value > 1.08 else "depletion" if value < 0.92 else "balanced"
    )
    st.dataframe(
        rw[rw["episode"] != "balanced"][
            ["date", "retail", "wholesale", "gap", "ws_retail_ratio", "episode"]
        ].tail(18),
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("Channel health needs the local wholesale data — `uv run lab wholesale`.")

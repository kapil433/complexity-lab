"""Market Brief: the context-aware entry point to the personal complexity lab."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from common import get_connection, render_app_shell, render_finding

from complexity_lab.data.access import FUEL_COLUMNS, market_annual, market_monthly, state_snapshot
from complexity_lab.data.intelligence import largest_moves
from complexity_lab.persistence import list_saved_views, list_watchlist
from complexity_lab.viz import indian_axis, kpi_value

st.set_page_config(page_title="Market Brief | Complexity Lab", page_icon="CL", layout="wide")

page = render_app_shell(
    "Market Brief",
    section="Observe",
    description=(
        "A personal complexity lab for India's passenger-vehicle market, grounded in "
        "actual Vahan registrations and clearly bounded wholesale evidence."
    ),
    limitations=(
        "The latest calendar year is partial and is excluded under the default period policy.",
        "Reference variables retain their own dates and quality labels; sparse snapshots are not time series.",
        "Wholesale has no fuel cut. Model metadata never becomes observed fuel volume.",
    ),
)

monthly = market_monthly(get_connection(), page.filters)
annual = market_annual(get_connection(), page.filters)
if monthly.empty or annual.empty:
    st.warning("No observations match this research context. Broaden the sidebar filters.")
    st.stop()

latest = annual.iloc[-1]
previous = annual.iloc[-2] if len(annual) > 1 else None
rolling = monthly.tail(12)["total_regs"].sum() if len(monthly) >= 12 else monthly["total_regs"].sum()
latest_month = pd.Timestamp(monthly["date"].max()).strftime("%B %Y")

fuel_shares = {
    fuel: latest[column] / latest["total_regs"]
    for fuel, column in FUEL_COLUMNS.items()
    if column in latest and latest["total_regs"] > 0
}
leading_fuel = max(fuel_shares, key=fuel_shares.get) if fuel_shares else "selected market"
growth = latest.get("yoy_growth")

state_codes = list(page.filters.states) or ["ALL"]
placeholders = ", ".join("?" for _ in state_codes)
oem_filter = ""
params: list[object] = [*state_codes, int(latest["year"])]
if page.filters.oems:
    oem_placeholders = ", ".join("?" for _ in page.filters.oems)
    oem_filter = f" AND maker IN ({oem_placeholders})"
    params.extend(page.filters.oems)
leader = get_connection().execute(
    f"""
    SELECT maker, SUM("count") AS regs
    FROM registrations
    WHERE state_code IN ({placeholders}) AND year = ? {oem_filter}
    GROUP BY maker
    ORDER BY regs DESC
    LIMIT 1
    """,
    params,
).fetchone()
leading_oem = leader[0] if leader else "Not available"

tables = {row[0] for row in get_connection().execute("SHOW TABLES").fetchall()}
ws_ratio = None
if "retail_wholesale_month" in tables:
    ws_row = get_connection().execute(
        """
        SELECT ws_retail_ratio
        FROM retail_wholesale_month
        WHERE ws_retail_ratio IS NOT NULL
        ORDER BY date DESC
        LIMIT 1
        """
    ).fetchone()
    ws_ratio = ws_row[0] if ws_row else None

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Latest observed month", page.cutoff.latest_period)
c2.metric("Rolling 12 months", kpi_value(rolling), latest_month)
c3.metric(
    "EV share",
    kpi_value(fuel_shares.get("EV"), "pct") if "EV" in fuel_shares else "Filtered out",
)
c4.metric(
    "CNG share",
    kpi_value(fuel_shares.get("CNG"), "pct") if "CNG" in fuel_shares else "Filtered out",
)
c5.metric("Leading OEM", leading_oem)
c6.metric("Latest wholesale / retail", f"{ws_ratio:.2f}" if ws_ratio is not None else "Local only")

comparison = ""
if previous is not None and pd.notna(growth):
    comparison = (
        f"Registrations changed {growth:+.1%} versus {int(previous['year'])}. "
    )
render_finding(
    comparison
    + f"{leading_fuel} is the largest fuel in the current scope"
    + (
        f" at {fuel_shares[leading_fuel]:.1%} of registrations."
        if leading_fuel in fuel_shares
        else "."
    )
)

st.markdown("#### Five-line market brief")
brief_lines = [
    f"1. **Scale:** {kpi_value(latest['total_regs'])} registrations in {int(latest['year'])}; "
    f"{kpi_value(rolling)} over the latest 12 observed months.",
    f"2. **Growth:** {growth:+.1%} versus {int(previous['year'])}."
    if previous is not None and pd.notna(growth)
    else "2. **Growth:** no like-for-like prior period in the selected context.",
    "3. **Fuel shift:** "
    + ", ".join(
        f"{fuel} {share:.1%}"
        for fuel, share in sorted(fuel_shares.items(), key=lambda item: item[1], reverse=True)[:3]
    )
    + ".",
    f"4. **OEM movement:** {leading_oem} leads the selected market.",
    (
        f"5. **Channel:** latest full-era wholesale/retail ratio is {ws_ratio:.2f}."
        if ws_ratio is not None
        else "5. **Channel:** proprietary wholesale is absent; retail analysis remains complete."
    ),
]
st.markdown("\n".join(brief_lines))

st.subheader("The observed market trajectory")
fuel_columns = [column for column in FUEL_COLUMNS.values() if column in monthly]
plot = monthly[["date", *fuel_columns]].melt(
    id_vars="date",
    var_name="fuel",
    value_name="registrations",
)
labels = {column: fuel for fuel, column in FUEL_COLUMNS.items()}
plot["fuel"] = plot["fuel"].map(labels)
fig = px.area(
    plot,
    x="date",
    y="registrations",
    color="fuel",
    title="Monthly registrations by fuel within the selected context",
    labels={"registrations": "registrations", "fuel": ""},
)
indian_axis(fig, max_value=float(monthly["total_regs"].max()))
fig.add_vline(
    x=pd.Timestamp(f"{page.cutoff.latest_complete_year}-12-31").timestamp() * 1000,
    line_dash="dot",
    line_color="#E4572E",
    annotation_text="complete-year boundary",
)
st.plotly_chart(fig, width="stretch")

snapshot = state_snapshot(
    get_connection(),
    min(page.filters.year_end, page.cutoff.latest_complete_year),
    page.filters.states,
)
if not snapshot.empty:
    left, right = st.columns([1.35, 1])
    with left:
        movers = snapshot.dropna(subset=["yoy_growth"]).nlargest(10, "yoy_growth").copy()
        movers["growth_pct"] = movers["yoy_growth"] * 100
        st.plotly_chart(
            px.bar(
                movers.sort_values("growth_pct"),
                x="growth_pct",
                y="state_name",
                orientation="h",
                title=f"Fastest state growth in {int(latest['year'])}",
                labels={"growth_pct": "YoY growth (%)", "state_name": ""},
            ),
            width="stretch",
        )
    with right:
        st.markdown("#### Read the movement")
        st.dataframe(
            snapshot.head(8)[["state_name", "total_regs", "yoy_growth", "ev_share"]].style.format(
                {"total_regs": "{:,.0f}", "yoy_growth": "{:+.1%}", "ev_share": "{:.1%}"}
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Growth and EV share are observed registration measures. They do not identify causes."
        )

moves = largest_moves(get_connection(), int(latest["year"]))
st.subheader("Largest moves")
tab_states, tab_oems, tab_fuels, tab_models = st.tabs(["States", "OEMs", "Fuels", "Models"])
with tab_states:
    st.dataframe(moves["states"], hide_index=True, width="stretch")
with tab_oems:
    st.dataframe(moves["oems"], hide_index=True, width="stretch")
with tab_fuels:
    if previous is None:
        st.info("A prior year is required for fuel-share movement.")
    else:
        fuel_moves = pd.DataFrame(
            [
                {
                    "fuel": fuel,
                    "share": fuel_shares.get(fuel),
                    "change_pp": (
                        latest.get(column, 0) / latest["total_regs"]
                        - previous.get(column, 0) / previous["total_regs"]
                    )
                    * 100,
                }
                for fuel, column in FUEL_COLUMNS.items()
                if column in latest
            ]
        ).sort_values("change_pp", key=abs, ascending=False)
        st.dataframe(fuel_moves, hide_index=True, width="stretch")
with tab_models:
    if "wholesale" not in tables:
        st.info("Model movement requires local proprietary wholesale data.")
    else:
        model_moves = get_connection().execute(
            """
            WITH annual AS (
                SELECT model, year, SUM(qty) AS units
                FROM wholesale
                WHERE coverage = 'full' AND year IN (?, ?)
                GROUP BY model, year
            ),
            pivoted AS (
                SELECT model,
                       MAX(units) FILTER (WHERE year = ?) AS current_units,
                       MAX(units) FILTER (WHERE year = ?) AS prior_units
                FROM annual
                GROUP BY model
            )
            SELECT *, current_units - COALESCE(prior_units, 0) AS unit_change
            FROM pivoted
            ORDER BY ABS(unit_change) DESC
            LIMIT 15
            """,
            [int(latest["year"]) - 1, int(latest["year"]), int(latest["year"]), int(latest["year"]) - 1],
        ).df()
        st.dataframe(model_moves, hide_index=True, width="stretch")
        st.warning("Wholesale has no fuel cut. Model movement is total dispatch volume.")

events = get_connection().execute(
    """
    SELECT date, category, label, state_code
    FROM ref_policy_events_canonical
    ORDER BY date DESC
    LIMIT 8
    """
).df()
st.subheader("Recent policy and data events")
st.dataframe(events, hide_index=True, width="stretch")
st.warning(
    "Strong Hybrid Vahan history has a 2024 classification break. Do not treat the "
    "pre/post series as one continuous observed adoption curve."
)

watchlist = list_watchlist()
saved = list_saved_views()
left_memory, right_memory = st.columns(2)
with left_memory:
    st.markdown("#### Pinned watchlist")
    if watchlist.empty:
        st.caption("Pin states and OEMs from their Intelligence pages.")
    else:
        st.dataframe(watchlist[["item_type", "label", "notes"]].head(8), hide_index=True)
with right_memory:
    st.markdown("#### Recent saved views")
    if saved.empty:
        st.caption("Saved views will appear here.")
    else:
        st.dataframe(saved[["title", "page", "data_cutoff", "created_at"]].head(8), hide_index=True)

st.subheader("Continue the investigation")
n1, n2, n3, n4 = st.columns(4)
with n1:
    st.markdown("**Compare states**  \nOpen a state dossier with peers and context.")
    st.page_link("pages/10_State_Intelligence.py", label="Open State Intelligence")
with n2:
    st.markdown("**Inspect an OEM**  \nConnect retail strength to portfolio structure.")
    st.page_link("pages/11_OEM_Model_Intelligence.py", label="Open OEM Intelligence")
with n3:
    st.markdown("**Test a driver**  \nFrame and save an empirical hypothesis.")
    st.page_link("pages/4_Hypothesis_Tester.py", label="Open Causal Lab")
with n4:
    st.markdown("**Build a forecast**  \nBenchmark models and save a vintage.")
    st.page_link("pages/7_Forecast_Studio.py", label="Open Forecast Studio")

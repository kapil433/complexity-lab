"""Market Brief: the context-aware entry point to the personal complexity lab."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from common import get_connection, render_app_shell, render_finding

from complexity_lab.data.access import FUEL_COLUMNS, market_annual, market_monthly, state_snapshot
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

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Latest complete year", int(latest["year"]))
c2.metric("Registrations", kpi_value(latest["total_regs"]))
c3.metric("Rolling 12 months", kpi_value(rolling), latest_month)
c4.metric(
    "EV share",
    kpi_value(fuel_shares.get("EV"), "pct") if "EV" in fuel_shares else "Filtered out",
)
c5.metric(
    "YoY growth",
    kpi_value(growth, "pct") if pd.notna(growth) else "Not available",
)

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

st.subheader("Continue the investigation")
n1, n2, n3, n4 = st.columns(4)
with n1:
    st.markdown("**Market Pulse**  \nTrack fuel, OEM, concentration, and state shifts.")
    st.page_link("pages/0_Macro_Dashboard.py", label="Open Market Pulse")
with n2:
    st.markdown("**Compare and Explore**  \nMove between maps, time series, and reference context.")
    st.page_link("pages/1_Explorer.py", label="Open Explorer")
with n3:
    st.markdown("**Wholesale and Channel**  \nInspect dispatches with the coverage break kept visible.")
    st.page_link("pages/5_Wholesale.py", label="Open Wholesale")
with n4:
    st.markdown("**Reference Lab**  \nAudit every contextual variable, source, and unavailable field.")
    st.page_link("pages/9_Reference_Lab.py", label="Open Reference Lab")

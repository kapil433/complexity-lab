"""State Intelligence: one research profile per state."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query, render_app_shell, render_finding

from complexity_lab.complexity.transitions import classify_regimes
from complexity_lab.data.intelligence import state_profile
from complexity_lab.persistence import add_watchlist_item
from complexity_lab.viz import indian_axis, kpi_value

st.set_page_config(page_title="State Intelligence | Complexity Lab", layout="wide")
page = render_app_shell(
    "State Intelligence",
    section="Observe",
    description=(
        "A complete state dossier: market size, fuel transition, OEM strength, peers, "
        "context, policy events, regimes, and local wholesale evidence when available."
    ),
    limitations=(
        "Peer groups are descriptive similarity sets, not causal controls.",
        "Andhra Pradesh contains the combined Vahan history; Telangana is not separately observed.",
        "Wholesale state joins block AP/Telangana ambiguity and wholesale has no fuel cut.",
    ),
)

states = query(
    "SELECT state_code, state_name FROM dim_state WHERE state_code <> 'ALL' ORDER BY state_name"
)
default_code = page.filters.states[0] if page.filters.states else "MH"
state_code = st.selectbox(
    "State",
    states["state_code"],
    index=int((states["state_code"] == default_code).idxmax()),
    format_func=lambda code: states.set_index("state_code").loc[code, "state_name"],
)
state_name = states.set_index("state_code").loc[state_code, "state_name"]
profile = state_profile(get_connection(), state_code, page.cutoff.latest_complete_year)
annual = profile["annual"]
latest = annual.iloc[-1]
previous = annual.iloc[-2]

if state_code in {"AP", "TS"}:
    st.error(
        "AP/Telangana boundary: Vahan history is combined under Andhra Pradesh. "
        "No separate Telangana trend or direct state-level wholesale-retail join is shown."
    )

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Registrations", kpi_value(latest["total_regs"]), f"{latest['yoy_growth']:+.1%} YoY")
c2.metric("EV share", f"{latest['ev_share']:.1%}", f"{latest['ev_share_chg_pp']:+.2f} pp")
c3.metric("CNG share", f"{latest['cng_share']:.1%}", f"{latest['cng_share_chg_pp']:+.2f} pp")
c4.metric("Leading OEM", profile["oems"].query("year == @latest.year").iloc[0]["maker"])
c5.metric("OEM concentration", f"{latest['hhi_oem']:,.0f}")
render_finding(
    f"{state_name} registrations changed {latest['yoy_growth']:+.1%} in {int(latest['year'])}. "
    f"EV share moved {latest['ev_share_chg_pp']:+.2f} pp and CNG share "
    f"{latest['cng_share_chg_pp']:+.2f} pp."
)

if st.button(f"Add {state_name} to watchlist"):
    add_watchlist_item(item_type="state", item_key=state_code, label=state_name)
    st.success("State added to the local watchlist.")

tab_market, tab_oem, tab_context, tab_regime, tab_wholesale = st.tabs(
    ["Market and fuel", "OEM leaderboard", "Peers and context", "Regimes and events", "Wholesale"]
)

with tab_market:
    left, right = st.columns(2)
    with left:
        fig = px.line(
            annual,
            x="year",
            y="total_regs",
            markers=True,
            title=f"{state_name} annual registrations",
        )
        st.plotly_chart(indian_axis(fig), width="stretch")
    with right:
        mix = annual.melt(
            id_vars="year",
            value_vars=["petrol_regs", "diesel_regs", "cng_regs", "ev_regs", "hybrid_regs"],
            var_name="fuel",
            value_name="registrations",
        )
        st.plotly_chart(
            px.area(
                mix,
                x="year",
                y="registrations",
                color="fuel",
                groupnorm="fraction",
                title="Observed fuel mix",
            ),
            width="stretch",
        )

with tab_oem:
    latest_oems = profile["oems"].query("year == @latest.year").head(15).copy()
    latest_oems["share_pct"] = latest_oems["share"] * 100
    st.plotly_chart(
        px.bar(
            latest_oems.sort_values("share_pct"),
            x="share_pct",
            y="maker",
            orientation="h",
            color="share_chg_pp",
            color_continuous_scale="RdBu",
            title=f"OEM leaderboard and share movement, {int(latest['year'])}",
        ),
        width="stretch",
    )
    st.dataframe(latest_oems, hide_index=True, width="stretch")

with tab_context:
    context = profile["context"]
    if not context.empty:
        row = context.iloc[0]
        cards = st.columns(5)
        cards[0].metric("Real income / capita", kpi_value(row["real_pc_income_inr"]))
        cards[1].metric("Urban share basis", f"{row['urban_pct']:.1f}%")
        cards[2].metric("EV chargers snapshot", f"{row['ev_chargers_2025']:,.0f}")
        cards[3].metric("CNG stations snapshot", f"{row['cng_stations_2024']:,.0f}")
        cards[4].metric("Broad credit / capita", kpi_value(row["broad_credit_per_capita_inr"]))
    st.markdown("#### Peer states")
    st.dataframe(
        profile["peers"][
            ["state_name", "zone", "real_pc_income_inr", "urban_pct", "peer_distance"]
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Income and urbanization retain their source quality. Charger and CNG values are dated snapshots."
    )

with tab_regime:
    panel = query("SELECT * FROM panel_state_year WHERE state_code <> 'ALL'")
    regimes = classify_regimes(panel)
    state_regimes = regimes[regimes["state_code"] == state_code]
    st.plotly_chart(
        px.timeline(
            state_regimes.assign(end=state_regimes["year"] + 1),
            x_start="year",
            x_end="end",
            y="state_code",
            color="regime",
            title="Rule-based fuel-regime history",
        ),
        width="stretch",
    )
    st.dataframe(
        profile["events"][["date", "category", "label", "state_code", "possible_overlap"]],
        hide_index=True,
        width="stretch",
    )
    st.caption("Events are candidate context, not causal attribution.")

with tab_wholesale:
    tables = {row[0] for row in get_connection().execute("SHOW TABLES").fetchall()}
    if "wholesale" not in tables:
        st.info("Local proprietary wholesale data is not available in this deployment.")
    elif state_code in {"AP", "TS"}:
        st.warning("State-level wholesale-retail comparison is blocked for AP/Telangana.")
    else:
        ws = get_connection().execute(
            """
            SELECT date, wholesale
            FROM ws_state_month
            WHERE state_code = ? AND date >= '2022-04-01'
            ORDER BY date
            """,
            [state_code],
        ).df()
        st.plotly_chart(
            px.line(ws, x="date", y="wholesale", title="Full-coverage wholesale dispatches"),
            width="stretch",
        )
        st.warning("Wholesale has no fuel cut; this is total dispatch volume only.")

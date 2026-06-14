"""OEM and Model Intelligence: retail structure plus local wholesale portfolio."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query, render_app_shell, render_finding

from complexity_lab.data.intelligence import oem_profile
from complexity_lab.persistence import add_watchlist_item
from complexity_lab.viz import kpi_value

st.set_page_config(page_title="OEM and Model Intelligence | Complexity Lab", layout="wide")
page = render_app_shell(
    "OEM and Model Intelligence",
    section="Observe",
    description=(
        "Follow an OEM from national retail share to state strength, observed Vahan fuel mix, "
        "network position, and local wholesale model/segment portfolio."
    ),
    limitations=(
        "Vahan fuel mix is observed registrations.",
        "Wholesale has no fuel cut; wholesale portfolio views are model and segment dispatches only.",
        "Cross-source OEM comparisons use normalized maker mappings and the full wholesale era.",
    ),
)

makers = query(
    """
    SELECT DISTINCT maker
    FROM registrations
    WHERE state_code = 'ALL'
    ORDER BY maker
    """
)["maker"].tolist()
default_maker = page.filters.oems[0] if page.filters.oems else "Maruti Suzuki"
maker = st.selectbox(
    "OEM",
    makers,
    index=makers.index(default_maker) if default_maker in makers else 0,
)
profile = oem_profile(get_connection(), maker, page.cutoff.latest_complete_year)
annual = profile["annual"]
latest = annual.iloc[-1]
previous = annual.iloc[-2]

state_latest = profile["states"].query("year == @latest.year")
top_state = state_latest.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Retail registrations", kpi_value(latest["regs"]))
c2.metric("National share", f"{latest['share']:.1%}", f"{latest['share'] - previous['share']:+.1%}")
c3.metric("Strongest state share", f"{top_state['share']:.1%}", top_state["state_name"])
c4.metric("States in top 3", int((state_latest["rnk"] <= 3).sum()))
render_finding(
    f"{maker} held {latest['share']:.1%} of national registrations in {int(latest['year'])}, "
    f"a {(latest['share'] - previous['share']) * 100:+.2f} pp change from the prior year."
)
if st.button(f"Add {maker} to watchlist"):
    add_watchlist_item(item_type="oem", item_key=maker, label=maker)
    st.success("OEM added to the local watchlist.")

tab_retail, tab_states, tab_fuel, tab_wholesale = st.tabs(
    ["Retail trajectory", "State strength", "Vahan fuel mix", "Wholesale models and segments"]
)
with tab_retail:
    fig = px.line(
        annual,
        x="year",
        y=["regs", "share"],
        markers=True,
        title=f"{maker}: registrations and national share",
    )
    st.plotly_chart(fig, width="stretch")

with tab_states:
    plot = state_latest.head(20).sort_values("share")
    st.plotly_chart(
        px.bar(
            plot,
            x="share",
            y="state_name",
            orientation="h",
            color="rnk",
            title=f"State strength, {int(latest['year'])}",
        ),
        width="stretch",
    )
    st.dataframe(state_latest.head(30), hide_index=True, width="stretch")

with tab_fuel:
    fuels = profile["fuels"].copy()
    st.plotly_chart(
        px.area(
            fuels,
            x="year",
            y="regs",
            color="fuel",
            groupnorm="fraction",
            title="Observed Vahan registration fuel mix",
        ),
        width="stretch",
    )

with tab_wholesale:
    tables = {row[0] for row in get_connection().execute("SHOW TABLES").fetchall()}
    if "wholesale" not in tables:
        st.info("Local proprietary wholesale data is not available in this deployment.")
    else:
        models = get_connection().execute(
            """
            SELECT model, segment5, SUM(qty) AS units
            FROM wholesale
            WHERE maker_vahan = ? AND coverage = 'full'
            GROUP BY model, segment5
            ORDER BY units DESC
            """,
            [maker],
        ).df()
        if models.empty:
            st.warning("No normalized wholesale portfolio matched this OEM.")
        else:
            st.plotly_chart(
                px.treemap(
                    models,
                    path=["segment5", "model"],
                    values="units",
                    title="Full-era wholesale model portfolio",
                ),
                width="stretch",
            )
            trajectories = get_connection().execute(
                """
                SELECT date, model, SUM(qty) AS units
                FROM wholesale
                WHERE maker_vahan = ? AND coverage = 'full'
                  AND model IN (
                      SELECT model
                      FROM wholesale
                      WHERE maker_vahan = ? AND coverage = 'full'
                      GROUP BY model ORDER BY SUM(qty) DESC LIMIT 8
                  )
                GROUP BY date, model
                ORDER BY date
                """,
                [maker, maker],
            ).df()
            st.plotly_chart(
                px.line(trajectories, x="date", y="units", color="model", title="Model ramp curves"),
                width="stretch",
            )
            st.warning("Wholesale has no fuel cut. These are model dispatches, not fuel volumes.")

"""Reference Lab: inspect covariates, provenance, coverage, and policy context."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_app_shell

st.set_page_config(page_title="Reference Lab | Complexity Lab", layout="wide")
page = render_app_shell(
    "Reference Lab",
    section="System",
    description=(
        "Audit the contextual data, provenance, coverage, quality, and evidence "
        "that remains unavailable."
    ),
    limitations=(
        "Reference data are context, not decoration or automatic causal controls.",
        "Sparse infrastructure snapshots are not presented as annual histories.",
        "Wholesale has no fuel cut.",
    ),
)

availability = query(
    """SELECT dataset, status, geography, time_coverage, quality_summary,
              approved_use, not_available, row_count
       FROM reference_availability
       ORDER BY CASE status WHEN 'usable' THEN 1 WHEN 'constrained' THEN 2 ELSE 3 END,
                dataset"""
)

usable = int((availability["status"] == "usable").sum())
constrained = int((availability["status"] == "constrained").sum())
unavailable = int((availability["status"] == "unavailable").sum())
c1, c2, c3 = st.columns(3)
c1.metric("Usable references", usable)
c2.metric("Constrained references", constrained)
c3.metric("Unavailable references", unavailable)

with st.expander("Full reference coverage contract"):
    st.dataframe(availability, width="stretch", hide_index=True)

tab_macro, tab_infra, tab_policy, tab_gaps = st.tabs(
    ["Macro and population", "Infrastructure", "Tax and policy", "Known gaps"]
)

with tab_macro:
    state_dim = query(
        "SELECT state_code, state_name FROM dim_state WHERE state_code <> 'ALL' ORDER BY state_name"
    )
    selected_names = st.multiselect(
        "States",
        state_dim["state_name"].tolist(),
        default=["Delhi", "Karnataka", "Maharashtra", "Tamil Nadu", "Uttar Pradesh"],
    )
    selected_codes = state_dim.loc[
        state_dim["state_name"].isin(selected_names), "state_code"
    ].tolist()
    if selected_codes:
        codes_sql = ", ".join(f"'{code}'" for code in selected_codes)
        population = query(
            f"""SELECT p.year, d.state_name, p.population_mn,
                       p.urban_population_mn, p.rural_population_mn, p.quality
                FROM ref_state_population_annual p
                JOIN dim_state d USING (state_code)
                WHERE p.state_code IN ({codes_sql})
                ORDER BY p.year, d.state_name"""
        )
        st.plotly_chart(
            px.line(
                population,
                x="year",
                y="population_mn",
                color="state_name",
                markers=True,
                title="Annual population denominator (estimated between anchors)",
            ),
            width="stretch",
        )
        st.warning(
            "Population is interpolated/extrapolated from 2011 and 2024 anchors. "
            "Urban and rural shares remain fixed at Census 2011, so these are not "
            "observed annual urbanization estimates."
        )

        panel = query(
            f"""SELECT year, state_name, pc_income_constant_2011_12_inr,
                       gsdp_real_growth_pct, personal_loans_per_capita_inr
                FROM panel_state_year
                WHERE state_code IN ({codes_sql})
                ORDER BY year, state_name"""
        )
        metric = st.selectbox(
            "Macro metric",
            [
                "pc_income_constant_2011_12_inr",
                "gsdp_real_growth_pct",
                "personal_loans_per_capita_inr",
            ],
            format_func=lambda value: {
                "pc_income_constant_2011_12_inr": "Real per-capita NSDP (INR)",
                "gsdp_real_growth_pct": "Real GSDP growth (%)",
                "personal_loans_per_capita_inr": "Broad personal loans per capita (INR)",
            }[value],
        )
        st.plotly_chart(
            px.line(
                panel.dropna(subset=[metric]),
                x="year",
                y=metric,
                color="state_name",
                markers=True,
                title=metric.replace("_", " ").title(),
            ),
            width="stretch",
        )
        if metric == "personal_loans_per_capita_inr":
            st.info(
                "This is scheduled-commercial-bank personal-loan stock divided by "
                "estimated population. It is not vehicle-finance penetration."
            )

with tab_infra:
    cng = query(
        """SELECT c.*, d.state_name
           FROM ref_cng_stations c JOIN dim_state d USING (state_code)
           WHERE c.state_code <> 'ALL' ORDER BY stations DESC"""
    )
    ev = query(
        """SELECT e.*, d.state_name
           FROM ref_ev_charging e JOIN dim_state d USING (state_code)
           WHERE e.state_code <> 'ALL' ORDER BY year, public_chargers DESC"""
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(
                cng[cng["year"] == 2024].head(20),
                x="stations",
                y="state_name",
                orientation="h",
                title="CNG stations, 31 May 2024 (top 20)",
                hover_data=["source", "quality", "coverage_scope"],
            ).update_layout(yaxis={"categoryorder": "total ascending"}),
            width="stretch",
        )
        st.caption("The 2024 state allocation reconciles to the national total.")
    with right:
        ev_2025 = ev[ev["year"] == 2025].head(20)
        st.plotly_chart(
            px.bar(
                ev_2025,
                x="public_chargers",
                y="state_name",
                color="quality",
                orientation="h",
                title="Stored EV charging snapshot, 2025 (top 20)",
                hover_data=["source", "coverage_scope"],
            ).update_layout(yaxis={"categoryorder": "total ascending"}),
            width="stretch",
        )
        coverage = ev.loc[
            ev["year"] == 2025, "state_allocation_coverage_pct"
        ].dropna()
        if not coverage.empty:
            st.warning(
                f"Stored state rows cover {coverage.iloc[0]:.2f}% of the stated "
                "national total. Approximate rows are not a complete state census."
            )
    st.info(
        "No EV or CNG state history is fabricated for 2012-2023. These variables "
        "are valid only as dated cross-sectional snapshots."
    )

with tab_policy:
    tax = query(
        """SELECT t.*, d.state_name
           FROM ref_vehicle_lifetime_tax t JOIN dim_state d USING (state_code)"""
    )
    fuel = st.selectbox("Tax comparison fuel label", sorted(tax["fuel"].unique()))
    tax_view = tax[tax["fuel"] == fuel].sort_values("lifetime_tax_rate_pct")
    st.plotly_chart(
        px.bar(
            tax_view,
            x="state_name",
            y="lifetime_tax_rate_pct",
            color="quality",
            title=f"Approximate lifetime-tax benchmark: {fuel}, INR 10 lakh basis",
            hover_data=["method", "source", "as_of"],
        ),
        width="stretch",
    )
    st.warning(
        "For Petrol, Diesel, CNG, and Strong Hybrid, the same ICE benchmark is "
        "repeated unless a source distinguished fuel. This is current policy context, "
        "not an invoice calculator or historical tax series."
    )

    events = query(
        """SELECT date, date_end, state_code, category, tier, label, origin,
                  possible_overlap
           FROM ref_policy_events_canonical ORDER BY date"""
    )
    events["event_date"] = pd.to_datetime(events["date"] + "-01", errors="coerce")
    event_counts = (
        events.dropna(subset=["event_date"])
        .assign(year=lambda frame: frame["event_date"].dt.year)
        .groupby(["year", "category"], as_index=False)
        .size()
    )
    st.plotly_chart(
        px.bar(
            event_counts,
            x="year",
            y="size",
            color="category",
            title="Canonical policy and market-event annotations",
            labels={"size": "events"},
        ),
        width="stretch",
    )
    st.caption(
        "The timeline combines curated and bundled annotations. Overlap flags are "
        "preserved; an event marker is context, not causal identification."
    )

with tab_gaps:
    gaps = query("SELECT * FROM ref_known_data_gaps ORDER BY gap_id")
    st.dataframe(
        gaps,
        width="stretch",
        hide_index=True,
    )
    st.error(
        "State x OEM dealer history and state vehicle-finance penetration remain "
        "unavailable. Placeholder observations have been deleted; the gap registry "
        "states exactly what evidence would qualify. Broad personal-loan depth remains "
        "under its own name."
    )
    st.markdown(
        "**Wholesale boundary:** wholesale dispatch data has no fuel cut. Model "
        "metadata cannot split mixed-fuel nameplates into Petrol, Diesel, CNG, EV, "
        "or Hybrid quantities."
    )

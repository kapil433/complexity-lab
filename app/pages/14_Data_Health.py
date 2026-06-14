"""Data Health and Refresh: authoritative coverage and verification surface."""

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, render_app_shell

from complexity_lab.config import settings
from complexity_lab.data.intelligence import data_health

st.set_page_config(page_title="Data Health | Complexity Lab", layout="wide")
page = render_app_shell(
    "Data Health and Refresh",
    section="System",
    description=(
        "The single authority for freshness, completeness, reference quality, "
        "wholesale mapping, safe comparison periods, and refresh commands."
    ),
    evidence="Observed",
    limitations=(
        "A green structural check does not upgrade a constrained source into observed data.",
        "Wholesale health is available only on machines with the proprietary source.",
    ),
)

health = data_health(get_connection())
periods = health["periods"]
references = health["references"]
latest = periods.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Vahan freshness", str(latest["freshness_date"]))
c2.metric("Latest status", latest["completeness_status"])
c3.metric("Reference datasets", len(references))
c4.metric("Unavailable references", int((references["status"] == "unavailable").sum()))

tab_periods, tab_refs, tab_wholesale, tab_truth, tab_refresh = st.tabs(
    ["Period completeness", "Reference quality", "Wholesale mapping", "Data Truth", "Refresh"]
)
with tab_periods:
    st.plotly_chart(
        px.bar(
            periods,
            x="period",
            y=["observed_month_count", "expected_month_count"],
            barmode="group",
            color_discrete_sequence=["#E4572E", "#9AA5B1"],
            title="Observed versus expected months",
        ),
        width="stretch",
    )
    st.dataframe(periods, hide_index=True, width="stretch")

with tab_refs:
    st.dataframe(references, hide_index=True, width="stretch")
    st.plotly_chart(
        px.histogram(references, x="status", color="status", title="Reference availability"),
        width="stretch",
    )

with tab_wholesale:
    tables = set(health["tables"]["table_name"])
    if "wholesale" not in tables:
        st.info("Wholesale is intentionally absent from the public deployment.")
    else:
        mapping = get_connection().execute(
            """
            SELECT coverage,
                   SUM(qty) AS units,
                   SUM(qty) FILTER (WHERE state_code IS NOT NULL) AS mapped_units,
                   100 * SUM(qty) FILTER (WHERE state_code IS NOT NULL) / SUM(qty)
                       AS mapped_pct
            FROM wholesale
            GROUP BY coverage
            ORDER BY coverage
            """
        ).df()
        st.dataframe(mapping, hide_index=True, width="stretch")
        st.warning(
            "Wholesale has no fuel cut. Mapping coverage refers only to city-to-state assignment."
        )

with tab_truth:
    st.markdown((settings.root / "DATA_TRUTH.md").read_text(encoding="utf-8"))

with tab_refresh:
    st.code(
        "\n".join(
            [
                "uv run lab ingest",
                "uv run lab panel",
                "uv run lab wholesale --refresh",
                "uv run python scripts/validate_numbers.py",
                "uv run pytest",
                "uv run ruff check .",
            ]
        ),
        language="powershell",
    )
    st.caption(
        "Run wholesale refresh only where the proprietary source is available. "
        "The public build intentionally skips it."
    )

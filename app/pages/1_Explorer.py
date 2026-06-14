"""Compare and Explore: structured state comparison, maps, ranks, and cohorts."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import load_geojson, query, render_app_shell, render_card

from complexity_lab.viz import indian_axis, pct_axis

st.set_page_config(page_title="Compare and Explore | Complexity Lab", layout="wide")
page = render_app_shell(
    "Compare and Explore",
    section="Observe",
    description=(
        "Compare states through maps, indexed trajectories, ranks, growth, volatility, "
        "reference context, and reproducible URL state."
    ),
    limitations=(
        "Maps and scatter plots show association and distribution, not causal effects.",
        "Population and reference metrics retain their source quality and denominator basis.",
    ),
)
render_card("descriptive-baseline")

METRICS = {
    "total_regs": ("Total registrations", "units"),
    "ev_share": ("EV share", "pct"),
    "cng_share": ("CNG share", "pct"),
    "diesel_share": ("Diesel share", "pct"),
    "petrol_share": ("Petrol share", "pct"),
    "hhi_oem": ("OEM concentration", "raw"),
    "yoy_growth": ("YoY growth", "pct"),
    "regs_per_1000_population": ("Registrations per 1,000 people", "raw"),
    "real_pc_income_inr": ("Real per-capita income", "units"),
    "real_gsdp_growth_pct": ("Real GSDP growth", "raw"),
    "broad_credit_per_capita_inr": ("Broad credit per capita", "units"),
}

panel = query("SELECT * FROM experiment_state_year")
context = query("SELECT * FROM experiment_state_context")
dimension = query("SELECT state_code, geojson_name, zone FROM dim_state")
panel = panel.merge(
    context[
        ["state_code", "urban_pct", "real_pc_income_inr", "ev_quality", "cng_quality"]
    ].rename(columns={"real_pc_income_inr": "context_income"}),
    on="state_code",
    how="left",
)
panel = panel.merge(dimension, on="state_code", how="left", suffixes=("", "_dim"))
panel["income_quartile"] = pd.qcut(
    panel.groupby("state_code")["context_income"].transform("max"),
    4,
    labels=["Q1 income", "Q2 income", "Q3 income", "Q4 income"],
    duplicates="drop",
)
panel["urban_quartile"] = pd.qcut(
    panel.groupby("state_code")["urban_pct_y" if "urban_pct_y" in panel else "urban_pct"].transform("max"),
    4,
    labels=["Q1 urban", "Q2 urban", "Q3 urban", "Q4 urban"],
    duplicates="drop",
)

query_metric = st.query_params.get("metric", "total_regs")
query_normalization = st.query_params.get("normalization", "Actual")
controls = st.columns([1.4, 1.2, 1.1, 1.1])
metric = controls[0].selectbox(
    "Metric",
    list(METRICS),
    index=list(METRICS).index(query_metric) if query_metric in METRICS else 0,
    format_func=lambda value: METRICS[value][0],
)
normalization = controls[1].selectbox(
    "Normalization",
    ["Actual", "Index to 100", "Percentile", "Share of selected states"],
    index=["Actual", "Index to 100", "Percentile", "Share of selected states"].index(
        query_normalization
    )
    if query_normalization in ["Actual", "Index to 100", "Percentile", "Share of selected states"]
    else 0,
)
grouping = controls[2].selectbox(
    "Group states by",
    ["None", "Zone", "Income quartile", "Urbanization quartile"],
)
snapshot_year = controls[3].slider(
    "Snapshot year",
    int(panel["year"].min()),
    int(panel["year"].max()),
    min(page.filters.year_end, page.cutoff.latest_complete_year),
)
st.query_params["metric"] = metric
st.query_params["normalization"] = normalization

state_names = sorted(panel["state_name"].unique())
query_states = [value for value in st.query_params.get("compare", "").split(",") if value]
default_names = panel.loc[
    panel["state_code"].isin(page.filters.states), "state_name"
].drop_duplicates().tolist()
selected_states = st.multiselect(
    "Comparison set (six or more remain readable in the indexed and table views)",
    state_names,
    default=query_states or default_names or ["Maharashtra", "Karnataka", "Uttar Pradesh", "Tamil Nadu"],
)
st.query_params["compare"] = ",".join(selected_states)

working = panel[
    panel["state_name"].isin(selected_states)
    & panel["year"].between(page.filters.year_start, page.filters.year_end)
].copy()
value_column = metric
if normalization == "Index to 100":
    working["display_value"] = working.groupby("state_code")[metric].transform(
        lambda series: 100 * series / series.dropna().iloc[0] if series.notna().any() else np.nan
    )
    value_column = "display_value"
elif normalization == "Percentile":
    working["display_value"] = working.groupby("year")[metric].rank(pct=True)
    value_column = "display_value"
elif normalization == "Share of selected states":
    working["display_value"] = working[metric] / working.groupby("year")[metric].transform("sum")
    value_column = "display_value"

tab_map, tab_compare, tab_scatter, tab_table = st.tabs(
    ["Map", "Compare trajectories", "Scatter / bubble", "Rank and export"]
)
with tab_map:
    snapshot = panel[panel["year"] == snapshot_year].copy()
    figure = px.choropleth(
        snapshot,
        geojson=load_geojson(),
        locations="geojson_name",
        featureidkey="properties.ST_NM",
        color=metric,
        color_continuous_scale="Viridis",
        hover_name="state_name",
        hover_data={
            "zone": True,
            "ev_quality": True,
            "cng_quality": True,
            "geojson_name": False,
        },
        title=f"{METRICS[metric][0]}, {snapshot_year}",
    )
    figure.update_geos(fitbounds="locations", visible=False)
    figure.update_layout(height=620, margin={"l": 0, "r": 0, "t": 45, "b": 0})
    st.plotly_chart(figure, width="stretch")
    st.caption("Select states in the comparison control above; map-click selection is not persisted by Streamlit.")

with tab_compare:
    color = {
        "None": "state_name",
        "Zone": "zone",
        "Income quartile": "income_quartile",
        "Urbanization quartile": "urban_quartile",
    }[grouping]
    figure = px.line(
        working,
        x="year",
        y=value_column,
        color=color,
        line_group="state_name",
        hover_name="state_name",
        markers=True,
        title=f"{METRICS[metric][0]} | {normalization}",
    )
    if METRICS[metric][1] == "pct" and normalization == "Actual":
        pct_axis(figure)
    elif METRICS[metric][1] == "units" and normalization == "Actual":
        indian_axis(figure)
    st.plotly_chart(figure, width="stretch")

with tab_scatter:
    numeric = list(METRICS)
    x_metric = st.selectbox("X axis", numeric, index=numeric.index("real_pc_income_inr"))
    y_metric = st.selectbox("Y axis", numeric, index=numeric.index("ev_share"))
    size_metric = st.selectbox("Bubble size", ["total_regs", "population_mn", "None"])
    scatter = panel[panel["year"] == snapshot_year].dropna(subset=[x_metric, y_metric])
    st.plotly_chart(
        px.scatter(
            scatter,
            x=x_metric,
            y=y_metric,
            size=None if size_metric == "None" else size_metric,
            color="zone",
            hover_name="state_name",
            trendline="ols",
            title=f"{METRICS[y_metric][0]} versus {METRICS[x_metric][0]}, {snapshot_year}",
        ),
        width="stretch",
    )

with tab_table:
    rows = []
    for state_name, group in working.groupby("state_name"):
        clean = group.dropna(subset=[metric]).sort_values("year")
        if clean.empty:
            continue
        start, end = clean.iloc[0], clean.iloc[-1]
        years = max(int(end["year"] - start["year"]), 1)
        cagr = (
            (end[metric] / start[metric]) ** (1 / years) - 1
            if start[metric] > 0 and end[metric] >= 0
            else np.nan
        )
        rows.append(
            {
                "state": state_name,
                "latest": end[metric],
                "rank": clean[clean["year"] == end["year"]][metric].rank(ascending=False).iloc[0],
                "cagr": cagr,
                "volatility": clean[metric].pct_change().std(),
                "contribution": end[metric]
                / panel.loc[panel["year"] == end["year"], metric].sum(),
            }
        )
    table = pd.DataFrame(rows)
    if not table.empty:
        table["rank"] = table["latest"].rank(ascending=False, method="min")
        table["percentile"] = table["latest"].rank(pct=True)
        prior = panel[panel["year"] == snapshot_year - 1].set_index("state_name")[metric]
        current = panel[panel["year"] == snapshot_year].set_index("state_name")[metric]
        rank_change = prior.rank(ascending=False) - current.rank(ascending=False)
        table["rank_change"] = table["state"].map(rank_change)
        st.dataframe(
            table.style.format(
                {
                    "latest": "{:,.3g}",
                    "cagr": "{:+.1%}",
                    "volatility": "{:.1%}",
                    "contribution": "{:.1%}",
                    "percentile": "{:.0%}",
                    "rank_change": "{:+.0f}",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Download comparison CSV",
            table.to_csv(index=False),
            file_name=f"state-comparison-{metric}.csv",
            mime="text/csv",
        )

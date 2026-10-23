"""Science Playground: one hypothesis, explicit knobs, and a result that can change."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, render_app_shell

from complexity_lab.data.autiqa import autiqa_status
from complexity_lab.data.public_macro import (
    SOURCE_CATALOG,
    cache_path,
    load_world_bank,
    refresh_world_bank,
)
from complexity_lab.playground.catalog import experiments
from complexity_lab.playground.data import state_codes
from complexity_lab.playground.service import run_experiment, run_validation_suite

st.set_page_config(page_title="Science Playground | Complexity Lab", layout="wide")
render_app_shell(
    "Science Playground",
    section="Research",
    description=(
        "Fifty pre-specified experiments on the Indian passenger-vehicle extract, "
        "from data checks through forecasts and complexity measures."
    ),
    evidence="Estimated",
    limitations=(
        "Each run is one pre-specified test. Browsing all fifty and keeping the surprising ones is not a confirmatory study.",
        "Changing a knob can change the sentence. It does not create a causal effect.",
        "Autiqa rows are loaded only when a pull passes the registration contract. A missing API adds nothing.",
        "World Bank series are national. They do not replace state income, state GSDP, or the estimated population denominator.",
    ),
)

specs = experiments()
tiers = list(dict.fromkeys(spec.tier for spec in specs))

tab_run, tab_variables, tab_sources, tab_validation = st.tabs(
    ["Run an experiment", "What the variables mean", "Sources we will and will not join", "Validation suite"]
)

with tab_run:
    tier = st.selectbox("Tier", tiers)
    choices = [spec for spec in specs if spec.tier == tier]
    spec = st.selectbox(
        "Experiment",
        choices,
        format_func=lambda item: f"{item.experiment_id}  {item.title}",
    )
    st.markdown(f"**Hypothesis.** {spec.hypothesis}")
    st.markdown(f"**Null.** {spec.null_hypothesis}")
    st.markdown(f"**Method.** {spec.method}")
    st.markdown("**Variables.** " + "; ".join(spec.variables))
    with st.expander("Limits, before you run it"):
        for item in spec.limitations:
            st.markdown(f"- {item}")
        st.markdown(f"**Do not infer.** {spec.do_not_infer}")

    codes = state_codes(get_connection())
    overrides = {}
    columns = st.columns(min(3, max(1, len(spec.knobs))))
    for index, knob in enumerate(spec.knobs):
        with columns[index % len(columns)]:
            widget_key = f"pg_{spec.experiment_id}_{knob.name}"
            if knob.kind == "bool":
                overrides[knob.name] = st.toggle(knob.label, value=bool(knob.default), help=knob.help, key=widget_key)
            elif knob.kind == "state":
                options = codes or [str(knob.default)]
                default = str(knob.default) if str(knob.default) in options else options[0]
                overrides[knob.name] = st.selectbox(
                    knob.label, options, index=options.index(default), help=knob.help, key=widget_key
                )
            elif knob.kind == "select":
                overrides[knob.name] = st.selectbox(
                    knob.label, list(knob.options), index=list(knob.options).index(knob.default),
                    help=knob.help, key=widget_key,
                )
            elif knob.kind == "int":
                overrides[knob.name] = int(
                    st.number_input(
                        knob.label, min_value=int(knob.minimum), max_value=int(knob.maximum),
                        value=int(knob.default), step=int(knob.step or 1), help=knob.help, key=widget_key,
                    )
                )
            else:
                overrides[knob.name] = float(
                    st.slider(
                        knob.label, min_value=float(knob.minimum), max_value=float(knob.maximum),
                        value=float(knob.default), step=float(knob.step or 0.01), help=knob.help, key=widget_key,
                    )
                )

    if st.button("Run this experiment", type="primary"):
        with st.spinner("Running on the local database. No missing number is being filled in."):
            st.session_state["playground_result"] = run_experiment(get_connection(), spec.experiment_id, overrides)
            st.session_state["playground_result_id"] = spec.experiment_id

    result = st.session_state.get("playground_result")
    if result is not None and st.session_state.get("playground_result_id") == spec.experiment_id:
        st.markdown(f"**Status.** {result.status} · **Evidence.** {result.evidence}")
        if result.metrics:
            metric_frame = pd.DataFrame(
                [{"metric": key, "value": value} for key, value in result.metrics.items()]
            )
            st.dataframe(metric_frame, hide_index=True, width="stretch")
        checks = pd.DataFrame(result.checks)
        if not checks.empty:
            st.dataframe(checks, hide_index=True, width="stretch")
        st.markdown(f"**Interpretation.** {result.interpretation}")
        st.markdown(f"**Do not infer.** {result.do_not_infer}")
        for note in result.data_notes:
            st.caption(note)
        if result.frame is not None and not result.frame.empty:
            if result.chart in {"line", "bar", "scatter"} and result.chart_x and result.chart_y:
                plot_frame = result.frame
                if result.chart == "bar" and len(plot_frame) > 25:
                    plot_frame = plot_frame.head(25)
                kwargs = {
                    "data_frame": plot_frame,
                    "x": result.chart_x,
                    "y": result.chart_y,
                    "title": spec.title,
                }
                if result.chart_color and result.chart_color in plot_frame.columns:
                    kwargs["color"] = result.chart_color
                if result.chart == "line":
                    figure = px.line(**kwargs, markers=True)
                elif result.chart == "scatter":
                    figure = px.scatter(**kwargs)
                else:
                    figure = px.bar(**kwargs)
                figure.update_layout(margin=dict(l=16, r=16, t=48, b=16), height=420)
                st.plotly_chart(figure, width="stretch")
            st.dataframe(result.frame, hide_index=True, width="stretch")
            st.download_button(
                "Download this result table",
                result.frame.to_csv(index=False).encode("utf-8"),
                file_name=f"{spec.experiment_id}.csv",
                mime="text/csv",
            )

with tab_variables:
    st.markdown(
        """
The outcome in almost every experiment is a Vahan registration count or a share
built from those counts. Covariates keep the quality label they arrived with.

| Variable | What it is | What it is not |
|---|---|---|
| All India registrations | The source's own national series | The sum of the state rows |
| State registrations | State and UT series in the bundle | A Telangana series, which is absent |
| Fuel counts | Petrol, diesel, CNG, EV, strong hybrid as classified by the source | A wholesale fuel split |
| Strong hybrid | Usable as labelled from 2024 | A continuous adoption curve back to 2012 |
| OEM HHI and entropy | Summaries of the OEM share vector | A welfare or quality score |
| Real per-capita income | RBI Table 20, constant 2011-12 prices, financial year | A calendar-year household survey |
| Real GSDP growth | RBI Table 22 level, growth derived from it | World Bank national GDP |
| Population | Interpolated denominator, labelled estimate | A census count for each year |
| Urban share | Census 2011 share, held fixed | Annual urbanisation |
| Petrol, diesel, CNG prices | Approximate annual state prices, basis disclosed | Daily pump prices or an energy-equivalent CNG cost |
| Personal loans per person | Broad bank credit depth | Vehicle-finance penetration |
| World Bank GDP growth | National calendar-year context, when the cache exists | A substitute for a missing state |
        """
    )

with tab_sources:
    status = autiqa_status()
    st.markdown(f"**Autiqa Supabase.** {status.status}. {status.detail}")
    cached = load_world_bank()
    if cached is None:
        st.markdown(
            f"**World Bank cache.** Not on disk at `{cache_path()}`. "
            "National GDP is left missing until a fetch succeeds."
        )
    else:
        latest = cached["retrieved_at_utc"].iloc[0]
        st.markdown(
            f"**World Bank cache.** {len(cached)} rows, retrieved {latest}. "
            "National series only."
        )
        st.dataframe(
            cached.groupby("series_name")["year"].agg(["min", "max", "count"]).reset_index(),
            hide_index=True,
            width="stretch",
        )
    if st.button("Fetch World Bank India series"):
        refreshed = refresh_world_bank()
        st.markdown(f"**{refreshed.status}.** {refreshed.detail}")
    st.dataframe(pd.DataFrame(SOURCE_CATALOG), hide_index=True, width="stretch")

with tab_validation:
    st.markdown(
        "These ten checks measure the extract and the catalog. "
        "A failure is reported. The suite does not impute, clip, or relabel the row that failed."
    )
    if st.button("Run V01–V10"):
        with st.spinner("Checking identities, labels, and the reference catalog."):
            st.session_state["playground_validation"] = run_validation_suite(get_connection())
    validation = st.session_state.get("playground_validation")
    if validation:
        summary = pd.DataFrame(
            [
                {
                    "id": item.experiment_id,
                    "title": item.title,
                    "status": item.status,
                    "failed_checks": len(item.failed_checks),
                    "interpretation": item.interpretation,
                }
                for item in validation
            ]
        )
        st.dataframe(summary, hide_index=True, width="stretch")

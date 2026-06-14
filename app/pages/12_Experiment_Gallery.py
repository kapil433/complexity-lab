"""Experiment Gallery: run, inspect, compare, and share visual research bundles."""

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import render_app_shell

from complexity_lab.config import settings
from complexity_lab.experiments.publishing import discover_runs, latest_runs_by_experiment
from complexity_lab.experiments.registry import list_experiments
from complexity_lab.experiments.runner import run_experiment
from complexity_lab.persistence import save_research_item

st.set_page_config(page_title="Experiment Gallery | Complexity Lab", layout="wide")
page = render_app_shell(
    "Experiment Gallery",
    section="Research",
    description=(
        "Run the lab's registered experiments and inspect their findings, diagnostics, "
        "cutoffs, limitations, artifacts, and share cards."
    ),
    evidence="Estimated",
    limitations=(
        "Wholesale-dependent experiments run only where proprietary local data is available.",
        "Public bundles contain approved aggregates; raw proprietary rows remain private.",
    ),
)

experiments = list_experiments()
latest = latest_runs_by_experiment(settings.outputs_dir)
selected = st.selectbox(
    "Experiment",
    [experiment.name for experiment in experiments],
    format_func=lambda name: next(
        experiment.description for experiment in experiments if experiment.name == name
    ),
)
experiment = next(item for item in experiments if item.name == selected)
st.markdown(f"**Registered ID:** `{experiment.name}`")
st.write(experiment.description)

params_text = st.text_area("Parameters (JSON)", value="{}", height=90)
run_col, save_col = st.columns([1, 1])
if run_col.button("Run experiment", type="primary"):
    try:
        params = json.loads(params_text)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
    else:
        with st.status("Running experiment", expanded=True) as status:
            st.write("Validating data contract")
            try:
                manifest = run_experiment(selected, params=params)
            except Exception as exc:  # noqa: BLE001
                status.update(label="Experiment failed", state="error")
                st.error(str(exc))
            else:
                st.write("Building diagnostics and visual bundle")
                status.update(label="Experiment published", state="complete")
                st.session_state["gallery_last_manifest"] = manifest
                st.rerun()

run = st.session_state.get("gallery_last_manifest") or latest.get(selected)
if run:
    run_dir = Path(run.get("_run_dir", ""))
    if not run_dir.exists() and run.get("_manifest_path"):
        run_dir = Path(run["_manifest_path"]).parent
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", run.get("status", "legacy run"))
    c2.metric("Run time", f"{run.get('elapsed_seconds', 0):.1f}s")
    c3.metric("Data cutoff", run.get("data_cutoff", {}).get("vahan", "legacy"))
    c4.metric("Privacy", run.get("privacy", "legacy"))
    st.markdown(f"### {run.get('primary_finding', 'Latest recorded result')}")

    hero = run_dir / "figures" / "01-primary.png"
    diagnostic = run_dir / "figures" / "02-diagnostic.png"
    share = run_dir / "share-card.png"
    if hero.exists():
        st.image(str(hero), caption="Editorial hero")
    if diagnostic.exists():
        with st.expander("Run diagnostics", expanded=True):
            st.image(str(diagnostic))
    if share.exists():
        with st.expander("Share card"):
            st.image(str(share))
            st.download_button(
                "Download share card",
                data=share.read_bytes(),
                file_name=f"{selected}-share-card.png",
                mime="image/png",
            )
    result_page = run_dir / "result.md"
    if result_page.exists():
        st.download_button(
            "Download result brief",
            data=result_page.read_bytes(),
            file_name=f"{selected}-result.md",
            mime="text/markdown",
        )
    tabs = st.tabs(["Metrics", "Limitations", "Artifacts", "Manifest"])
    with tabs[0]:
        metrics = run.get("metrics", {})
        primitive = {
            key: str(value)
            for key, value in metrics.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        st.dataframe(
            pd.DataFrame([primitive]).T.rename(columns={0: "value"}),
            width="stretch",
        )
    with tabs[1]:
        for limitation in run.get("limitations", ["Legacy run; see experiment card."]):
            st.markdown(f"- {limitation}")
    with tabs[2]:
        artifacts = run.get("artifacts", [])
        if artifacts and isinstance(artifacts[0], str):
            artifacts = [{"path": value, "classification": "legacy"} for value in artifacts]
        st.dataframe(pd.DataFrame(artifacts), hide_index=True, width="stretch")
    with tabs[3]:
        st.json(run)

    if save_col.button("Save result to research inbox"):
        save_research_item(
            "experiment",
            title=f"{selected}: {run.get('primary_finding', 'result')}",
            parameters=run.get("params", {}),
            result=run.get("metrics", {}),
            data_cutoff=run.get("data_cutoff", {}).get("vahan", page.cutoff.latest_period),
        )
        st.success("Experiment result saved.")
else:
    st.info("No local run yet. Run the experiment to create its visual result bundle.")

runs = latest_runs_by_experiment(settings.outputs_dir)
if runs:
    st.subheader("Latest run by experiment")
    gallery = pd.DataFrame(
        [
            {
                "experiment": name,
                "status": manifest.get("status", "legacy"),
                "finding": manifest.get("primary_finding", ""),
                "cutoff": manifest.get("data_cutoff", {}).get("vahan", ""),
                "timestamp": manifest.get("timestamp_utc", ""),
            }
            for name, manifest in runs.items()
        ]
    )
    st.dataframe(gallery, hide_index=True, width="stretch")

all_selected_runs = [
    item for item in discover_runs(settings.outputs_dir) if item["experiment"] == selected
]
if len(all_selected_runs) >= 2:
    st.subheader("Compare runs")
    labels = {
        f"{item.get('timestamp_utc', 'unknown')} | {item.get('primary_finding', '')}": item
        for item in all_selected_runs
    }
    chosen = st.multiselect(
        "Choose two runs",
        list(labels),
        default=list(labels)[:2],
        max_selections=2,
    )
    if len(chosen) == 2:
        comparison = []
        for label in chosen:
            item = labels[label]
            comparison.append(
                {
                    "run": item.get("timestamp_utc"),
                    "cutoff": item.get("data_cutoff", {}).get("vahan"),
                    "elapsed_seconds": item.get("elapsed_seconds"),
                    "parameters": json.dumps(item.get("params", {}), sort_keys=True),
                    "finding": item.get("primary_finding"),
                }
            )
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
        metric_keys = sorted(
            set(labels[chosen[0]].get("metrics", {}))
            | set(labels[chosen[1]].get("metrics", {}))
        )
        metric_rows = []
        for key in metric_keys:
            values = [labels[label].get("metrics", {}).get(key) for label in chosen]
            if all(isinstance(value, (str, int, float, bool)) or value is None for value in values):
                metric_rows.append({"metric": key, chosen[0]: str(values[0]), chosen[1]: str(values[1])})
        if metric_rows:
            st.dataframe(pd.DataFrame(metric_rows), hide_index=True, width="stretch")

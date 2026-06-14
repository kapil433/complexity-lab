"""Saved Questions: local research inbox and exportable research cards."""

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import render_app_shell

from complexity_lab.persistence import (
    list_research_items,
    list_watchlist,
    save_research_item,
)

st.set_page_config(page_title="Saved Questions | Complexity Lab", layout="wide")
page = render_app_shell(
    "Saved Questions",
    section="Research",
    description=(
        "Your local research inbox for saved views, notes, hypotheses, forecasts, "
        "scenarios, experiments, and watchlist items."
    ),
    evidence="Derived",
    limitations=(
        "Research memory is stored locally and is not synchronized across deployments.",
        "A saved card records its data cutoff; rerunning later may use a newer vintage.",
    ),
)

with st.expander("Add a research note", expanded=False):
    title = st.text_input("Question or note title")
    note = st.text_area("Note")
    if st.button("Save note", disabled=not title.strip()):
        save_research_item(
            "note",
            title=title,
            parameters=page.filters.to_payload(),
            result={},
            data_cutoff=page.cutoff.latest_period,
            notes=note,
        )
        st.success("Note saved.")

items = list_research_items()
watchlist = list_watchlist()
c1, c2, c3 = st.columns(3)
c1.metric("Research cards", len(items))
c2.metric("Watchlist items", len(watchlist))
c3.metric("Latest cutoff", page.cutoff.latest_period)

tab_inbox, tab_watchlist, tab_export = st.tabs(["Inbox", "Watchlist", "Export brief"])
with tab_inbox:
    if items.empty:
        st.info("No research cards yet. Save a view, forecast, scenario, or note.")
    else:
        kinds = st.multiselect(
            "Kinds",
            sorted(items["kind"].unique()),
            default=sorted(items["kind"].unique()),
        )
        filtered = items[items["kind"].isin(kinds)]
        st.dataframe(
            filtered[
                ["kind", "title", "data_cutoff", "method_version", "notes", "created_at"]
            ],
            hide_index=True,
            width="stretch",
        )
        selected_id = st.selectbox(
            "Open card",
            filtered["id"],
            format_func=lambda item_id: filtered.set_index("id").loc[item_id, "title"],
        )
        row = filtered.set_index("id").loc[selected_id]
        st.markdown(f"### {row['title']}")
        st.caption(f"{row['kind']} | cutoff {row['data_cutoff']} | {row['created_at']}")
        st.json(json.loads(row["parameter_payload"]))
        result = json.loads(row["result_payload"])
        if result:
            st.json(result)

with tab_watchlist:
    if watchlist.empty:
        st.info("Use State Intelligence or OEM Intelligence to pin items.")
    else:
        st.dataframe(watchlist, hide_index=True, width="stretch")

with tab_export:
    brief = {
        "generated_from": "Complexity Lab",
        "data_cutoff": page.cutoff.latest_period,
        "context": page.filters.to_payload(),
        "research_items": items.to_dict("records"),
        "watchlist": watchlist.to_dict("records"),
    }
    st.download_button(
        "Download research brief (JSON)",
        json.dumps(brief, indent=2, default=str),
        file_name="complexity-lab-research-brief.json",
        mime="application/json",
    )

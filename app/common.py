"""Shared Streamlit shell, truth context, and display helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

import duckdb
import pandas as pd
import streamlit as st

from complexity_lab.app_state import GlobalContext
from complexity_lab.config import settings
from complexity_lab.data.access import (
    DataCutoff,
    maker_options,
    state_dimension,
    table_exists,
    vahan_cutoff,
)
from complexity_lab.persistence import list_saved_views, save_view
from complexity_lab.viz import use_lab_theme

use_lab_theme()


@dataclass(frozen=True)
class PageContext:
    filters: GlobalContext
    cutoff: DataCutoff


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not settings.db_path.exists():
        st.error("data/lab.duckdb not found. Run `uv run lab ingest && uv run lab panel`.")
        st.stop()
    return duckdb.connect(str(settings.db_path), read_only=True)


@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    return get_connection().execute(sql).df()


@st.cache_data(ttl=3600)
def query_with_params(sql: str, params: tuple[object, ...]) -> pd.DataFrame:
    return get_connection().execute(sql, list(params)).df()


@st.cache_data(ttl=3600)
def load_geojson() -> dict:
    return json.loads(settings.geojson_path.read_text(encoding="utf-8"))


@st.cache_data(ttl=3600)
def _shell_options() -> tuple[pd.DataFrame, list[str], DataCutoff, bool]:
    con = get_connection()
    return state_dimension(con), maker_options(con), vahan_cutoff(con), table_exists(con, "wholesale")


def _query_dict() -> dict[str, str | list[str]]:
    return {key: st.query_params.get_all(key) for key in st.query_params}


def _sync_url(context: GlobalContext) -> None:
    desired = context.to_query_params()
    current = {
        key: values[-1]
        for key, values in _query_dict().items()
        if values
    }
    if current != desired:
        st.query_params.from_dict(desired)


def global_filters() -> PageContext:
    states, oems, cutoff, has_wholesale = _shell_options()
    min_year = int(query("SELECT MIN(year) AS y FROM panel_state_year")["y"][0])
    max_year = int(query("SELECT MAX(year) AS y FROM panel_state_year")["y"][0])

    if "_lab_global_initialized" not in st.session_state:
        initial = GlobalContext.from_query_params(
            _query_dict(),
            min_year=min_year,
            max_year=max_year,
            default_end=cutoff.latest_complete_year,
        )
        st.session_state["global_years"] = (initial.year_start, initial.year_end)
        st.session_state["global_states"] = list(initial.states)
        st.session_state["global_fuels"] = list(initial.fuels)
        st.session_state["global_oems"] = list(initial.oems)
        st.session_state["global_coverage"] = initial.coverage
        st.session_state["_lab_global_initialized"] = True

    state_names = dict(zip(states["state_code"], states["state_name"], strict=True))
    with st.sidebar:
        st.markdown("### Research context")
        coverage = st.radio(
            "Period policy",
            ["complete", "available"],
            format_func=lambda value: {
                "complete": "Complete years only",
                "available": "Include partial latest year",
            }[value],
            key="global_coverage",
        )
        years = st.slider(
            "Calendar years",
            min_year,
            max_year,
            key="global_years",
        )
        selected_states = st.multiselect(
            "States",
            states["state_code"].tolist(),
            format_func=lambda code: state_names.get(code, code),
            placeholder="All India",
            key="global_states",
        )
        selected_fuels = st.multiselect(
            "Fuel",
            ["Petrol", "Diesel", "CNG", "EV", "Strong Hybrid"],
            placeholder="All fuels",
            key="global_fuels",
        )
        with st.expander("OEM and source"):
            selected_oems = st.multiselect(
                "OEM",
                oems,
                placeholder="All OEMs",
                key="global_oems",
            )
            st.caption("Primary source: Vahan registrations")
            if has_wholesale:
                st.caption("Local wholesale is available on its dedicated page.")

    effective_end = min(years[1], cutoff.latest_complete_year) if coverage == "complete" else years[1]
    context = GlobalContext(
        year_start=min(years[0], effective_end),
        year_end=effective_end,
        states=tuple(selected_states),
        fuels=tuple(selected_fuels),
        oems=tuple(selected_oems),
        coverage=coverage,
    )
    _sync_url(context)
    return PageContext(filters=context, cutoff=cutoff)


def render_app_shell(
    title: str,
    *,
    section: str,
    description: str,
    evidence: str = "Observed",
    limitations: tuple[str, ...] = (),
) -> PageContext:
    context = global_filters()
    st.markdown(
        """
        <style>
        .lab-eyebrow {font-size:.76rem; font-weight:700; letter-spacing:.12em;
          text-transform:uppercase; color:#E4572E; margin-bottom:.15rem}
        .lab-title {font-size:2.35rem; line-height:1.08; font-weight:720; margin:0 0 .35rem}
        .lab-deck {font-size:1.05rem; color:var(--text-color); opacity:.76;
          max-width:850px; margin-bottom:.65rem}
        .lab-badge {display:inline-block; padding:.2rem .55rem; margin:0 .35rem .35rem 0;
          border:1px solid rgba(128,128,128,.35); border-radius:999px; font-size:.76rem}
        .lab-finding {border-left:4px solid #E4572E; padding:.7rem 1rem;
          background:rgba(228,87,46,.08); margin:.7rem 0 1rem}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="lab-eyebrow">{section}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="lab-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="lab-deck">{description}</div>', unsafe_allow_html=True)
    filter_scope = (
        f"{len(context.filters.states)} selected states"
        if context.filters.states
        else "All India"
    )
    badges = [
        evidence,
        f"Vahan through {context.cutoff.latest_period}",
        f"Latest complete year {context.cutoff.latest_complete_year}",
        f"{filter_scope}, {context.filters.year_start}-{context.filters.year_end}",
    ]
    st.markdown(
        "".join(f'<span class="lab-badge">{badge}</span>' for badge in badges),
        unsafe_allow_html=True,
    )
    if context.filters.coverage == "available" and context.filters.year_end > context.cutoff.latest_complete_year:
        st.warning(context.cutoff.warning)

    with st.expander("Methodology, provenance, and shareable context"):
        st.markdown(
            f"**Primary source:** Vahan registrations. **Observed range:** "
            f"{context.cutoff.first_period} to {context.cutoff.latest_period}. "
            f"The latest year contains {context.cutoff.observed_months_latest_year} months."
        )
        if limitations:
            st.markdown("**Boundaries**")
            for item in limitations:
                st.markdown(f"- {item}")
        payload = context.filters.to_payload()
        payload["data_cutoff"] = context.cutoff.latest_period
        st.json(payload)
        st.download_button(
            "Download view context",
            json.dumps(payload, indent=2),
            file_name="complexity-lab-view.json",
            mime="application/json",
            key=f"context-download-{title}",
        )

    with st.sidebar.expander("Save this view"):
        saved_title = st.text_input("Title", value=title, key=f"save-title-{title}")
        saved_notes = st.text_area("Notes", key=f"save-notes-{title}", height=70)
        if st.button("Save locally", key=f"save-view-{title}", width="stretch"):
            save_view(
                title=saved_title,
                page=title,
                payload=context.filters.to_payload(),
                data_cutoff=context.cutoff.latest_period,
                notes=saved_notes,
            )
            st.success("View saved to the local research library.")
        saved = list_saved_views()
        if not saved.empty:
            st.caption(f"{len(saved)} saved view(s) in this local lab.")
    return context


def render_finding(text: str, *, label: str = "What changed") -> None:
    st.markdown(
        f'<div class="lab-finding"><strong>{label}</strong><br>{text}</div>',
        unsafe_allow_html=True,
    )


def year_range_slider(df: pd.DataFrame, key: str = "years") -> tuple[int, int]:
    lo, hi = int(df["year"].min()), int(df["year"].max())
    return st.slider("Years", lo, hi, (max(lo, 2013), hi - 1), key=key)


def render_card(card_id: str) -> None:
    """Render the method, interpretation, and limits for an experiment."""
    from complexity_lab.experiments.cards import get_card

    card = get_card(card_id)
    with st.expander(f"About this experiment: {card.name}", expanded=False):
        st.caption(f"`{card.id}` | {card.category} | {card.tier}")
        st.markdown(f"**Why this matters.** {card.question}")
        st.markdown(f"**Method.** {card.method}")

        tab_how, tab_concepts, tab_math, tab_read, tab_limits = st.tabs(
            ["How it works", "Concepts", "Math", "Read the results", "Limits and uses"]
        )
        with tab_how:
            for i, step in enumerate(card.how_it_works, 1):
                st.markdown(f"{i}. {step}")
            st.caption("Data: " + "; ".join(card.data_used))
        with tab_concepts:
            for term, meaning in card.plain_english.items():
                st.markdown(f"- **{term}**: {meaning}")
        with tab_math:
            st.markdown(card.math)
        with tab_read:
            for item in card.look_for:
                st.markdown(f"- {item}")
        with tab_limits:
            st.markdown("**Do not over-interpret when:**")
            for item in card.limitations:
                st.markdown(f"- {item}")
            st.markdown("**Who acts on this:**")
            for item in card.decisions:
                st.markdown(f"- {item}")
            if card.related:
                st.caption("Related: " + ", ".join(card.related))


def events_toggle_and_overlay(fig, key: str = "events"):
    from complexity_lab.viz import add_event_markers, load_events

    if st.checkbox("Show policy events", value=True, key=key):
        events = load_events(get_connection())
        fig = add_event_markers(fig, events, max_labels=12)
    return fig

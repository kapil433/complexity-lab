"""Shared Streamlit shell, truth context, and display helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape

import duckdb
import pandas as pd
import streamlit as st

from complexity_lab.app_state import GlobalContext, normalized_year_range
from complexity_lab.config import settings
from complexity_lab.data.access import (
    DataCutoff,
    maker_options,
    state_dimension,
    table_exists,
    vahan_cutoff,
)
from complexity_lab.persistence import list_saved_views, save_view
from complexity_lab.research_graph import PAGE_GRAPH, PageNode, get_page_node
from complexity_lab.research_session import ResearchSession
from complexity_lab.viz import use_lab_theme

use_lab_theme()


@dataclass(frozen=True)
class PageContext:
    filters: GlobalContext
    cutoff: DataCutoff


NAV_SECTIONS = ("Observe", "Explain", "Anticipate", "Research", "System")


def _page_link_path(node: PageNode) -> str:
    return node.app_path.removeprefix("app/")


def _page_route(node: PageNode) -> str:
    if node.app_path == "app/Home.py":
        return "/"
    stem = _page_link_path(node).removesuffix(".py").split("/")[-1]
    return "/" + re.sub(r"^\d+_", "", stem)


def _inject_lab_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"],
        [data-testid="stSidebarNavItems"] {
          display: none !important;
          height: 0 !important;
          overflow: hidden !important;
        }
        .block-container {
          padding-top: 1.15rem;
          padding-bottom: 3rem;
          max-width: 1280px;
        }
        .stApp {
          background:
            linear-gradient(180deg, rgba(250,249,244,.96), rgba(245,246,241,.96));
        }
        section[data-testid="stSidebar"] {
          background: #171b1a;
          border-right: 1px solid rgba(255,255,255,.08);
        }
        section[data-testid="stSidebar"] * {color: rgba(255,255,255,.88);}
        section[data-testid="stSidebar"] a,
        section[data-testid="stSidebar"] a *,
        section[data-testid="stSidebar"] p {
          color: rgba(255,255,255,.9) !important;
          opacity: 1 !important;
        }
        section[data-testid="stSidebar"] a {
          border-radius:.45rem;
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stCaptionContainer {color: rgba(255,255,255,.72);}
        section[data-testid="stSidebar"] .stButton button,
        section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
          border-color: rgba(255,255,255,.18);
          background: rgba(255,255,255,.06);
        }
        .lab-nav-brand {
          display:flex; align-items:center; gap:.65rem; margin:.2rem 0 1rem;
        }
        .lab-nav-mark {
          width:2.15rem; height:2.15rem; border-radius:.5rem; display:grid; place-items:center;
          background:#E4572E; color:#fff; font-weight:800; letter-spacing:0;
        }
        .lab-nav-title {font-size:.95rem; font-weight:760; line-height:1.1;}
        .lab-nav-subtitle {font-size:.72rem; color:rgba(255,255,255,.6);}
        .lab-nav-section {
          margin:.85rem 0 .25rem; font-size:.68rem; font-weight:760; letter-spacing:.12em;
          text-transform:uppercase; color:rgba(255,255,255,.48);
        }
        .lab-nav-link {
          display:block; padding:.45rem .6rem; margin:.12rem 0; border-radius:.45rem;
          color:rgba(255,255,255,.9) !important; text-decoration:none !important;
          font-size:.86rem; line-height:1.25;
        }
        .lab-nav-link.active {
          background:rgba(165,174,192,.2); font-weight:760;
        }
        .lab-nav-link:hover {background:rgba(255,255,255,.08);}
        .lab-data-pill {
          border:1px solid rgba(255,255,255,.16); border-radius:.55rem;
          background:rgba(255,255,255,.06); padding:.7rem .78rem; margin:1rem 0 .45rem;
        }
        .lab-data-pill strong {display:block; font-size:.78rem;}
        .lab-data-pill span {display:block; margin-top:.25rem; color:rgba(255,255,255,.62); font-size:.72rem;}
        .lab-shell {
          border:1px solid rgba(40,45,42,.12); background:rgba(255,255,255,.74);
          color:#101412 !important;
          border-radius:.65rem; padding:1.05rem 1.15rem .9rem; margin:.15rem 0 1rem;
          box-shadow:0 10px 28px rgba(28,32,28,.05);
        }
        .lab-shell * {color:inherit;}
        .lab-shell-top {
          display:flex; justify-content:space-between; align-items:flex-start; gap:1.25rem;
        }
        .lab-eyebrow {font-size:.72rem; font-weight:800; letter-spacing:.12em;
          text-transform:uppercase; color:#E4572E; margin-bottom:.2rem}
        .lab-title {font-size:2.25rem; line-height:1.06; font-weight:790; letter-spacing:0; margin:0; color:#101412 !important;}
        .lab-deck {font-size:1.01rem; color:rgba(16,20,18,.68) !important; max-width:820px; margin:.55rem 0 .8rem}
        .lab-actions {min-width:280px; display:flex; flex-direction:column; gap:.65rem; align-items:flex-end;}
        .lab-command {
          width:100%; border:1px solid rgba(40,45,42,.13); border-radius:.55rem; padding:.58rem .72rem;
          background:#fff; color:rgba(16,20,18,.55); font-size:.82rem;
        }
        .lab-badges {display:flex; gap:.4rem; flex-wrap:wrap;}
        .lab-badge {display:inline-flex; align-items:center; min-height:1.72rem; padding:.18rem .58rem;
          border:1px solid rgba(40,45,42,.14); border-radius:999px; font-size:.74rem; font-weight:650;
          background:#fff; color:rgba(16,20,18,.78) !important;}
        .lab-badge.evidence {border-color:rgba(228,87,46,.38); color:#A63B1E !important; background:rgba(228,87,46,.08);}
        .lab-finding {border-left:4px solid #E4572E; border-radius:.35rem; padding:.75rem 1rem;
          background:rgba(228,87,46,.08); margin:.8rem 0 1.05rem}
        .lab-warning {
          border:1px solid rgba(181,133,0,.28); border-left:4px solid #D49A00;
          border-radius:.55rem; padding:.75rem .95rem; margin:.8rem 0 1rem;
          background:rgba(255,246,181,.92); color:#101412 !important; font-weight:650;
        }
        .lab-compass {
          display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:.75rem;
          margin:.7rem 0 1.1rem;
        }
        .lab-compass-card {
          border:1px solid rgba(40,45,42,.12); border-radius:.55rem; background:rgba(255,255,255,.7);
          padding:.75rem .85rem; min-height:5.2rem;
        }
        .lab-compass-card h4 {
          margin:0 0 .35rem; color:#E4572E; font-size:.74rem; letter-spacing:.08em;
          text-transform:uppercase;
        }
        .lab-compass-card p {margin:0; color:rgba(16,20,18,.68); font-size:.81rem; line-height:1.35;}
        .lab-section-band {
          border:1px solid rgba(40,45,42,.12); border-radius:.55rem; background:rgba(255,255,255,.72);
          padding:1rem; margin:.75rem 0 1rem;
        }
        .lab-path-card {
          border:1px solid rgba(40,45,42,.13); border-radius:.55rem; background:#fff;
          padding:.85rem; min-height:7rem;
        }
        .lab-path-card strong {display:block; margin-bottom:.35rem; font-size:.9rem;}
        .lab-path-card span {display:block; color:rgba(16,20,18,.62); font-size:.78rem; line-height:1.35;}
        div[data-testid="stMetric"] {
          border:1px solid rgba(40,45,42,.12); background:rgba(255,255,255,.78);
          border-radius:.55rem; padding:.8rem .85rem;
        }
        div[data-testid="stMetric"] label {font-weight:700; color:rgba(16,20,18,.62);}
        div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {
          border-radius:.55rem; overflow:hidden;
        }
        div[data-testid="stAlert"] {
          border-radius:.55rem;
          background:rgba(255,246,181,.88);
        }
        div[data-testid="stAlert"] *,
        div[data-testid="stAlert"] p {
          color:#101412 !important;
          opacity:1 !important;
        }
        .stTabs [data-baseweb="tab-list"] {gap:.35rem;}
        .stTabs [data-baseweb="tab"] {
          border:1px solid rgba(40,45,42,.12); border-radius:999px; padding:.35rem .7rem;
          background:rgba(255,255,255,.62);
        }
        @media (max-width: 900px) {
          .lab-shell-top, .lab-compass {display:block;}
          .lab-actions {align-items:stretch; margin-top:.9rem;}
          .lab-compass-card {margin-bottom:.55rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_nav(current_title: str) -> None:
    st.markdown(
        """
        <div class="lab-nav-brand">
          <div class="lab-nav-mark">CL</div>
          <div>
            <div class="lab-nav-title">Complexity Lab</div>
            <div class="lab-nav-subtitle">research cockpit</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    query_text = st.text_input(
        "Jump/search",
        key="lab_nav_search",
        placeholder="State, OEM, forecast, experiment",
        label_visibility="collapsed",
    ).strip().lower()
    for section in NAV_SECTIONS:
        nodes = [node for node in PAGE_GRAPH if node.section == section]
        if query_text:
            nodes = [
                node for node in nodes
                if query_text in node.title.lower() or query_text in section.lower()
            ]
        if not nodes:
            continue
        st.markdown(f'<div class="lab-nav-section">{section}</div>', unsafe_allow_html=True)
        for node in nodes:
            label = f"{'● ' if node.title == current_title else ''}{node.title}"
            active = " active" if node.title == current_title else ""
            st.markdown(
                f'<a class="lab-nav-link{active}" href="{_page_route(node)}" target="_self">{escape(label)}</a>',
                unsafe_allow_html=True,
            )


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
    current = {key: values[-1] for key, values in _query_dict().items() if values}
    global_keys = {"from", "to", "source", "coverage", "states", "fuels", "oems", "segments"}
    merged = {key: value for key, value in current.items() if key not in global_keys}
    merged.update(desired)
    if current != merged:
        st.query_params.from_dict(merged)


def global_filters(current_title: str) -> PageContext:
    states, oems, cutoff, has_wholesale = _shell_options()
    min_year = int(query("SELECT MIN(year) AS y FROM panel_state_year")["y"][0])
    max_year = int(query("SELECT MAX(year) AS y FROM panel_state_year")["y"][0])
    initial = GlobalContext.from_query_params(
        {
            **({"coverage": "available"} if "coverage" not in st.query_params else {}),
            **_query_dict(),
        },
        min_year=min_year,
        max_year=max_year,
        default_end=cutoff.latest_observed_year,
    )

    if "_lab_global_initialized" not in st.session_state:
        st.session_state["_lab_global_initialized"] = True

    # Streamlit removes page-scoped widget keys during multipage navigation while
    # leaving ordinary session keys intact. Restore and validate every shared
    # control before constructing its widget.
    fallback_years = (initial.year_start, initial.year_end)
    st.session_state["global_years"] = normalized_year_range(
        st.session_state.get("global_years"),
        fallback=fallback_years,
        min_year=min_year,
        max_year=max_year,
    )
    st.session_state.setdefault("global_states", list(initial.states))
    st.session_state.setdefault("global_fuels", list(initial.fuels))
    st.session_state.setdefault("global_oems", list(initial.oems))
    if st.session_state.get("global_coverage") not in {"complete", "available"}:
        st.session_state["global_coverage"] = initial.coverage

    state_names = dict(zip(states["state_code"], states["state_name"], strict=True))
    with st.sidebar:
        _render_sidebar_nav(current_title)
        st.markdown(
            f"""
            <div class="lab-data-pill">
              <strong>Vahan through {cutoff.latest_period}</strong>
              <span>{'wholesale available locally' if has_wholesale else 'public build: retail only'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
    _inject_lab_css()
    context = global_filters(title)
    filter_scope = (
        f"{len(context.filters.states)} selected states"
        if context.filters.states
        else "All India"
    )
    badges = [
        evidence,
        f"Vahan through {context.cutoff.latest_period}",
        f"Latest observed {context.cutoff.latest_period}",
        f"{filter_scope}, {context.filters.year_start}-{context.filters.year_end}",
    ]
    badge_html = "".join(
        f'<span class="lab-badge {"evidence" if index == 0 else ""}">{escape(badge)}</span>'
        for index, badge in enumerate(badges)
    )
    st.markdown(
        f"""
        <section class="lab-shell">
          <div class="lab-shell-top">
            <div>
              <div class="lab-eyebrow">{escape(section)}</div>
              <div class="lab-title">{escape(title)}</div>
              <div class="lab-deck">{escape(description)}</div>
              <div class="lab-badges">{badge_html}</div>
            </div>
            <div class="lab-actions">
              <div class="lab-command">Search states, OEMs, experiments</div>
              <div class="lab-badges">
                <span class="lab-badge">Save locally</span>
                <span class="lab-badge">Export context</span>
              </div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if context.filters.coverage == "available" and context.filters.year_end > context.cutoff.latest_complete_year:
        st.markdown(
            f'<div class="lab-warning">{escape(context.cutoff.warning)}</div>',
            unsafe_allow_html=True,
        )

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
        session = ResearchSession(
            page=title,
            global_context=context.filters,
            evidence=evidence,
            data_cutoff=context.cutoff.latest_period,
            limitations=limitations,
        )
        st.download_button(
            "Download research session",
            json.dumps(session.to_payload(), indent=2, default=str),
            file_name="complexity-lab-session.json",
            mime="application/json",
            key=f"session-download-{title}",
        )

    try:
        node = get_page_node(title)
    except KeyError:
        node = None
    if node is not None:
        methods = ", ".join(node.experiment_slugs[:3]) if node.experiment_slugs else "No direct experiment"
        notebook = node.notebooks[0] if node.notebooks else "No notebook mapped"
        st.markdown(
            f"""
            <div class="lab-compass">
              <div class="lab-compass-card">
                <h4>Use this page to</h4>
                <p>{escape('; '.join(node.research_actions[:3]) or 'Explore the current context')}</p>
              </div>
              <div class="lab-compass-card">
                <h4>Truth guardrails</h4>
                <p>{escape('; '.join(node.truth_guardrails[:2]) or 'Respect evidence labels and data cutoff')}</p>
              </div>
              <div class="lab-compass-card">
                <h4>Runnable methods</h4>
                <p>{escape(methods)}</p>
              </div>
              <div class="lab-compass-card">
                <h4>Notebook link</h4>
                <p>{escape(notebook)}</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
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

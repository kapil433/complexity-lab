"""Shared helpers for the Streamlit lab pages."""

from __future__ import annotations

import json

import duckdb
import pandas as pd
import streamlit as st

from complexity_lab.config import settings


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not settings.db_path.exists():
        st.error("data/lab.duckdb not found — run `uv run lab ingest && uv run lab panel` first.")
        st.stop()
    return duckdb.connect(str(settings.db_path), read_only=True)


@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    return get_connection().execute(sql).df()


@st.cache_data(ttl=3600)
def load_geojson() -> dict:
    return json.loads(settings.geojson_path.read_text(encoding="utf-8"))


def year_range_slider(df: pd.DataFrame, key: str = "years") -> tuple[int, int]:
    lo, hi = int(df["year"].min()), int(df["year"].max())
    return st.slider("Years", lo, hi, (max(lo, 2013), hi - 1), key=key)


def render_card(card_id: str) -> None:
    """Collapsible experiment card (blueprint §7.5): background, concepts, math,
    interpretation — so every page explains itself."""
    from complexity_lab.experiments.cards import get_card

    card = get_card(card_id)
    with st.expander(f"📖 About this experiment — {card.name}", expanded=False):
        st.caption(f"`{card.id}` · {card.category} · {card.tier}")
        st.markdown(f"**Why this matters.** {card.question}")
        st.markdown(f"**Method.** {card.method}")

        tab_how, tab_concepts, tab_math, tab_read, tab_limits = st.tabs(
            ["How it works", "Concepts", "Math", "Read the results", "Limits & uses"]
        )
        with tab_how:
            for i, step in enumerate(card.how_it_works, 1):
                st.markdown(f"{i}. {step}")
            st.caption("Data: " + "; ".join(card.data_used))
        with tab_concepts:
            for term, meaning in card.plain_english.items():
                st.markdown(f"- **{term}** — {meaning}")
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
    """Checkbox + policy event overlay for any time-series figure."""
    from complexity_lab.viz import add_event_markers, load_events

    if st.checkbox("Show policy events", value=True, key=key):
        events = load_events(get_connection())
        fig = add_event_markers(fig, events, max_labels=12)
    return fig

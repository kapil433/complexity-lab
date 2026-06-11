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

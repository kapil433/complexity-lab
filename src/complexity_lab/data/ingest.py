"""Ingest the VAHAN master bundle and reference CSVs into DuckDB.

The master bundle (``data/raw/vahan_master.json.gz``) is the canonical source:
index-encoded rows ``[region_idx, cal_year, month, fy_label, maker_idx, fuel_idx, count]``.

Caveats handled here (see the bundle README):
- 'All India' rows are pre-aggregated — never sum states to get All India.
- Partial calendar years / FYs are flagged in ``meta`` and stored in the ``meta`` table.
- Telangana split from Andhra Pradesh in June 2014 (kept as-is; flagged in events).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import duckdb
import pandas as pd

from complexity_lab.config import settings
from complexity_lab.data.reference import load_reference_tables

REQUIRED_KEYS = {"regions", "makers", "fuels", "data", "meta"}


def load_master(path: Path | None = None) -> dict:
    """Load and parse the gzipped master bundle."""
    path = path or settings.master_bundle
    with gzip.open(path, "rt", encoding="utf-8") as f:
        bundle = json.load(f)
    missing = REQUIRED_KEYS - bundle.keys()
    if missing:
        raise ValueError(f"Master bundle missing keys: {missing}")
    return bundle


def decode_registrations(bundle: dict) -> pd.DataFrame:
    """Decode index-encoded rows into a long dataframe."""
    regions = bundle["regions"]
    makers = bundle["makers"]
    fuels = bundle["fuels"]
    df = pd.DataFrame(
        bundle["data"],
        columns=["region_idx", "year", "month", "fy", "maker_idx", "fuel_idx", "count"],
    )
    df["state_name"] = df["region_idx"].map(dict(enumerate(regions)))
    df["maker"] = df["maker_idx"].map(dict(enumerate(makers)))
    df["fuel"] = df["fuel_idx"].map(dict(enumerate(fuels)))
    df = df.drop(columns=["region_idx", "maker_idx", "fuel_idx"])
    df["count"] = df["count"].astype("int64")
    return df


def decode_events(bundle: dict) -> pd.DataFrame:
    """Policy/structural events embedded in the bundle (BS6, FAME, COVID, ...)."""
    events = bundle.get("events", [])
    if not events:
        return pd.DataFrame()
    df = pd.json_normalize(events)
    # params can be a list — store as JSON text for DuckDB friendliness
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].map(json.dumps)
    return df


def connect(db_path: Path | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path or settings.db_path), read_only=read_only)


def ingest(db_path: Path | None = None, bundle_path: Path | None = None) -> dict:
    """Full ingest: master bundle + reference CSVs -> DuckDB. Returns a summary."""
    bundle = load_master(bundle_path)
    regs = decode_registrations(bundle)
    events = decode_events(bundle)

    con = connect(db_path)
    try:
        # dim_state first — registrations join against it
        ref_summary = load_reference_tables(con)

        con.register("regs_df", regs)
        con.execute("""
            CREATE OR REPLACE TABLE registrations AS
            SELECT s.state_code,
                   r.state_name,
                   r.year, r.month, r.fy,
                   r.maker, r.fuel, r."count"
            FROM regs_df r
            LEFT JOIN dim_state s ON r.state_name = s.state_name
        """)
        unmatched = con.execute(
            "SELECT DISTINCT state_name FROM registrations WHERE state_code IS NULL"
        ).fetchall()
        if unmatched:
            raise ValueError(f"States missing from dim_state: {[u[0] for u in unmatched]}")

        if not events.empty:
            con.register("events_df", events)
            con.execute("CREATE OR REPLACE TABLE events AS SELECT * FROM events_df")

        meta = bundle["meta"]
        con.execute("CREATE OR REPLACE TABLE meta (key VARCHAR, value JSON)")
        for k, v in meta.items():
            con.execute("INSERT INTO meta VALUES (?, ?)", [k, json.dumps(v)])

        n_rows = con.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
        n_states = con.execute(
            "SELECT COUNT(DISTINCT state_code) FROM registrations WHERE state_code <> 'ALL'"
        ).fetchone()[0]
        return {
            "registrations": n_rows,
            "states": n_states,
            "events": len(events),
            "reference_tables": ref_summary,
        }
    finally:
        con.close()

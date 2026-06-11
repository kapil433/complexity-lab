"""Load and validate the enrichment reference CSVs into DuckDB.

Every CSV in ``data/reference/`` becomes a table. ``states.csv`` becomes
``dim_state`` (the canonical state dimension); every other file becomes
``ref_<stem>`` and, if it has a ``state_code`` column, is validated against
``dim_state``.

Reference CSVs use ``#`` comment lines at the top for provenance notes and
carry ``source`` / ``quality`` columns so estimates stay distinguishable from
official figures all the way into analysis.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from complexity_lab.config import settings


def read_reference_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, comment="#")


def load_reference_tables(
    con: duckdb.DuckDBPyConnection, reference_dir: Path | None = None
) -> dict[str, int]:
    """Load states.csv -> dim_state, then every other CSV -> ref_<stem>."""
    ref_dir = reference_dir or settings.reference_dir
    states_path = ref_dir / "states.csv"
    if not states_path.exists():
        raise FileNotFoundError(f"Canonical state dimension not found: {states_path}")

    states = read_reference_csv(states_path)
    required = {"state_code", "state_name", "geojson_name", "zone", "is_ut"}
    missing = required - set(states.columns)
    if missing:
        raise ValueError(f"states.csv missing columns: {missing}")
    if states["state_code"].duplicated().any():
        raise ValueError("states.csv has duplicate state_code values")

    con.register("states_df", states)
    con.execute("CREATE OR REPLACE TABLE dim_state AS SELECT * FROM states_df")
    valid_codes = set(states["state_code"])

    summary: dict[str, int] = {"dim_state": len(states)}
    for path in sorted(ref_dir.glob("*.csv")):
        if path.name == "states.csv":
            continue
        df = read_reference_csv(path)
        if "state_code" in df.columns:
            bad = set(df["state_code"].dropna()) - valid_codes
            if bad:
                raise ValueError(f"{path.name}: unknown state codes {sorted(bad)}")
        table = f"ref_{path.stem}"
        con.register("ref_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM ref_df")
        con.unregister("ref_df")
        summary[table] = len(df)
    return summary

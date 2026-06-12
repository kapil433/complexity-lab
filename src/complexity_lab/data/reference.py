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

CATALOG_COLUMNS = {
    "dataset",
    "file",
    "status",
    "geography",
    "time_coverage",
    "temporal_type",
    "quality_summary",
    "approved_use",
    "not_available",
    "app_behavior",
    "source_url",
}
VALID_STATUSES = {"usable", "constrained", "unavailable"}
VALID_APP_BEHAVIORS = {"show", "warn", "hide"}


def read_reference_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, comment="#")


def validate_reference_catalog(reference_dir: Path) -> pd.DataFrame | None:
    """Validate the optional governing catalog against files in the directory."""
    path = reference_dir / "reference_catalog.csv"
    if not path.exists():
        return None

    catalog = read_reference_csv(path).fillna("")
    missing = CATALOG_COLUMNS - set(catalog.columns)
    if missing:
        raise ValueError(f"reference_catalog.csv missing columns: {sorted(missing)}")
    if catalog["dataset"].duplicated().any() or catalog["file"].duplicated().any():
        raise ValueError("reference_catalog.csv has duplicate dataset or file entries")

    bad_status = set(catalog["status"]) - VALID_STATUSES
    if bad_status:
        raise ValueError(f"reference_catalog.csv has invalid statuses: {sorted(bad_status)}")
    bad_behavior = set(catalog["app_behavior"]) - VALID_APP_BEHAVIORS
    if bad_behavior:
        raise ValueError(
            f"reference_catalog.csv has invalid app_behavior values: {sorted(bad_behavior)}"
        )

    actual = {p.name for p in reference_dir.glob("*.csv")} - {"reference_catalog.csv"}
    declared = set(catalog["file"])
    if actual != declared:
        raise ValueError(
            "reference_catalog.csv file mismatch: "
            f"missing entries={sorted(actual - declared)}, missing files={sorted(declared - actual)}"
        )
    return catalog


def build_reference_availability(
    reference_dir: Path, catalog: pd.DataFrame
) -> pd.DataFrame:
    """Materialize one row per reference dataset with observed file facts."""
    rows = []
    for item in catalog.to_dict("records"):
        df = read_reference_csv(reference_dir / item["file"])
        row = dict(item)
        row["row_count"] = len(df)
        row["column_count"] = len(df.columns)
        row["state_codes_present"] = int(df["state_code"].nunique()) if "state_code" in df else None
        row["quality_values"] = (
            ", ".join(sorted(map(str, df["quality"].dropna().unique())))
            if "quality" in df
            else ""
        )
        rows.append(row)
    return pd.DataFrame(rows)


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

    catalog = validate_reference_catalog(ref_dir)

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

    if catalog is not None:
        availability = build_reference_availability(ref_dir, catalog)
        con.register("availability_df", availability)
        con.execute(
            "CREATE OR REPLACE TABLE reference_availability AS SELECT * FROM availability_df"
        )
        con.unregister("availability_df")
        summary["reference_availability"] = len(availability)
    return summary

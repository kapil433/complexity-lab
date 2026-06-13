"""Normalize sparse infrastructure and unavailable-market reference tables.

This script does not create historical observations. It adds dated snapshot and
reconciliation metadata to the available EV/CNG files, and replaces the dealer
placeholder with an explicit empty schema.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference"


def write_csv(path: Path, comments: list[str], df: pd.DataFrame) -> None:
    prefix = "".join(f"# {comment}\n" for comment in comments)
    path.write_text(prefix + df.to_csv(index=False, lineterminator="\n"), encoding="utf-8")


def normalize_cng() -> pd.DataFrame:
    df = pd.read_csv(REFERENCE / "cng_stations.csv", comment="#")
    df["snapshot_date"] = df["year"].map({2024: "2024-05-31", 2025: "2025-03-31"})
    df["coverage_scope"] = "national_total"
    df.loc[(df["year"] == 2024) & (df["state_code"] != "ALL"), "coverage_scope"] = (
        "complete_state_allocation"
    )
    df["state_allocation_coverage_pct"] = pd.NA
    df.loc[df["year"] == 2024, "state_allocation_coverage_pct"] = 100.0
    df["reconciliation_note"] = df["year"].map(
        {
            2024: "State rows reconcile exactly to the 6,890 national total.",
            2025: "Only the national total is available; no state allocation is stored.",
        }
    )
    return df


def normalize_ev() -> pd.DataFrame:
    df = pd.read_csv(REFERENCE / "ev_charging.csv", comment="#")
    df["snapshot_date"] = df["year"].map({2024: "2024-02-02", 2025: "2025-08-01"})
    df["coverage_scope"] = "national_total"
    df.loc[(df["year"] == 2024) & (df["state_code"] != "ALL"), "coverage_scope"] = (
        "selected_state_snapshot"
    )
    df.loc[(df["year"] == 2025) & (df["state_code"] != "ALL"), "coverage_scope"] = (
        "incomplete_state_allocation"
    )
    df["state_allocation_coverage_pct"] = pd.NA
    state_2025 = df[(df["year"] == 2025) & (df["state_code"] != "ALL")][
        "public_chargers"
    ].sum()
    national_2025 = df[(df["year"] == 2025) & (df["state_code"] == "ALL")][
        "public_chargers"
    ].iloc[0]
    coverage = round(100 * state_2025 / national_2025, 2)
    df.loc[df["year"] == 2025, "state_allocation_coverage_pct"] = coverage
    df["reconciliation_note"] = ""
    df.loc[df["year"] == 2024, "reconciliation_note"] = (
        "Only Maharashtra and Delhi state rows are stored; do not sum them as India."
    )
    df.loc[df["year"] == 2025, "reconciliation_note"] = (
        f"Stored state rows sum to {state_2025:,}, or {coverage:.2f}% of the "
        f"{national_2025:,} national total; approximate rows are not a census."
    )
    return df


def empty_dealer_schema() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "state_code",
            "year",
            "oem",
            "outlet_id",
            "outlet_name",
            "city",
            "outlet_type",
            "source",
            "quality",
            "snapshot_date",
        ]
    )


def main() -> None:
    write_csv(
        REFERENCE / "cng_stations.csv",
        [
            "Dated CNG station snapshots; no interpolation or invented history.",
            "2024 state rows reconcile to the national total; 2025 is national only.",
        ],
        normalize_cng(),
    )
    write_csv(
        REFERENCE / "ev_charging.csv",
        [
            "Dated public-EV-charging snapshots; no interpolation or invented history.",
            "The 2025 state allocation is incomplete and includes approximate rows.",
        ],
        normalize_ev(),
    )
    write_csv(
        REFERENCE / "dealer_counts.csv",
        [
            "Empty schema: no defensible state x OEM x year dealer panel is available.",
            "Populate only from dated, deduplicated OEM/FADA outlet snapshots.",
        ],
        empty_dealer_schema(),
    )
    print("Normalized CNG and EV snapshots; dealer_counts.csv now has zero data rows")


if __name__ == "__main__":
    main()

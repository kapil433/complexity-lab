"""Generate derived reference tables from audited local inputs.

Outputs:
- state_credit_depth.csv: broad scheduled-bank personal-loan context.
- vehicle_lifetime_tax.csv: normalized fuel rows from the current tax cross-section.
- policy_events_canonical.csv: one schema for curated and bundle events.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference"


def write_csv(path: Path, comment: str, df: pd.DataFrame) -> None:
    path.write_text(
        comment + df.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
    )


def build_credit_depth() -> pd.DataFrame:
    loans = pd.read_csv(REFERENCE / "state_personal_loans.csv", comment="#")
    population = pd.read_csv(REFERENCE / "state_population_annual.csv", comment="#")[
        ["state_code", "year", "population_mn", "quality"]
    ].rename(columns={"quality": "population_quality"})
    df = loans.merge(population, on=["state_code", "year"], how="inner")
    df = df[df["year"].between(2012, 2025)].copy()
    df["personal_loans_per_capita_inr"] = (
        df["personal_loans_outstanding_crore"] * 10 / df["population_mn"]
    ).round(2)
    df["personal_loans_yoy_growth_pct"] = (
        df.groupby("state_code")["personal_loans_outstanding_crore"].pct_change() * 100
    ).round(3)
    df["source"] = (
        "RBI Table 159 personal loans; per-capita denominator from "
        "state_population_annual.csv"
    )
    df["quality"] = "estimate"
    return df[
        [
            "state_code",
            "year",
            "personal_loans_outstanding_crore",
            "personal_loans_per_capita_inr",
            "personal_loans_yoy_growth_pct",
            "population_mn",
            "source",
            "quality",
            "geography_note",
        ]
    ].sort_values(["state_code", "year"])


def build_lifetime_tax() -> pd.DataFrame:
    base = pd.read_csv(REFERENCE / "road_tax.csv", comment="#")
    rows: list[dict] = []
    for row in base.itertuples(index=False):
        for fuel in ["Petrol", "Diesel", "CNG", "Strong Hybrid", "EV"]:
            rate = row.ev_rate_pct if fuel == "EV" else row.rate_pct_10l
            rows.append(
                {
                    "state_code": row.state_code,
                    "fuel": fuel,
                    "vehicle_price_basis_inr": 1_000_000,
                    "lifetime_tax_rate_pct": rate,
                    "as_of": row.as_of,
                    "method": (
                        "EV-specific rate from source cross-section"
                        if fuel == "EV"
                        else "ICE benchmark rate reused; source does not distinguish this fuel"
                    ),
                    "source": row.source,
                    "quality": row.quality,
                }
            )
    return pd.DataFrame(rows).sort_values(["state_code", "fuel"])


def build_policy_events() -> pd.DataFrame:
    curated = pd.read_csv(REFERENCE / "policy_events.csv", comment="#").fillna("")
    curated_rows = []
    for row in curated.to_dict("records"):
        curated_rows.append(
            {
                "event_id": f"curated:{row['event_id']}",
                "date": row["date"],
                "date_end": row["date"],
                "state_code": row["state_code"],
                "category": row["category"],
                "type": row["category"],
                "tier": 2,
                "label": row["label"],
                "detail": row["detail"],
                "source": row["source"],
                "quality": row["quality"],
                "origin": "curated_reference",
            }
        )

    with gzip.open(ROOT / "data" / "raw" / "vahan_master.json.gz", "rt", encoding="utf-8") as f:
        bundle = json.load(f)
    bundle_rows = []
    for row in bundle.get("events", []):
        bundle_rows.append(
            {
                "event_id": f"bundle:{row['id']}",
                "date": row["date"],
                "date_end": row.get("date_end", row["date"]),
                "state_code": "AP" if row.get("ap_only") else "ALL",
                "category": row.get("type", "event"),
                "type": row.get("type", "event"),
                "tier": row.get("tier", 1),
                "label": row["label"],
                "detail": row.get("detail", ""),
                "source": "; ".join(row.get("sources", [])),
                "quality": "reported",
                "origin": "vahan_bundle",
            }
        )

    df = pd.DataFrame([*bundle_rows, *curated_rows])
    df["possible_overlap"] = df.duplicated(["date", "state_code", "category"], keep=False)
    return df.sort_values(["date", "tier", "event_id"])


def main() -> None:
    credit = build_credit_depth()
    write_csv(
        REFERENCE / "state_credit_depth.csv",
        "# Broad personal-loan credit depth; not vehicle-finance penetration.\n"
        "# Loan stocks are official RBI data; per-capita values use estimated population.\n",
        credit,
    )
    tax = build_lifetime_tax()
    write_csv(
        REFERENCE / "vehicle_lifetime_tax.csv",
        "# Normalized current lifetime-tax benchmark by fuel for a roughly INR 10 lakh car.\n"
        "# Non-EV fuel rows repeat the same ICE benchmark unless the source distinguished fuel.\n",
        tax,
    )
    events = build_policy_events()
    write_csv(
        REFERENCE / "policy_events_canonical.csv",
        "# Unified curated and Vahan-bundle event timeline; possible_overlap flags collisions.\n"
        "# Event annotations provide context, not causal identification.\n",
        events,
    )
    print(
        f"Wrote credit={len(credit)}, tax={len(tax)}, events={len(events)} reference rows"
    )


if __name__ == "__main__":
    main()

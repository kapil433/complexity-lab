"""Generate transparent annual state population denominators for 2012-2026.

The generator geometrically interpolates between the existing Census-2011 and
projected-2024 anchors, then extrapolates the same state-specific rate to 2026.
Urban and rural counts use fixed Census-2011 shares and therefore do not represent
annual urbanization change.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / "data" / "reference" / "population.csv"
URBANIZATION = ROOT / "data" / "reference" / "urbanization.csv"
OUTPUT = ROOT / "data" / "reference" / "state_population_annual.csv"


def build() -> pd.DataFrame:
    population = pd.read_csv(POPULATION, comment="#")
    urbanization = pd.read_csv(URBANIZATION, comment="#")[
        ["state_code", "urban_pct", "rural_pct"]
    ]
    anchors = population.merge(urbanization, on="state_code", validate="one_to_one")
    rows: list[dict] = []
    years_between = 2024 - 2011
    for row in anchors.itertuples(index=False):
        annual_factor = (row.proj_2024_mn / row.census_2011_mn) ** (1 / years_between)
        for year in range(2012, 2027):
            total = row.census_2011_mn * annual_factor ** (year - 2011)
            method = (
                "geometric interpolation between 2011 and 2024 anchors"
                if year <= 2024
                else "extrapolation of 2011-2024 geometric growth rate"
            )
            rows.append(
                {
                    "state_code": row.state_code,
                    "year": year,
                    "population_mn": round(total, 4),
                    "urban_population_mn": round(total * row.urban_pct / 100, 4),
                    "rural_population_mn": round(total * row.rural_pct / 100, 4),
                    "urban_pct_basis": row.urban_pct,
                    "rural_pct_basis": row.rural_pct,
                    "urban_share_year": 2011,
                    "method": method,
                    "source": (
                        "Derived from data/reference/population.csv anchors and "
                        "Census-2011 urban/rural shares"
                    ),
                    "quality": "estimate",
                }
            )
    return pd.DataFrame(rows).sort_values(["state_code", "year"])


def main() -> None:
    df = build()
    comment = (
        "# Annual population denominators, 2012-2026 (million people).\n"
        "# Estimated by geometric interpolation/extrapolation from local 2011 and 2024 anchors.\n"
        "# Urban/rural counts hold Census-2011 shares fixed; they are not annual urbanization estimates.\n"
    )
    OUTPUT.write_text(
        comment + df.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(df)} rows, {df['state_code'].nunique()} geographies, "
        f"{df['year'].min()}..{df['year'].max()} -> {OUTPUT}"
    )


if __name__ == "__main__":
    main()

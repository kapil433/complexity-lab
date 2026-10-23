"""Read-only extracts for playground experiments.

Queries use the panel tables built by ``lab panel``. They do not sum state
rows into an All India total.
"""

from __future__ import annotations

import duckdb
import pandas as pd

NATIONAL_MONTH_SQL = """
SELECT date, year, month, total_regs, ev_regs, cng_regs, petrol_regs, diesel_regs,
       hybrid_regs, ev_share, cng_share, petrol_share, diesel_share, hybrid_share,
       hhi_oem, entropy_oem
FROM panel_state_month
WHERE state_code = 'ALL'
ORDER BY date
"""

NATIONAL_YEAR_SQL = """
SELECT year, total_regs, ev_regs, cng_regs, petrol_regs, diesel_regs, hybrid_regs,
       ev_share, cng_share, petrol_share, diesel_share, hybrid_share,
       yoy_growth, hhi_oem, entropy_oem
FROM panel_state_year
WHERE state_code = 'ALL'
ORDER BY year
"""

STATE_YEAR_SQL = """
SELECT state_code,
       state_name,
       year,
       total_regs,
       ev_share,
       cng_share,
       petrol_share,
       diesel_share,
       hybrid_share,
       yoy_growth,
       hhi_oem,
       entropy_oem,
       regs_per_1000_population,
       population_mn,
       population_quality,
       urban_pct,
       pc_income_constant_2011_12_inr AS real_pc_income_inr,
       income_constant_quality,
       gsdp_real_growth_pct AS real_gsdp_growth_pct,
       gsdp_quality,
       personal_loans_per_capita_inr AS broad_credit_per_capita_inr,
       credit_depth_quality,
       petrol_price_inr,
       petrol_price_basis,
       petrol_price_quality,
       diesel_price_inr,
       diesel_price_basis,
       cng_price_inr,
       cng_price_basis,
       cng_price_quality
FROM panel_state_year
WHERE state_code <> 'ALL'
  AND year BETWEEN ? AND ?
ORDER BY state_code, year
"""


def national_month(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = con.execute(NATIONAL_MONTH_SQL).df()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def national_year(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(NATIONAL_YEAR_SQL).df()


def state_year(
    con: duckdb.DuckDBPyConnection, year_start: int, year_end: int
) -> pd.DataFrame:
    return con.execute(STATE_YEAR_SQL, [int(year_start), int(year_end)]).df()


def state_codes(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        """
        SELECT state_code
        FROM dim_state
        WHERE state_code <> 'ALL'
        ORDER BY state_code
        """
    ).fetchall()
    return [row[0] for row in rows]


def monthly_state(
    con: duckdb.DuckDBPyConnection, state_code: str, column: str
) -> pd.Series:
    if column not in {
        "total_regs",
        "ev_regs",
        "cng_regs",
        "petrol_regs",
        "diesel_regs",
        "hybrid_regs",
        "ev_share",
        "cng_share",
        "diesel_share",
    }:
        raise ValueError(f"Refusing unlisted monthly column: {column}")
    frame = con.execute(
        f"""
        SELECT date, {column} AS value
        FROM panel_state_month
        WHERE state_code = ?
        ORDER BY date
        """,
        [state_code],
    ).df()
    series = frame.set_index("date")["value"].astype(float)
    series.index = pd.to_datetime(series.index)
    return series


def oem_edges(con: duckdb.DuckDBPyConnection, year: int) -> pd.DataFrame:
    return con.execute(
        """
        SELECT state_code, maker, regs
        FROM oem_state_edges
        WHERE year = ?
        """,
        [int(year)],
    ).df()


def adjacency(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT state_a, state_b FROM ref_state_adjacency").df()

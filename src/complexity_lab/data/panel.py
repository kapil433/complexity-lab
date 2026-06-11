"""Build the canonical analysis panels in DuckDB.

Two workhorse tables every experiment starts from:

- ``panel_state_month``: state × calendar month — registrations by fuel,
  EV/CNG shares, OEM concentration (HHI), OEM entropy.
- ``panel_state_year``: state × calendar year — the same aggregates plus
  YoY growth and the slow-moving covariates (per-capita income, urbanization,
  CNG stations, EV chargers, fuel prices).

Notes:
- 'All India' (state_code = 'ALL') rows are pre-aggregated upstream and kept
  in the panels; filter them out for cross-state work.
- Income is reported by fiscal year; the year panel joins the FY that starts
  in that calendar year (documented approximation).
"""

from __future__ import annotations

from pathlib import Path

from complexity_lab.data.ingest import connect

_FUEL_PIVOT = """
    SUM("count")                                                   AS total_regs,
    SUM(CASE WHEN fuel = 'EV'            THEN "count" ELSE 0 END)  AS ev_regs,
    SUM(CASE WHEN fuel = 'CNG'           THEN "count" ELSE 0 END)  AS cng_regs,
    SUM(CASE WHEN fuel = 'Petrol'        THEN "count" ELSE 0 END)  AS petrol_regs,
    SUM(CASE WHEN fuel = 'Diesel'        THEN "count" ELSE 0 END)  AS diesel_regs,
    SUM(CASE WHEN fuel = 'Strong Hybrid' THEN "count" ELSE 0 END)  AS hybrid_regs
"""

_SQL_PANEL_MONTH = f"""
CREATE OR REPLACE TABLE panel_state_month AS
WITH base AS (
    SELECT state_code, state_name, year, month, fy,
           {_FUEL_PIVOT}
    FROM registrations
    GROUP BY state_code, state_name, year, month, fy
),
maker_shares AS (
    SELECT state_code, year, month,
           maker,
           SUM("count")::DOUBLE / NULLIF(SUM(SUM("count")) OVER (PARTITION BY state_code, year, month), 0) AS share
    FROM registrations
    GROUP BY state_code, year, month, maker
),
conc AS (
    SELECT state_code, year, month,
           SUM(share * share) * 10000                       AS hhi_oem,
           -SUM(CASE WHEN share > 0 THEN share * LN(share) ELSE 0 END) AS entropy_oem,
           COUNT(*) FILTER (WHERE share > 0)                AS n_oems
    FROM maker_shares
    GROUP BY state_code, year, month
)
SELECT b.*,
       MAKE_DATE(b.year, b.month, 1)                        AS date,
       b.ev_regs::DOUBLE  / NULLIF(b.total_regs, 0)         AS ev_share,
       b.cng_regs::DOUBLE / NULLIF(b.total_regs, 0)         AS cng_share,
       c.hhi_oem, c.entropy_oem, c.n_oems
FROM base b
LEFT JOIN conc c USING (state_code, year, month)
ORDER BY b.state_code, b.year, b.month
"""

_SQL_PANEL_YEAR = f"""
CREATE OR REPLACE TABLE panel_state_year AS
WITH base AS (
    SELECT state_code, state_name, year,
           {_FUEL_PIVOT}
    FROM registrations
    GROUP BY state_code, state_name, year
),
maker_shares AS (
    SELECT state_code, year, maker,
           SUM("count")::DOUBLE / NULLIF(SUM(SUM("count")) OVER (PARTITION BY state_code, year), 0) AS share
    FROM registrations
    GROUP BY state_code, year, maker
),
conc AS (
    SELECT state_code, year,
           SUM(share * share) * 10000                       AS hhi_oem,
           -SUM(CASE WHEN share > 0 THEN share * LN(share) ELSE 0 END) AS entropy_oem,
           COUNT(*) FILTER (WHERE share > 0)                AS n_oems
    FROM maker_shares
    GROUP BY state_code, year
),
enriched AS (
    SELECT b.*,
           PRINTF('%d-%02d', b.year, (b.year + 1) % 100)    AS fy_starting,
           b.ev_regs::DOUBLE  / NULLIF(b.total_regs, 0)     AS ev_share,
           b.cng_regs::DOUBLE / NULLIF(b.total_regs, 0)     AS cng_share,
           c.hhi_oem, c.entropy_oem, c.n_oems
    FROM base b
    LEFT JOIN conc c USING (state_code, year)
)
SELECT e.*,
       e.total_regs::DOUBLE / NULLIF(LAG(e.total_regs) OVER w, 0) - 1 AS yoy_growth,
       inc.pc_nsdp_current_inr                              AS pc_income_inr,
       urb.urban_pct,
       cng.stations                                          AS cng_stations,
       ev.public_chargers                                    AS ev_chargers,
       fp_p.price_avg_inr                                    AS petrol_price_inr,
       fp_d.price_avg_inr                                    AS diesel_price_inr,
       fp_c.price_avg_inr                                    AS cng_price_inr
FROM enriched e
LEFT JOIN ref_state_income inc
       ON inc.state_code = e.state_code AND inc.fy = e.fy_starting
LEFT JOIN ref_urbanization urb
       ON urb.state_code = e.state_code
LEFT JOIN ref_cng_stations cng
       ON cng.state_code = e.state_code AND cng.year = e.year
LEFT JOIN ref_ev_charging ev
       ON ev.state_code = e.state_code AND ev.year = e.year
LEFT JOIN ref_fuel_prices fp_p
       ON fp_p.fuel = 'Petrol'
      AND fp_p.year = e.year
      AND fp_p.state_code = COALESCE(
            (SELECT f2.state_code FROM ref_fuel_prices f2
             WHERE f2.fuel = 'Petrol' AND f2.year = e.year AND f2.state_code = e.state_code
             LIMIT 1), 'ALL')
LEFT JOIN ref_fuel_prices fp_d
       ON fp_d.fuel = 'Diesel'
      AND fp_d.year = e.year
      AND fp_d.state_code = COALESCE(
            (SELECT f2.state_code FROM ref_fuel_prices f2
             WHERE f2.fuel = 'Diesel' AND f2.year = e.year AND f2.state_code = e.state_code
             LIMIT 1), 'ALL')
LEFT JOIN ref_fuel_prices fp_c
       ON fp_c.fuel = 'CNG'
      AND fp_c.year = e.year
      AND fp_c.state_code = COALESCE(
            (SELECT f2.state_code FROM ref_fuel_prices f2
             WHERE f2.fuel = 'CNG' AND f2.year = e.year AND f2.state_code = e.state_code
             LIMIT 1), 'ALL')
WINDOW w AS (PARTITION BY e.state_code ORDER BY e.year)
ORDER BY e.state_code, e.year
"""

_SQL_EDGES = """
CREATE OR REPLACE VIEW oem_state_edges AS
SELECT state_code, state_name, maker, year, fy, SUM("count") AS regs
FROM registrations
WHERE state_code <> 'ALL'
GROUP BY state_code, state_name, maker, year, fy
"""


def build_panels(db_path: Path | None = None) -> dict[str, int]:
    """(Re)build panel tables. Returns row counts."""
    con = connect(db_path)
    try:
        con.execute(_SQL_PANEL_MONTH)
        con.execute(_SQL_PANEL_YEAR)
        con.execute(_SQL_EDGES)
        return {
            "panel_state_month": con.execute("SELECT COUNT(*) FROM panel_state_month").fetchone()[0],
            "panel_state_year": con.execute("SELECT COUNT(*) FROM panel_state_year").fetchone()[0],
        }
    finally:
        con.close()

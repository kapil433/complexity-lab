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
       b.ev_regs::DOUBLE     / NULLIF(b.total_regs, 0)      AS ev_share,
       b.cng_regs::DOUBLE    / NULLIF(b.total_regs, 0)      AS cng_share,
       b.petrol_regs::DOUBLE / NULLIF(b.total_regs, 0)      AS petrol_share,
       b.diesel_regs::DOUBLE / NULLIF(b.total_regs, 0)      AS diesel_share,
       b.hybrid_regs::DOUBLE / NULLIF(b.total_regs, 0)      AS hybrid_share,
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
           b.ev_regs::DOUBLE     / NULLIF(b.total_regs, 0)  AS ev_share,
           b.cng_regs::DOUBLE    / NULLIF(b.total_regs, 0)  AS cng_share,
           b.petrol_regs::DOUBLE / NULLIF(b.total_regs, 0)  AS petrol_share,
           b.diesel_regs::DOUBLE / NULLIF(b.total_regs, 0)  AS diesel_share,
           b.hybrid_regs::DOUBLE / NULLIF(b.total_regs, 0)  AS hybrid_share,
           c.hhi_oem, c.entropy_oem, c.n_oems
    FROM base b
    LEFT JOIN conc c USING (state_code, year)
)
SELECT e.*,
       e.total_regs::DOUBLE / NULLIF(LAG(e.total_regs) OVER w, 0) - 1 AS yoy_growth,
       (e.ev_share     - LAG(e.ev_share)     OVER w) * 100  AS ev_share_chg_pp,
       (e.cng_share    - LAG(e.cng_share)    OVER w) * 100  AS cng_share_chg_pp,
       (e.petrol_share - LAG(e.petrol_share) OVER w) * 100  AS petrol_share_chg_pp,
       (e.diesel_share - LAG(e.diesel_share) OVER w) * 100  AS diesel_share_chg_pp,
       (e.hybrid_share - LAG(e.hybrid_share) OVER w) * 100  AS hybrid_share_chg_pp,
       e.total_regs::DOUBLE / NULLIF(pop_annual.population_mn * 1000, 0)
                                                               AS regs_per_1000_population,
       e.total_regs::DOUBLE / NULLIF(pop_2024.population_mn * 1000, 0)
                                                               AS regs_per_1000_population_2024,
       e.total_regs::DOUBLE / NULLIF(pop_annual.population_mn * 1000, 0)
                                                               AS regs_per_1000_capita,
       pop_annual.population_mn,
       pop_annual.urban_population_mn,
       pop_annual.rural_population_mn,
       pop_annual.method                                       AS population_method,
       pop_annual.source                                       AS population_source,
       pop_annual.quality                                      AS population_quality,
       inc_real.pc_nsdp_constant_2011_12_inr                   AS pc_income_constant_2011_12_inr,
       inc_real.fy                                             AS income_constant_fy,
       inc_real.source                                         AS income_constant_source,
       inc_real.quality                                        AS income_constant_quality,
       gsdp.gsdp_constant_2011_12_lakh,
       gsdp.gsdp_real_growth_pct,
       gsdp.source                                              AS gsdp_source,
       gsdp.quality                                             AS gsdp_quality,
       credit.personal_loans_outstanding_crore,
       credit.personal_loans_per_capita_inr,
       credit.personal_loans_yoy_growth_pct,
       credit.source                                            AS credit_depth_source,
       credit.quality                                           AS credit_depth_quality,
       pop_annual.urban_pct_basis                              AS urban_pct,
       pop_annual.urban_share_year                             AS urbanization_census_year,
       pop_annual.source                                       AS urbanization_source,
       pop_annual.quality                                      AS urbanization_quality,
       cng.stations                                            AS cng_stations,
       cng.source                                              AS cng_stations_source,
       cng.quality                                             AS cng_stations_quality,
       cng.snapshot_date                                       AS cng_snapshot_date,
       cng.coverage_scope                                      AS cng_coverage_scope,
       cng.state_allocation_coverage_pct                       AS cng_state_allocation_coverage_pct,
       ev.public_chargers                                      AS ev_chargers,
       ev.source                                               AS ev_chargers_source,
       ev.quality                                              AS ev_chargers_quality,
       ev.snapshot_date                                        AS ev_snapshot_date,
       ev.coverage_scope                                       AS ev_coverage_scope,
       ev.state_allocation_coverage_pct                        AS ev_state_allocation_coverage_pct,
       COALESCE(fp_p_state.price_avg_inr, fp_p_all.price_avg_inr)
                                                               AS petrol_price_inr,
       COALESCE(fp_p_state.source, fp_p_all.source)             AS petrol_price_source,
       COALESCE(fp_p_state.quality, fp_p_all.quality)           AS petrol_price_quality,
       CASE WHEN fp_p_state.state_code IS NOT NULL THEN 'state'
            WHEN fp_p_all.state_code IS NOT NULL THEN 'ALL/Delhi fallback'
       END                                                     AS petrol_price_basis,
       COALESCE(fp_d_state.price_avg_inr, fp_d_all.price_avg_inr)
                                                               AS diesel_price_inr,
       COALESCE(fp_d_state.source, fp_d_all.source)             AS diesel_price_source,
       COALESCE(fp_d_state.quality, fp_d_all.quality)           AS diesel_price_quality,
       CASE WHEN fp_d_state.state_code IS NOT NULL THEN 'state'
            WHEN fp_d_all.state_code IS NOT NULL THEN 'ALL/Delhi fallback'
       END                                                     AS diesel_price_basis,
       COALESCE(fp_c_state.price_avg_inr, fp_c_all.price_avg_inr)
                                                               AS cng_price_inr,
       COALESCE(fp_c_state.source, fp_c_all.source)             AS cng_price_source,
       COALESCE(fp_c_state.quality, fp_c_all.quality)           AS cng_price_quality,
       CASE WHEN fp_c_state.state_code IS NOT NULL THEN 'state'
            WHEN fp_c_all.state_code IS NOT NULL THEN 'ALL/Delhi fallback'
       END                                                     AS cng_price_basis
FROM enriched e
LEFT JOIN ref_state_population_annual pop_annual
       ON pop_annual.state_code = e.state_code AND pop_annual.year = e.year
LEFT JOIN ref_state_population_annual pop_2024
       ON pop_2024.state_code = e.state_code AND pop_2024.year = 2024
LEFT JOIN ref_state_income_constant inc_real
       ON inc_real.state_code = e.state_code AND inc_real.fy = e.fy_starting
LEFT JOIN ref_state_gsdp gsdp
       ON gsdp.state_code = e.state_code AND gsdp.fy = e.fy_starting
LEFT JOIN ref_state_credit_depth credit
       ON credit.state_code = e.state_code AND credit.year = e.year
LEFT JOIN ref_cng_stations cng
       ON cng.state_code = e.state_code AND cng.year = e.year
LEFT JOIN ref_ev_charging ev
       ON ev.state_code = e.state_code AND ev.year = e.year
LEFT JOIN ref_fuel_prices fp_p_state
       ON fp_p_state.fuel = 'Petrol'
      AND fp_p_state.year = e.year
      AND fp_p_state.state_code = e.state_code
LEFT JOIN ref_fuel_prices fp_p_all
       ON fp_p_all.fuel = 'Petrol'
      AND fp_p_all.year = e.year
      AND fp_p_all.state_code = 'ALL'
LEFT JOIN ref_fuel_prices fp_d_state
       ON fp_d_state.fuel = 'Diesel'
      AND fp_d_state.year = e.year
      AND fp_d_state.state_code = e.state_code
LEFT JOIN ref_fuel_prices fp_d_all
       ON fp_d_all.fuel = 'Diesel'
      AND fp_d_all.year = e.year
      AND fp_d_all.state_code = 'ALL'
LEFT JOIN ref_fuel_prices fp_c_state
       ON fp_c_state.fuel = 'CNG'
      AND fp_c_state.year = e.year
      AND fp_c_state.state_code = e.state_code
LEFT JOIN ref_fuel_prices fp_c_all
       ON fp_c_all.fuel = 'CNG'
      AND fp_c_all.year = e.year
      AND fp_c_all.state_code = 'ALL'
WINDOW w AS (PARTITION BY e.state_code ORDER BY e.year)
ORDER BY e.state_code, e.year
"""

_SQL_EXPERIMENT_VIEWS = """
CREATE OR REPLACE VIEW experiment_state_year AS
SELECT state_code,
       state_name,
       year,
       total_regs,
       ev_regs,
       cng_regs,
       petrol_regs,
       diesel_regs,
       hybrid_regs,
       ev_share,
       cng_share,
       petrol_share,
       diesel_share,
       hybrid_share,
       yoy_growth,
       hhi_oem,
       entropy_oem,
       n_oems,
       regs_per_1000_population,
       population_mn,
       urban_population_mn,
       rural_population_mn,
       urban_pct,
       pc_income_constant_2011_12_inr AS real_pc_income_inr,
       gsdp_constant_2011_12_lakh AS real_gsdp_lakh,
       gsdp_real_growth_pct AS real_gsdp_growth_pct,
       personal_loans_per_capita_inr AS broad_credit_per_capita_inr,
       personal_loans_yoy_growth_pct AS broad_credit_growth_pct,
       petrol_price_inr,
       diesel_price_inr,
       cng_price_inr
FROM panel_state_year
WHERE state_code <> 'ALL';

CREATE OR REPLACE VIEW experiment_state_context AS
WITH latest AS (
    SELECT state_code,
           MAX_BY(pc_income_constant_2011_12_inr, year)
               FILTER (WHERE pc_income_constant_2011_12_inr IS NOT NULL)
               AS real_pc_income_inr,
           MAX_BY(gsdp_constant_2011_12_lakh, year)
               FILTER (WHERE gsdp_constant_2011_12_lakh IS NOT NULL)
               AS real_gsdp_lakh,
           MAX_BY(gsdp_real_growth_pct, year)
               FILTER (WHERE gsdp_real_growth_pct IS NOT NULL)
               AS latest_real_gsdp_growth_pct,
           MAX_BY(personal_loans_per_capita_inr, year)
               FILTER (WHERE personal_loans_per_capita_inr IS NOT NULL)
               AS broad_credit_per_capita_inr,
           MAX_BY(population_mn, year) FILTER (WHERE year = 2025)
               AS population_2025_mn,
           MAX(urban_pct) AS urban_pct
    FROM panel_state_year
    WHERE state_code <> 'ALL'
    GROUP BY state_code
),
tax AS (
    SELECT state_code,
           MAX(lifetime_tax_rate_pct) FILTER (WHERE fuel = 'EV') AS ev_tax_rate_pct,
           MAX(lifetime_tax_rate_pct) FILTER (WHERE fuel = 'Strong Hybrid')
               AS hybrid_tax_rate_pct,
           MAX(lifetime_tax_rate_pct) FILTER (WHERE fuel = 'Petrol') AS ice_tax_rate_pct,
           MAX(as_of) AS tax_as_of
    FROM ref_vehicle_lifetime_tax
    GROUP BY state_code
)
SELECT d.state_code,
       d.state_name,
       d.zone,
       l.real_pc_income_inr,
       l.real_gsdp_lakh,
       l.latest_real_gsdp_growth_pct,
       l.broad_credit_per_capita_inr,
       l.population_2025_mn,
       l.urban_pct,
       cng.stations AS cng_stations_2024,
       cng.snapshot_date AS cng_snapshot_date,
       cng.quality AS cng_quality,
       ev.public_chargers AS ev_chargers_2025,
       ev.snapshot_date AS ev_snapshot_date,
       ev.quality AS ev_quality,
       ev.state_allocation_coverage_pct AS ev_allocation_coverage_pct,
       tax.ev_tax_rate_pct,
       tax.hybrid_tax_rate_pct,
       tax.ice_tax_rate_pct,
       tax.tax_as_of
FROM dim_state d
LEFT JOIN latest l USING (state_code)
LEFT JOIN ref_cng_stations cng
       ON cng.state_code = d.state_code AND cng.year = 2024
LEFT JOIN ref_ev_charging ev
       ON ev.state_code = d.state_code AND ev.year = 2025
LEFT JOIN tax USING (state_code)
WHERE d.state_code <> 'ALL';
"""

_SQL_EDGES = """
CREATE OR REPLACE VIEW oem_state_edges AS
SELECT state_code, state_name, maker, year, fy, SUM("count") AS regs
FROM registrations
WHERE state_code <> 'ALL'
GROUP BY state_code, state_name, maker, year, fy
"""

_SQL_MAKER_SHARE = """
CREATE OR REPLACE TABLE maker_state_share AS
WITH base AS (
    SELECT state_code, state_name, maker, year, SUM("count") AS regs
    FROM registrations
    GROUP BY state_code, state_name, maker, year
),
shares AS (
    SELECT *,
           regs::DOUBLE / NULLIF(SUM(regs) OVER (PARTITION BY state_code, year), 0) AS share,
           RANK() OVER (PARTITION BY state_code, year ORDER BY regs DESC)           AS rnk
    FROM base
)
SELECT s.*,
       (s.share - LAG(s.share) OVER w) * 100        AS share_chg_pp,
       LAG(s.rnk) OVER w - s.rnk                    AS rank_chg
FROM shares s
WINDOW w AS (PARTITION BY s.state_code, s.maker ORDER BY s.year)
ORDER BY s.state_code, s.year, s.rnk
"""


def build_panels(db_path: Path | None = None) -> dict[str, int]:
    """(Re)build panel tables. Returns row counts."""
    con = connect(db_path)
    try:
        con.execute(_SQL_PANEL_MONTH)
        con.execute(_SQL_PANEL_YEAR)
        con.execute(_SQL_EDGES)
        con.execute(_SQL_MAKER_SHARE)
        con.execute(_SQL_EXPERIMENT_VIEWS)
        return {
            "panel_state_month": con.execute("SELECT COUNT(*) FROM panel_state_month").fetchone()[0],
            "panel_state_year": con.execute("SELECT COUNT(*) FROM panel_state_year").fetchone()[0],
            "maker_state_share": con.execute("SELECT COUNT(*) FROM maker_state_share").fetchone()[0],
            "experiment_state_year": con.execute(
                "SELECT COUNT(*) FROM experiment_state_year"
            ).fetchone()[0],
            "experiment_state_context": con.execute(
                "SELECT COUNT(*) FROM experiment_state_context"
            ).fetchone()[0],
        }
    finally:
        con.close()

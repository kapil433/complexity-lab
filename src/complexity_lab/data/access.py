"""Cutoff-aware, parameterized accessors for the interactive app."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from complexity_lab.app_state import GlobalContext

FUEL_COLUMNS = {
    "EV": "ev_regs",
    "CNG": "cng_regs",
    "Petrol": "petrol_regs",
    "Diesel": "diesel_regs",
    "Strong Hybrid": "hybrid_regs",
}


@dataclass(frozen=True)
class DataCutoff:
    source: str
    first_period: str
    latest_period: str
    latest_complete_year: int
    latest_observed_year: int
    latest_observed_month: int
    observed_months_latest_year: int
    status: str
    warning: str


def table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table],
        ).fetchone()[0]
    )


def vahan_period_status(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if table_exists(con, "data_period_status"):
        return con.execute(
            """
            SELECT *
            FROM data_period_status
            WHERE source = 'vahan'
            ORDER BY period
            """
        ).df()
    return con.execute(
        """
        SELECT 'vahan' AS source,
               'calendar_year' AS grain,
               CAST(year AS VARCHAR) AS period,
               COUNT(DISTINCT month)::INTEGER AS observed_month_count,
               12 AS expected_month_count,
               CASE WHEN COUNT(DISTINCT month) = 12 THEN 'complete' ELSE 'partial' END
                   AS completeness_status,
               MAX(date) AS freshness_date,
               'national registration coverage' AS coverage_regime,
               CASE WHEN COUNT(DISTINCT month) = 12 THEN ''
                    ELSE 'Partial calendar year; do not compare with full years.'
               END AS warning_text
        FROM panel_state_month
        WHERE state_code = 'ALL'
        GROUP BY year
        ORDER BY year
        """
    ).df()


def vahan_cutoff(con: duckdb.DuckDBPyConnection) -> DataCutoff:
    status = vahan_period_status(con)
    complete = status[status["completeness_status"] == "complete"]
    latest = status.iloc[-1]
    first_date, latest_date = con.execute(
        """
        SELECT MIN(date), MAX(date)
        FROM panel_state_month
        WHERE state_code = 'ALL'
        """
    ).fetchone()
    return DataCutoff(
        source="Vahan registrations",
        first_period=first_date.strftime("%B %Y"),
        latest_period=latest_date.strftime("%B %Y"),
        latest_complete_year=int(complete["period"].astype(int).max()),
        latest_observed_year=int(latest_date.year),
        latest_observed_month=int(latest_date.month),
        observed_months_latest_year=int(latest["observed_month_count"]),
        status=str(latest["completeness_status"]),
        warning=str(latest["warning_text"]),
    )


def state_dimension(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        """
        SELECT state_code, state_name, zone
        FROM dim_state
        WHERE state_code <> 'ALL'
        ORDER BY state_name
        """
    ).df()


def maker_options(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            """
            SELECT DISTINCT maker
            FROM registrations
            WHERE maker IS NOT NULL
            ORDER BY maker
            """
        ).fetchall()
    ]


def market_monthly(
    con: duckdb.DuckDBPyConnection,
    context: GlobalContext,
) -> pd.DataFrame:
    states = list(context.states) or ["ALL"]
    state_placeholders = ", ".join("?" for _ in states)
    fuels = [fuel for fuel in context.fuels if fuel in FUEL_COLUMNS]
    fuel_columns = [FUEL_COLUMNS[fuel] for fuel in fuels] or list(FUEL_COLUMNS.values())

    if context.oems:
        oem_placeholders = ", ".join("?" for _ in context.oems)
        fuel_filter = ""
        params: list[object] = [*states, *context.oems]
        if fuels:
            fuel_placeholders = ", ".join("?" for _ in fuels)
            fuel_filter = f" AND fuel IN ({fuel_placeholders})"
            params.extend(fuels)
        params.extend([context.year_start, context.year_end])
        select_fuels = ",\n".join(
            f"""SUM(CASE WHEN fuel = '{fuel}' THEN "count" ELSE 0 END)
                AS {FUEL_COLUMNS[fuel]}"""
            for fuel in (fuels or list(FUEL_COLUMNS))
        )
        return con.execute(
            f"""
            SELECT MAKE_DATE(year, month, 1) AS date, year, month,
                   SUM("count") AS total_regs,
                   {select_fuels}
            FROM registrations
            WHERE state_code IN ({state_placeholders})
              AND maker IN ({oem_placeholders})
              {fuel_filter}
              AND year BETWEEN ? AND ?
            GROUP BY date, year, month
            ORDER BY date
            """,
            params,
        ).df()

    total_expression = (
        " + ".join(f"SUM({column})" for column in fuel_columns)
        if fuels
        else "SUM(total_regs)"
    )
    select_fuels = ",\n".join(f"SUM({column}) AS {column}" for column in fuel_columns)
    return con.execute(
        f"""
        SELECT date, year, month,
               {total_expression} AS total_regs,
               {select_fuels}
        FROM panel_state_month
        WHERE state_code IN ({state_placeholders})
          AND year BETWEEN ? AND ?
        GROUP BY date, year, month
        ORDER BY date
        """,
        [*states, context.year_start, context.year_end],
    ).df()


def market_annual(
    con: duckdb.DuckDBPyConnection,
    context: GlobalContext,
    through_month: int | None = None,
) -> pd.DataFrame:
    monthly = market_monthly(con, context)
    if through_month is not None:
        monthly = monthly[monthly["month"] <= through_month]
    value_columns = [
        column
        for column in ["total_regs", *FUEL_COLUMNS.values()]
        if column in monthly.columns
    ]
    annual = monthly.groupby("year", as_index=False)[value_columns].sum()
    for fuel, column in FUEL_COLUMNS.items():
        if column in annual:
            annual[f"{fuel.lower().replace(' ', '_')}_share"] = (
                annual[column] / annual["total_regs"]
            )
    annual["yoy_growth"] = annual["total_regs"].pct_change()
    return annual


def matched_ytd_state_year(
    con: duckdb.DuckDBPyConnection,
    through_month: int,
) -> pd.DataFrame:
    """State-year panel using the same January-through-month window in every year."""
    base = con.execute(
        """
        WITH totals AS (
            SELECT state_code, MAX(state_name) AS state_name, year,
                   SUM("count") AS total_regs,
                   SUM("count") FILTER (WHERE fuel = 'EV') AS ev_regs,
                   SUM("count") FILTER (WHERE fuel = 'CNG') AS cng_regs,
                   SUM("count") FILTER (WHERE fuel = 'Petrol') AS petrol_regs,
                   SUM("count") FILTER (WHERE fuel = 'Diesel') AS diesel_regs,
                   SUM("count") FILTER (WHERE fuel = 'Strong Hybrid') AS hybrid_regs
            FROM registrations
            WHERE month <= ?
            GROUP BY state_code, year
        ),
        maker AS (
            SELECT state_code, year, maker, SUM("count") AS regs
            FROM registrations
            WHERE month <= ?
            GROUP BY state_code, year, maker
        ),
        maker_share AS (
            SELECT *,
                   regs::DOUBLE / NULLIF(SUM(regs) OVER (PARTITION BY state_code, year), 0)
                       AS share
            FROM maker
        ),
        concentration AS (
            SELECT state_code, year,
                   SUM(share * share) * 10000 AS hhi_oem,
                   -SUM(CASE WHEN share > 0 THEN share * LN(share) ELSE 0 END) AS entropy_oem,
                   COUNT(*) FILTER (WHERE share > 0) AS n_oems
            FROM maker_share
            GROUP BY state_code, year
        )
        SELECT t.*, c.hhi_oem, c.entropy_oem, c.n_oems
        FROM totals t
        LEFT JOIN concentration c USING (state_code, year)
        ORDER BY state_code, year
        """,
        [through_month, through_month],
    ).df()
    fuel_columns = ["ev", "cng", "petrol", "diesel", "hybrid"]
    for fuel in fuel_columns:
        base[f"{fuel}_regs"] = base[f"{fuel}_regs"].fillna(0)
        base[f"{fuel}_share"] = base[f"{fuel}_regs"] / base["total_regs"]
    grouped = base.groupby("state_code", sort=False)
    base["yoy_growth"] = grouped["total_regs"].pct_change()
    for fuel in fuel_columns:
        base[f"{fuel}_share_chg_pp"] = grouped[f"{fuel}_share"].diff() * 100

    context = con.execute("SELECT * FROM panel_state_year").df()
    observed = {
        "state_name",
        "total_regs",
        "ev_regs",
        "cng_regs",
        "petrol_regs",
        "diesel_regs",
        "hybrid_regs",
        "ev_share",
        "cng_share",
        "petrol_share",
        "diesel_share",
        "hybrid_share",
        "yoy_growth",
        "ev_share_chg_pp",
        "cng_share_chg_pp",
        "petrol_share_chg_pp",
        "diesel_share_chg_pp",
        "hybrid_share_chg_pp",
        "hhi_oem",
        "entropy_oem",
        "n_oems",
        "regs_per_1000_population",
        "regs_per_1000_population_2024",
        "regs_per_1000_capita",
    }
    context_columns = [
        column
        for column in context.columns
        if column in {"state_code", "year"} or column not in observed
    ]
    result = base.merge(context[context_columns], on=["state_code", "year"], how="left")
    if "population_mn" in result:
        result["regs_per_1000_population"] = (
            result["total_regs"] / (result["population_mn"] * 1000)
        )
        result["regs_per_1000_capita"] = result["regs_per_1000_population"]
    aliases = {
        "pc_income_constant_2011_12_inr": "real_pc_income_inr",
        "gsdp_constant_2011_12_lakh": "real_gsdp_lakh",
        "gsdp_real_growth_pct": "real_gsdp_growth_pct",
        "personal_loans_per_capita_inr": "broad_credit_per_capita_inr",
        "personal_loans_yoy_growth_pct": "broad_credit_growth_pct",
    }
    for source, target in aliases.items():
        if source in result:
            result[target] = result[source]
    result["matched_through_month"] = through_month
    return result


def matched_ytd_maker_state(
    con: duckdb.DuckDBPyConnection,
    through_month: int,
) -> pd.DataFrame:
    """Maker-state shares and ranks on matched January-through-month windows."""
    result = con.execute(
        """
        WITH base AS (
            SELECT state_code, MAX(state_name) AS state_name, maker, year,
                   SUM("count") AS regs
            FROM registrations
            WHERE month <= ?
            GROUP BY state_code, maker, year
        ),
        shares AS (
            SELECT *,
                   regs::DOUBLE / NULLIF(SUM(regs) OVER (PARTITION BY state_code, year), 0)
                       AS share,
                   RANK() OVER (PARTITION BY state_code, year ORDER BY regs DESC) AS rnk
            FROM base
        )
        SELECT *
        FROM shares
        ORDER BY state_code, year, rnk
        """,
        [through_month],
    ).df()
    grouped = result.groupby(["state_code", "maker"], sort=False)
    result["share_chg_pp"] = grouped["share"].diff() * 100
    result["rank_chg"] = grouped["rnk"].shift() - result["rnk"]
    result["matched_through_month"] = through_month
    return result


def state_snapshot(
    con: duckdb.DuckDBPyConnection,
    year: int,
    states: tuple[str, ...] = (),
    through_month: int | None = None,
) -> pd.DataFrame:
    if through_month is not None:
        snapshot = matched_ytd_state_year(con, through_month)
        snapshot = snapshot[
            (snapshot["year"] == year) & (snapshot["state_code"] != "ALL")
        ]
        if states:
            snapshot = snapshot[snapshot["state_code"].isin(states)]
        dimension = con.execute(
            "SELECT state_code, zone, geojson_name FROM dim_state"
        ).df()
        return (
            snapshot.merge(dimension, on="state_code", how="left")
            .sort_values("total_regs", ascending=False)
            .reset_index(drop=True)
        )

    params: list[object] = [year]
    state_filter = ""
    if states:
        placeholders = ", ".join("?" for _ in states)
        state_filter = f" AND p.state_code IN ({placeholders})"
        params.extend(states)
    return con.execute(
        f"""
        SELECT p.state_code, p.state_name, p.total_regs, p.yoy_growth,
               p.ev_share, p.ev_share_chg_pp, p.cng_share, p.cng_share_chg_pp,
               d.zone, d.geojson_name
        FROM panel_state_year p
        JOIN dim_state d USING (state_code)
        WHERE p.year = ? AND p.state_code <> 'ALL' {state_filter}
        ORDER BY p.total_regs DESC
        """,
        params,
    ).df()

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
) -> pd.DataFrame:
    monthly = market_monthly(con, context)
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


def state_snapshot(
    con: duckdb.DuckDBPyConnection,
    year: int,
    states: tuple[str, ...] = (),
) -> pd.DataFrame:
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

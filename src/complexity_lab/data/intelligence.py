"""Reusable state, OEM, movement, and health queries for intelligence pages."""

from __future__ import annotations

import duckdb
import pandas as pd


def state_profile(
    con: duckdb.DuckDBPyConnection,
    state_code: str,
    through_year: int,
) -> dict[str, pd.DataFrame]:
    annual = con.execute(
        """
        SELECT *
        FROM panel_state_year
        WHERE state_code = ? AND year <= ?
        ORDER BY year
        """,
        [state_code, through_year],
    ).df()
    monthly = con.execute(
        """
        SELECT *
        FROM panel_state_month
        WHERE state_code = ? AND year <= ?
        ORDER BY date
        """,
        [state_code, through_year],
    ).df()
    oems = con.execute(
        """
        SELECT year, maker, regs, share, share_chg_pp, rnk
        FROM maker_state_share
        WHERE state_code = ? AND year <= ?
        ORDER BY year, rnk
        """,
        [state_code, through_year],
    ).df()
    context = con.execute(
        "SELECT * FROM experiment_state_context WHERE state_code = ?",
        [state_code],
    ).df()
    peers = con.execute(
        """
        WITH target AS (
            SELECT zone, real_pc_income_inr, urban_pct
            FROM experiment_state_context
            WHERE state_code = ?
        )
        SELECT c.*,
               ABS(LN(NULLIF(c.real_pc_income_inr, 0) / NULLIF(t.real_pc_income_inr, 0)))
                 + ABS(COALESCE(c.urban_pct, 0) - COALESCE(t.urban_pct, 0)) / 100
                 + CASE WHEN c.zone = t.zone THEN 0 ELSE 0.25 END AS peer_distance
        FROM experiment_state_context c
        CROSS JOIN target t
        WHERE c.state_code <> ?
        ORDER BY peer_distance
        LIMIT 6
        """,
        [state_code, state_code],
    ).df()
    events = con.execute(
        """
        SELECT *
        FROM ref_policy_events_canonical
        WHERE state_code IN (?, 'ALL')
        ORDER BY date
        """,
        [state_code],
    ).df()
    return {
        "annual": annual,
        "monthly": monthly,
        "oems": oems,
        "context": context,
        "peers": peers,
        "events": events,
    }


def oem_profile(
    con: duckdb.DuckDBPyConnection,
    maker: str,
    through_year: int,
) -> dict[str, pd.DataFrame]:
    annual = con.execute(
        """
        WITH maker_year AS (
            SELECT year, SUM("count") AS regs
            FROM registrations
            WHERE state_code = 'ALL' AND maker = ? AND year <= ?
            GROUP BY year
        ),
        market AS (
            SELECT year, SUM("count") AS market_regs
            FROM registrations
            WHERE state_code = 'ALL' AND year <= ?
            GROUP BY year
        )
        SELECT m.year, m.regs, m.regs::DOUBLE / NULLIF(t.market_regs, 0) AS share
        FROM maker_year m
        JOIN market t USING (year)
        ORDER BY m.year
        """,
        [maker, through_year, through_year],
    ).df()
    fuels = con.execute(
        """
        SELECT year, fuel, SUM("count") AS regs
        FROM registrations
        WHERE state_code = 'ALL' AND maker = ? AND year <= ?
        GROUP BY year, fuel
        ORDER BY year, fuel
        """,
        [maker, through_year],
    ).df()
    states = con.execute(
        """
        SELECT state_code, state_name, year, regs, share, rnk
        FROM maker_state_share
        WHERE maker = ? AND state_code <> 'ALL' AND year <= ?
        ORDER BY year, share DESC
        """,
        [maker, through_year],
    ).df()
    return {"annual": annual, "fuels": fuels, "states": states}


def largest_moves(
    con: duckdb.DuckDBPyConnection,
    year: int,
    limit: int = 8,
) -> dict[str, pd.DataFrame]:
    states = con.execute(
        """
        SELECT state_code, state_name, total_regs, yoy_growth,
               ev_share_chg_pp, cng_share_chg_pp
        FROM panel_state_year
        WHERE state_code <> 'ALL' AND year = ?
        ORDER BY ABS(yoy_growth) DESC
        LIMIT ?
        """,
        [year, limit],
    ).df()
    oems = con.execute(
        """
        SELECT maker, regs, share, share_chg_pp, rank_chg
        FROM maker_state_share
        WHERE state_code = 'ALL' AND year = ?
        ORDER BY ABS(share_chg_pp) DESC
        LIMIT ?
        """,
        [year, limit],
    ).df()
    return {"states": states, "oems": oems}


def data_health(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    periods = con.execute("SELECT * FROM data_period_status ORDER BY period").df()
    references = con.execute(
        """
        SELECT dataset, status, geography, time_coverage, quality_summary,
               row_count, not_available
        FROM reference_availability
        ORDER BY status, dataset
        """
    ).df()
    tables = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).df()
    return {"periods": periods, "references": references, "tables": tables}

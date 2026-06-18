"""Reusable state, OEM, movement, and health queries for intelligence pages."""

from __future__ import annotations

import duckdb
import pandas as pd

from complexity_lab.data.access import matched_ytd_maker_state, matched_ytd_state_year


def state_profile(
    con: duckdb.DuckDBPyConnection,
    state_code: str,
    through_year: int,
    through_month: int = 12,
) -> dict[str, pd.DataFrame]:
    annual = matched_ytd_state_year(con, through_month)
    annual = annual[
        (annual["state_code"] == state_code) & (annual["year"] <= through_year)
    ].sort_values("year")
    monthly = con.execute(
        """
        SELECT *
        FROM panel_state_month
        WHERE state_code = ?
          AND (year < ? OR (year = ? AND month <= ?))
        ORDER BY date
        """,
        [state_code, through_year, through_year, through_month],
    ).df()
    oems = matched_ytd_maker_state(con, through_month)
    oems = oems[
        (oems["state_code"] == state_code) & (oems["year"] <= through_year)
    ].sort_values(["year", "rnk"])
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
    through_month: int = 12,
) -> dict[str, pd.DataFrame]:
    maker_state = matched_ytd_maker_state(con, through_month)
    annual = maker_state[
        (maker_state["state_code"] == "ALL")
        & (maker_state["maker"] == maker)
        & (maker_state["year"] <= through_year)
    ][["year", "regs", "share", "share_chg_pp", "rnk", "rank_chg"]].sort_values("year")
    fuels = con.execute(
        """
        SELECT year, fuel, SUM("count") AS regs
        FROM registrations
        WHERE state_code = 'ALL' AND maker = ? AND year <= ? AND month <= ?
        GROUP BY year, fuel
        ORDER BY year, fuel
        """,
        [maker, through_year, through_month],
    ).df()
    states = maker_state[
        (maker_state["maker"] == maker)
        & (maker_state["state_code"] != "ALL")
        & (maker_state["year"] <= through_year)
    ].sort_values(["year", "share"], ascending=[True, False])
    return {"annual": annual, "fuels": fuels, "states": states}


def largest_moves(
    con: duckdb.DuckDBPyConnection,
    year: int,
    limit: int = 8,
    through_month: int | None = None,
) -> dict[str, pd.DataFrame]:
    if through_month is not None:
        panel = matched_ytd_state_year(con, through_month)
        states = (
            panel[(panel["state_code"] != "ALL") & (panel["year"] == year)]
            .sort_values("yoy_growth", key=lambda values: values.abs(), ascending=False)
            .head(limit)[
                [
                    "state_code",
                    "state_name",
                    "total_regs",
                    "yoy_growth",
                    "ev_share_chg_pp",
                    "cng_share_chg_pp",
                ]
            ]
        )
        makers = matched_ytd_maker_state(con, through_month)
        oems = (
            makers[(makers["state_code"] == "ALL") & (makers["year"] == year)]
            .sort_values("share_chg_pp", key=lambda values: values.abs(), ascending=False)
            .head(limit)[["maker", "regs", "share", "share_chg_pp", "rank_chg"]]
        )
        return {"states": states, "oems": oems}

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

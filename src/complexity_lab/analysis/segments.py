"""Segment-transition analysis on wholesale data (blueprint SEG-K01).

Wholesale natively carries a 5-level segment taxonomy (``segment5``), so the
hatchback→SUV structural shift is directly measurable — at state grain in the
full-coverage era (2022-04+) and, crucially, over a 9-year window on the
*panel cities*: the ~50 cities present since 2017, which form an internally
consistent longitudinal sample across the coverage break.
"""

from __future__ import annotations

import duckdb
import pandas as pd

SUV_SEGMENTS = ("Entry Suv", "Mid Suv", "Premium Suv", "Suv")
HATCH_SEGMENTS = ("Entry Hatch", "Mid Hatch", "Premium Hatch")


def panel_cities(con: duckdb.DuckDBPyConnection, min_pre_months: int = 36) -> list[str]:
    """Cities reported in most of the pre-2022 sample era — the consistent panel."""
    df = con.execute(
        """SELECT city, COUNT(DISTINCT date) AS months
           FROM wholesale WHERE coverage = 'sample'
           GROUP BY city HAVING months >= ?""",
        [min_pre_months],
    ).df()
    return sorted(df["city"])


def suv_share_series(
    con: duckdb.DuckDBPyConnection,
    grain: str = "state",
    cities: list[str] | None = None,
) -> pd.DataFrame:
    """Monthly SUV share of wholesale.

    grain='state' (full-coverage era) or 'city' (restricted to ``cities``,
    spanning the whole 2017+ window).
    """
    suv_list = ", ".join(f"'{s}'" for s in SUV_SEGMENTS)
    if grain == "state":
        return con.execute(
            f"""SELECT state_code AS entity, date, year, month,
                       SUM(qty) FILTER (WHERE segment5 IN ({suv_list}))::DOUBLE
                           / NULLIF(SUM(qty), 0) AS suv_share
                FROM wholesale
                WHERE coverage = 'full' AND state_code IS NOT NULL
                GROUP BY state_code, date, year, month ORDER BY entity, date"""
        ).df()
    if not cities:
        raise ValueError("city grain requires a cities list (see panel_cities)")
    city_list = ", ".join(f"'{c}'" for c in cities)
    return con.execute(
        f"""SELECT city AS entity, date, year, month,
                   SUM(qty) FILTER (WHERE segment5 IN ({suv_list}))::DOUBLE
                       / NULLIF(SUM(qty), 0) AS suv_share
            FROM wholesale
            WHERE city IN ({city_list})
            GROUP BY city, date, year, month ORDER BY entity, date"""
    ).df()


def segment_mix(con: duckdb.DuckDBPyConnection, by: str = "year") -> pd.DataFrame:
    """National segment shares (full-coverage era)."""
    return con.execute(
        f"""SELECT {by}, segment5, SUM(qty) AS units,
                   SUM(qty)::DOUBLE / SUM(SUM(qty)) OVER (PARTITION BY {by}) AS share
            FROM wholesale WHERE coverage = 'full'
            GROUP BY {by}, segment5 ORDER BY {by}, units DESC"""
    ).df()


def oem_suv_trajectories(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """SUV share within each OEM's own portfolio by year (full era)."""
    suv_list = ", ".join(f"'{s}'" for s in SUV_SEGMENTS)
    return con.execute(
        f"""SELECT maker, year,
                   SUM(qty) FILTER (WHERE segment5 IN ({suv_list}))::DOUBLE
                       / NULLIF(SUM(qty), 0) AS suv_share,
                   SUM(qty) AS units
            FROM wholesale WHERE coverage = 'full'
            GROUP BY maker, year HAVING SUM(qty) > 20000 ORDER BY maker, year"""
    ).df()


def classify_movers(oem_traj: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Early mover / fast follower / late adapter / segment-locked, by the year an
    OEM's own portfolio crossed ``threshold`` SUV share."""
    rows = []
    for maker, grp in oem_traj.sort_values("year").groupby("maker"):
        crossed = grp[grp["suv_share"] >= threshold]
        first = int(crossed["year"].min()) if not crossed.empty else None
        latest = grp.iloc[-1]
        rows.append(
            {
                "maker": maker,
                "crossed_year": first,
                "latest_suv_share": float(latest["suv_share"]),
                "latest_units": int(latest["units"]),
            }
        )
    df = pd.DataFrame(rows).set_index("maker")
    years = df["crossed_year"].dropna()
    med = years.median() if not years.empty else None
    def _label(r):
        if r["crossed_year"] is None or pd.isna(r["crossed_year"]):
            return "segment-locked" if r["latest_suv_share"] < 0.35 else "approaching"
        return "early mover" if r["crossed_year"] <= med else "fast follower"
    df["class"] = df.apply(_label, axis=1)
    return df.sort_values(["class", "latest_suv_share"], ascending=[True, False])


def state_archetypes(
    con: duckdb.DuckDBPyConnection, year: int, k: int = 4, seed: int = 42
) -> pd.DataFrame:
    """k-means on states' segment-share vectors → archetypes (Entry / Transitioning /
    Aspiration / Premium in the blueprint's typology)."""
    from scipy.cluster.vq import kmeans2

    mix = con.execute(
        """SELECT state_code, segment5, SUM(qty)::DOUBLE AS units
           FROM wholesale WHERE coverage = 'full' AND year = ? AND state_code IS NOT NULL
           GROUP BY state_code, segment5""",
        [year],
    ).df()
    pivot = mix.pivot_table(index="state_code", columns="segment5", values="units", fill_value=0.0)
    shares = pivot.div(pivot.sum(axis=1), axis=0)
    shares = shares[shares.sum(axis=1) > 0]
    _, labels = kmeans2(shares.to_numpy(), k, minit="++", seed=seed)
    out = shares.copy()
    out["cluster"] = labels
    suv_cols = [c for c in shares.columns if c in SUV_SEGMENTS]
    order = out.groupby("cluster")[suv_cols].sum().sum(axis=1).sort_values().index
    rank = {c: i for i, c in enumerate(order)}
    names = ["Entry market", "Transitioning", "Aspiration majority", "Premium/SUV-first"]
    out["archetype"] = out["cluster"].map(lambda c: names[min(rank[c], len(names) - 1)])
    return out.drop(columns="cluster")

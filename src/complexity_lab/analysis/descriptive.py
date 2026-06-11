"""Descriptive statistics on the panels: growth, shares, seasonality, concentration.

All functions are dataframe-in / dataframe-out so they are trivially testable;
pull inputs from DuckDB (``panel_state_month`` / ``panel_state_year``) upstream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def hhi(shares: pd.Series) -> float:
    """Herfindahl–Hirschman index on a series of shares summing to 1 (scale 0–10000)."""
    s = shares.dropna()
    return float((s**2).sum() * 10000)


def shannon_entropy(shares: pd.Series, normalize: bool = False) -> float:
    """Shannon entropy (nats) of a share vector; optionally normalized to [0, 1]."""
    s = shares.dropna()
    s = s[s > 0]
    if s.empty:
        return 0.0
    h = float(-(s * np.log(s)).sum())
    if normalize and len(s) > 1:
        h /= np.log(len(s))
    return h


def cagr(series: pd.Series) -> float:
    """Compound annual growth rate from first to last value of an annual series."""
    s = series.dropna()
    if len(s) < 2 or s.iloc[0] <= 0:
        return float("nan")
    years = len(s) - 1
    return float((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1)


def yoy_growth(df: pd.DataFrame, value_col: str, group_col: str | None = None) -> pd.Series:
    """Year-over-year growth; optionally within groups (e.g. per state)."""
    if group_col:
        return df.groupby(group_col)[value_col].pct_change()
    return df[value_col].pct_change()


def seasonality_profile(monthly: pd.DataFrame, value_col: str = "total_regs") -> pd.DataFrame:
    """Average month-of-year index (1.0 = average month) with dispersion.

    Expects columns ``year``, ``month``, ``value_col``. Each year is normalised
    by its own mean before averaging so trend doesn't contaminate seasonality.
    """
    d = monthly.copy()
    yearly_mean = d.groupby("year")[value_col].transform("mean")
    d["index"] = d[value_col] / yearly_mean
    out = d.groupby("month")["index"].agg(["mean", "std", "count"])
    return out.rename(columns={"mean": "seasonal_index"})


def market_shares(df: pd.DataFrame, entity_col: str, value_col: str = "regs") -> pd.DataFrame:
    """Share of each entity (maker / state / fuel) of the total."""
    g = df.groupby(entity_col)[value_col].sum().sort_values(ascending=False)
    return pd.DataFrame({"total": g, "share": g / g.sum()})


def concentration_series(
    df: pd.DataFrame, time_col: str, entity_col: str, value_col: str = "regs"
) -> pd.DataFrame:
    """HHI and entropy of entity shares for each time period."""
    rows = []
    for t, grp in df.groupby(time_col):
        shares = grp.groupby(entity_col)[value_col].sum()
        shares = shares / shares.sum()
        rows.append(
            {
                time_col: t,
                "hhi": hhi(shares),
                "entropy": shannon_entropy(shares),
                "entropy_norm": shannon_entropy(shares, normalize=True),
                "n_entities": int((shares > 0).sum()),
            }
        )
    return pd.DataFrame(rows).set_index(time_col)


def summary_table(panel_year: pd.DataFrame) -> pd.DataFrame:
    """One-row-per-state summary: size, growth, EV/CNG share, concentration."""
    latest_full_year = int(panel_year.loc[panel_year["total_regs"].notna(), "year"].max()) - 1
    rows = []
    for code, grp in panel_year.groupby("state_code"):
        grp = grp.sort_values("year")
        full = grp[grp["year"] <= latest_full_year]
        if full.empty:
            continue
        last = full.iloc[-1]
        rows.append(
            {
                "state_code": code,
                "state_name": last["state_name"],
                "latest_year": int(last["year"]),
                "total_regs": last["total_regs"],
                "cagr_5y": cagr(full.set_index("year")["total_regs"].tail(6)),
                "ev_share": last["ev_share"],
                "cng_share": last["cng_share"],
                "hhi_oem": last["hhi_oem"],
            }
        )
    return pd.DataFrame(rows).set_index("state_code").sort_values("total_regs", ascending=False)

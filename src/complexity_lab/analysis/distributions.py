"""Distributional analysis: heavy tails, rank–size structure, inequality."""

from __future__ import annotations

import numpy as np
import pandas as pd


def gini(values: pd.Series | np.ndarray) -> float:
    """Gini coefficient of a non-negative array."""
    x = np.sort(np.asarray(values, dtype=float))
    x = x[~np.isnan(x)]
    if x.size == 0 or x.sum() == 0:
        return float("nan")
    n = x.size
    cum = np.cumsum(x)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def rank_size(values: pd.Series) -> pd.DataFrame:
    """Rank–size table with log columns, for Zipf-style plots and fits."""
    v = values.dropna().sort_values(ascending=False).reset_index(drop=True)
    df = pd.DataFrame({"rank": np.arange(1, len(v) + 1), "size": v.values})
    df = df[df["size"] > 0]
    df["log_rank"] = np.log(df["rank"])
    df["log_size"] = np.log(df["size"])
    return df


def zipf_exponent(values: pd.Series) -> dict:
    """OLS slope of log(size) ~ log(rank). Slope ≈ -1 suggests Zipf's law."""
    df = rank_size(values)
    if len(df) < 3:
        return {"slope": float("nan"), "r2": float("nan"), "n": len(df)}
    slope, intercept = np.polyfit(df["log_rank"], df["log_size"], 1)
    pred = slope * df["log_rank"] + intercept
    ss_res = ((df["log_size"] - pred) ** 2).sum()
    ss_tot = ((df["log_size"] - df["log_size"].mean()) ** 2).sum()
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "n": len(df),
    }


def powerlaw_fit(values: pd.Series, xmin: float | None = None) -> dict:
    """Clauset-style power-law fit via the `powerlaw` package, with a
    lognormal likelihood-ratio comparison. Returns NaNs if too few points."""
    import powerlaw  # heavy import — keep local

    x = np.asarray(values.dropna(), dtype=float)
    x = x[x > 0]
    if x.size < 10:
        return {"alpha": float("nan"), "xmin": float("nan"), "n_tail": 0}
    fit = powerlaw.Fit(x, xmin=xmin, verbose=False)
    r, p = fit.distribution_compare("power_law", "lognormal", normalized_ratio=True)
    return {
        "alpha": float(fit.power_law.alpha),
        "xmin": float(fit.power_law.xmin),
        "sigma": float(fit.power_law.sigma),
        "n_tail": int((x >= fit.power_law.xmin).sum()),
        "lr_powerlaw_vs_lognormal": float(r),
        "lr_pvalue": float(p),
    }

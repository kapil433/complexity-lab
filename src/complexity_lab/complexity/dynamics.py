"""Dynamical-systems diagnostics: early-warning signals and regime structure.

Critical-slowing-down theory: approaching a regime shift, a system's
fluctuations show rising variance and lag-1 autocorrelation. We compute these
on rolling windows of detrended series (Scheffer et al., 2009).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def detrend(series: pd.Series, window: int = 12) -> pd.Series:
    """Subtract a centred rolling mean (Gaussian-ish detrending for EWS)."""
    trend = series.rolling(window, center=True, min_periods=max(2, window // 2)).mean()
    return series - trend


def early_warning_signals(series: pd.Series, window: int = 24, detrend_window: int = 12) -> pd.DataFrame:
    """Rolling variance, lag-1 autocorrelation and skewness on the detrended series."""
    resid = detrend(series.astype(float), window=detrend_window)

    def _ac1(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < 3 or np.std(x) == 0:
            return np.nan
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    roll = resid.rolling(window, min_periods=window // 2)
    out = pd.DataFrame(
        {
            "value": series,
            "residual": resid,
            "variance": roll.var(),
            "autocorr1": roll.apply(_ac1, raw=True),
            "skewness": roll.skew(),
        }
    )
    return out


def kendall_tau_trend(series: pd.Series) -> dict:
    """Kendall's tau of an indicator vs time — the standard EWS trend statistic."""
    from scipy.stats import kendalltau

    s = series.dropna()
    if len(s) < 5:
        return {"tau": float("nan"), "pvalue": float("nan"), "n": len(s)}
    tau, p = kendalltau(np.arange(len(s)), s.to_numpy())
    return {"tau": float(tau), "pvalue": float(p), "n": len(s)}


def volatility_regimes(series: pd.Series, window: int = 12, n_regimes: int = 2) -> pd.Series:
    """Classify each period into volatility regimes via quantile thresholds on
    rolling std (simple, transparent alternative to HMMs)."""
    vol = series.pct_change().rolling(window, min_periods=window // 2).std()
    labels = pd.qcut(vol, n_regimes, labels=False, duplicates="drop")
    return labels.rename("vol_regime")

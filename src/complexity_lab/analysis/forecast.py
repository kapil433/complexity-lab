"""Short-horizon forecasting for monthly registration series.

Three honest baselines — seasonal naive (with drift), Holt-Winters
(exponential smoothing) and SARIMA — each evaluated by rolling-origin
backtest so the winner per series is an empirical fact, not a preference.

All functions take a monthly pd.Series indexed by date (freq MS) and return
a dataframe with columns ``mean``, ``lo``, ``hi`` indexed by future dates.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def seasonal_naive(series: pd.Series, horizon: int, season: int = 12) -> pd.DataFrame:
    """y_{t+h} = y_{t+h-season}, scaled by trailing-3 YoY drift; ±1.96σ of YoY errors."""
    s = series.dropna()
    ratio = (s / s.shift(season)).dropna()
    drift = float(ratio.tail(3).mean()) if len(ratio) >= 3 else 1.0
    resid_sd = float((s - s.shift(season) * drift).std())
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(), periods=horizon, freq="MS")
    base = [s.iloc[-season + (h % season)] if season - len(s) <= 0 else np.nan for h in range(horizon)]
    mean = np.array(base, dtype=float) * drift
    return pd.DataFrame({"mean": mean, "lo": mean - 1.96 * resid_sd, "hi": mean + 1.96 * resid_sd}, index=idx)


def holt_winters(series: pd.Series, horizon: int, season: int = 12) -> pd.DataFrame:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    s = series.dropna().astype(float)
    s.index = pd.DatetimeIndex(s.index, freq="MS")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(
            s, trend="add", seasonal="add", seasonal_periods=season, initialization_method="estimated"
        ).fit()
    mean = fit.forecast(horizon)
    resid_sd = float(np.std(fit.resid))
    return pd.DataFrame(
        {"mean": mean, "lo": mean - 1.96 * resid_sd, "hi": mean + 1.96 * resid_sd}, index=mean.index
    )


def sarima(series: pd.Series, horizon: int, season: int = 12) -> pd.DataFrame:
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    s = series.dropna().astype(float)
    s.index = pd.DatetimeIndex(s.index, freq="MS")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = SARIMAX(
            s, order=(1, 1, 1), seasonal_order=(1, 1, 1, season),
            enforce_stationarity=False, enforce_invertibility=False,
        ).fit(disp=False)
        pred = fit.get_forecast(horizon)
    ci = pred.conf_int(alpha=0.05)
    return pd.DataFrame(
        {"mean": pred.predicted_mean, "lo": ci.iloc[:, 0], "hi": ci.iloc[:, 1]},
        index=pred.predicted_mean.index,
    )


MODELS = {"seasonal_naive": seasonal_naive, "holt_winters": holt_winters, "sarima": sarima}


def backtest(
    series: pd.Series, model: str, horizon: int = 3, n_origins: int = 8, season: int = 12
) -> dict:
    """Rolling-origin evaluation: at each origin, fit on history, predict `horizon`
    ahead, score MAPE on actuals. Returns mean MAPE and per-origin detail."""
    fn = MODELS[model]
    s = series.dropna().astype(float)
    rows = []
    for k in range(n_origins, 0, -1):
        cut = len(s) - horizon - (k - 1)
        train, test = s.iloc[:cut], s.iloc[cut : cut + horizon]
        if len(train) < 2 * season + 4 or len(test) < horizon:
            continue
        try:
            fc = fn(train, horizon, season=season)
        except Exception:  # noqa: BLE001 — a failed fit scores as missing, not a crash
            continue
        ape = np.abs(fc["mean"].to_numpy()[: len(test)] - test.to_numpy()) / test.to_numpy()
        rows.append({"origin": train.index[-1], "mape": float(np.mean(ape))})
    detail = pd.DataFrame(rows)
    return {
        "model": model,
        "mape": float(detail["mape"].mean()) if not detail.empty else np.nan,
        "n_origins": len(detail),
        "detail": detail,
    }


def benchmark(series: pd.Series, horizon: int = 3, n_origins: int = 8) -> pd.DataFrame:
    """Backtest every model; returns a ranked table (best first)."""
    rows = [backtest(series, m, horizon=horizon, n_origins=n_origins) for m in MODELS]
    out = pd.DataFrame([{"model": r["model"], "mape": r["mape"], "n_origins": r["n_origins"]} for r in rows])
    return out.sort_values("mape").reset_index(drop=True)

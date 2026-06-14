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
    return pd.DataFrame(
        {
            "mean": np.maximum(mean, 0),
            "lo": np.maximum(mean - 1.96 * resid_sd, 0),
            "hi": np.maximum(mean + 1.96 * resid_sd, 0),
        },
        index=idx,
    )


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
        {
            "mean": mean.clip(lower=0),
            "lo": (mean - 1.96 * resid_sd).clip(lower=0),
            "hi": (mean + 1.96 * resid_sd).clip(lower=0),
        },
        index=mean.index,
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
        {
            "mean": pred.predicted_mean.clip(lower=0),
            "lo": ci.iloc[:, 0].clip(lower=0),
            "hi": ci.iloc[:, 1].clip(lower=0),
        },
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
        predicted = fc["mean"].to_numpy()[: len(test)]
        actual = test.to_numpy()
        error = predicted - actual
        abs_error = np.abs(error)
        ape = abs_error / np.maximum(np.abs(actual), 1)
        covered = (
            (actual >= fc["lo"].to_numpy()[: len(test)])
            & (actual <= fc["hi"].to_numpy()[: len(test)])
        )
        rows.append(
            {
                "origin": train.index[-1],
                "mape": float(np.mean(ape)),
                "absolute_error": float(abs_error.sum()),
                "actual_units": float(np.abs(actual).sum()),
                "signed_error": float(error.sum()),
                "n_predictions": len(test),
                "covered": int(covered.sum()),
            }
        )
    detail = pd.DataFrame(rows)
    absolute_error = detail["absolute_error"].sum() if not detail.empty else np.nan
    actual_units = detail["actual_units"].sum() if not detail.empty else np.nan
    n_predictions = detail["n_predictions"].sum() if not detail.empty else 0
    return {
        "model": model,
        "mape": float(detail["mape"].mean()) if not detail.empty else np.nan,
        "wape": float(absolute_error / actual_units)
        if not detail.empty and actual_units
        else np.nan,
        "mae": float(absolute_error / n_predictions) if n_predictions else np.nan,
        "bias": float(detail["signed_error"].sum() / n_predictions)
        if n_predictions
        else np.nan,
        "interval_coverage": float(detail["covered"].sum() / n_predictions)
        if n_predictions
        else np.nan,
        "n_origins": len(detail),
        "detail": detail,
    }


def benchmark(series: pd.Series, horizon: int = 3, n_origins: int = 8) -> pd.DataFrame:
    """Backtest every model; returns a ranked table (best first)."""
    rows = [backtest(series, m, horizon=horizon, n_origins=n_origins) for m in MODELS]
    out = pd.DataFrame(
        [
            {
                "model": result["model"],
                "mape": result["mape"],
                "wape": result["wape"],
                "mae": result["mae"],
                "bias": result["bias"],
                "interval_coverage": result["interval_coverage"],
                "n_origins": result["n_origins"],
            }
            for result in rows
        ]
    )
    naive_mape = out.loc[out["model"] == "seasonal_naive", "mape"].iloc[0]
    out["naive_relative_skill"] = 1 - out["mape"] / naive_mape
    return out.sort_values("mape").reset_index(drop=True)

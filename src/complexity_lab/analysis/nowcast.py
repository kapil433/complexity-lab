"""Nowcasting retail registrations from wholesale dispatches.

Wholesale (factory → dealer) is observable weeks before registrations settle
(VAHAN's most recent months are partial). A nowcast regression of retail on
contemporaneous wholesale + seasonal memory gives a same-month estimate.

Everything here is deliberately simple and honestly evaluated: rolling
out-of-sample one-step predictions compared against a seasonal-naive baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def cross_correlation(
    a: pd.Series, b: pd.Series, max_lag: int = 6, on_growth: bool = True
) -> pd.DataFrame:
    """corr(a_t, b_{t-k}) for k in [-max_lag, max_lag]; k>0 means b leads a."""
    if on_growth:
        a, b = a.pct_change(), b.pct_change()
    rows = []
    for k in range(-max_lag, max_lag + 1):
        c = a.corr(b.shift(k))
        rows.append({"lag": k, "corr": c})
    return pd.DataFrame(rows).set_index("lag")


def _design(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["retail_lag12"] = d["retail"].shift(12)
    d["month_factor"] = d["month"].astype(str)
    return d


def nowcast_eval(
    rw: pd.DataFrame, test_months: int = 12, min_train: int = 18
) -> dict:
    """Rolling one-step out-of-sample nowcast of retail from wholesale.

    ``rw`` needs columns: date, year, month, retail, wholesale (monthly, sorted).
    Model: retail_t ~ wholesale_t + retail_{t-12}. Baseline: retail_{t-12}
    scaled by trailing-3-month YoY drift (seasonal naive with drift).
    Returns per-month predictions and MAPE comparison.
    """
    d = _design(rw.sort_values("date").reset_index(drop=True))
    preds = []
    for i in range(len(d) - test_months, len(d)):
        train = d.iloc[:i].dropna(subset=["retail", "wholesale", "retail_lag12"])
        if len(train) < min_train:
            continue
        X = sm.add_constant(train[["wholesale", "retail_lag12"]].astype(float))
        model = sm.OLS(train["retail"].astype(float), X).fit()
        row = d.iloc[i]
        if pd.isna(row["wholesale"]) or pd.isna(row["retail_lag12"]):
            continue
        x_new = pd.DataFrame(
            {"const": [1.0], "wholesale": [row["wholesale"]], "retail_lag12": [row["retail_lag12"]]}
        )
        yhat = float(model.predict(x_new).iloc[0])

        # seasonal-naive-with-drift baseline
        drift_window = d.iloc[max(0, i - 3) : i]
        drift = (drift_window["retail"] / drift_window["retail_lag12"]).mean()
        base = float(row["retail_lag12"] * (drift if np.isfinite(drift) else 1.0))

        preds.append(
            {
                "date": row["date"],
                "actual": float(row["retail"]),
                "nowcast": yhat,
                "baseline": base,
            }
        )
    out = pd.DataFrame(preds)
    if out.empty:
        return {"predictions": out, "mape_nowcast": np.nan, "mape_baseline": np.nan}
    out["ape_nowcast"] = (out["nowcast"] - out["actual"]).abs() / out["actual"]
    out["ape_baseline"] = (out["baseline"] - out["actual"]).abs() / out["actual"]
    return {
        "predictions": out,
        "mape_nowcast": float(out["ape_nowcast"].mean()),
        "mape_baseline": float(out["ape_baseline"].mean()),
        "n_oos": len(out),
    }

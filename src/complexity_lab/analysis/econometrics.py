"""Econometric tools: panel correlations/regressions, Granger causality, changepoints."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import grangercausalitytests


def correlation_matrix(df: pd.DataFrame, cols: list[str], method: str = "spearman") -> pd.DataFrame:
    """Correlation matrix over selected columns (spearman default — robust to scale)."""
    return df[cols].corr(method=method)


def panel_ols(
    df: pd.DataFrame,
    y: str,
    x: list[str],
    entity_col: str = "state_code",
    time_col: str = "year",
    entity_effects: bool = True,
    time_effects: bool = False,
) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Fixed-effects OLS via dummy variables (LSDV). Drops rows with NaNs.

    Standard errors are clustered by entity.
    """
    d = df[[y, *x, entity_col, time_col]].dropna().copy()
    X = d[x].astype(float)
    if entity_effects:
        X = pd.concat([X, pd.get_dummies(d[entity_col], prefix="ent", drop_first=True, dtype=float)], axis=1)
    if time_effects:
        X = pd.concat([X, pd.get_dummies(d[time_col], prefix="t", drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X)
    model = sm.OLS(d[y].astype(float), X)
    return model.fit(cov_type="cluster", cov_kwds={"groups": d[entity_col]})


def granger(
    df: pd.DataFrame, cause: str, effect: str, maxlag: int = 4
) -> pd.DataFrame:
    """Granger-causality F-test p-values for lags 1..maxlag on a single series pair.

    Expects a time-ordered dataframe; differencing/stationarity is the caller's job.
    """
    d = df[[effect, cause]].dropna()
    res = grangercausalitytests(d, maxlag=maxlag)
    rows = [
        {"lag": lag, "f_pvalue": out[0]["ssr_ftest"][1], "f_stat": out[0]["ssr_ftest"][0]}
        for lag, out in res.items()
    ]
    return pd.DataFrame(rows).set_index("lag")


def did(
    df: pd.DataFrame,
    treated: str | list[str],
    controls: list[str],
    event_date: str,
    value_col: str,
    entity_col: str = "state_code",
    date_col: str = "date",
    pre_months: int = 6,
    post_months: int = 6,
) -> dict:
    """Difference-in-differences on a monthly panel around an event date.

    ATT = (treated_post − treated_pre) − (control_post − control_pre).
    Also returns a per-control 'placebo' distribution (each control treated as
    if it were the treated unit) so the ATT can be judged against in-sample noise.
    """
    treated = [treated] if isinstance(treated, str) else list(treated)
    d = df[[entity_col, date_col, value_col]].dropna().copy()
    d[date_col] = pd.to_datetime(d[date_col])
    event = pd.Timestamp(event_date)
    lo = event - pd.DateOffset(months=pre_months)
    hi = event + pd.DateOffset(months=post_months)
    d = d[(d[date_col] >= lo) & (d[date_col] < hi)]
    d["post"] = d[date_col] >= event

    def _gap(entities: list[str]) -> float:
        sub = d[d[entity_col].isin(entities)]
        means = sub.groupby("post")[value_col].mean()
        if len(means) < 2:
            return np.nan
        return float(means[True] - means[False])

    att = _gap(treated) - _gap(controls)
    placebos = {c: _gap([c]) - _gap([x for x in controls if x != c]) for c in controls}
    placebo_vals = np.array([v for v in placebos.values() if np.isfinite(v)])
    rank_p = (
        float((np.sum(np.abs(placebo_vals) >= abs(att)) + 1) / (placebo_vals.size + 1))
        if placebo_vals.size
        else np.nan
    )
    return {
        "att": att,
        "treated_change": _gap(treated),
        "control_change": _gap(controls),
        "placebos": placebos,
        "placebo_rank_p": rank_p,
        "n_treated": len(treated),
        "n_controls": len(controls),
        "window": (str(lo.date()), str(hi.date())),
    }


def changepoints(
    series: pd.Series, n_bkps: int | None = None, penalty: float | None = None, model: str = "rbf"
) -> list[int]:
    """Offline changepoint detection (ruptures, PELT/Binseg).

    Pass ``n_bkps`` for a fixed number of breaks (Binseg) or ``penalty``
    for automatic selection (PELT). Returns integer positions into the series.
    """
    import ruptures as rpt

    x = series.dropna().to_numpy(dtype=float).reshape(-1, 1)
    if n_bkps is not None:
        algo = rpt.Binseg(model=model).fit(x)
        bkps = algo.predict(n_bkps=n_bkps)
    else:
        algo = rpt.Pelt(model=model).fit(x)
        bkps = algo.predict(pen=penalty if penalty is not None else 3 * np.log(len(x)))
    return [b for b in bkps if b < len(x)]  # drop the terminal boundary

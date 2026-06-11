"""Bass diffusion model: fit to adoption series and run forward scenarios.

Bass (1969): f(t)/[1-F(t)] = p + q·F(t), with innovation coefficient ``p``,
imitation coefficient ``q`` and market potential ``m``. We fit cumulative
adoption with nonlinear least squares and expose scenario projection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


def bass_cumulative(t: np.ndarray, p: float, q: float, m: float) -> np.ndarray:
    """Closed-form cumulative Bass adoption at times t (t starts at 0)."""
    e = np.exp(-(p + q) * t)
    return m * (1 - e) / (1 + (q / p) * e)


def fit_bass(adoption: pd.Series, m_max_multiple: float = 50.0) -> dict:
    """Fit Bass (p, q, m) to a *cumulative* adoption series indexed 0..n-1.

    Returns parameters, standard errors, R², and the implied peak time
    t* = ln(q/p)/(p+q).
    """
    y = adoption.dropna().to_numpy(dtype=float)
    if len(y) < 5 or y[-1] <= 0:
        return {"p": np.nan, "q": np.nan, "m": np.nan, "r2": np.nan, "n": len(y)}
    t = np.arange(len(y), dtype=float)
    p0 = [0.003, 0.3, max(y[-1] * 2, 1.0)]
    bounds = ([1e-6, 1e-6, y[-1]], [0.5, 2.0, y[-1] * m_max_multiple])
    try:
        params, cov = curve_fit(bass_cumulative, t, y, p0=p0, bounds=bounds, maxfev=20000)
    except RuntimeError:
        return {"p": np.nan, "q": np.nan, "m": np.nan, "r2": np.nan, "n": len(y)}
    p, q, m = params
    pred = bass_cumulative(t, *params)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    se = np.sqrt(np.diag(cov)) if cov is not None else [np.nan] * 3
    return {
        "p": float(p),
        "q": float(q),
        "m": float(m),
        "p_se": float(se[0]),
        "q_se": float(se[1]),
        "m_se": float(se[2]),
        "r2": 1 - ss_res / ss_tot if ss_tot > 0 else np.nan,
        "peak_time": float(np.log(q / p) / (p + q)) if p > 0 and q > p else np.nan,
        "n": len(y),
    }


def project_bass(
    fit: dict, horizon: int, t0: int = 0, p_mult: float = 1.0, q_mult: float = 1.0, m_mult: float = 1.0
) -> pd.DataFrame:
    """Forward scenario: scale fitted (p, q, m) and project cumulative + incremental adoption.

    Multipliers express policy levers — e.g. ``q_mult=1.2`` for stronger
    social contagion (visibility of EVs), ``m_mult`` for a larger eventual market.
    """
    t = np.arange(t0, t0 + horizon, dtype=float)
    cum = bass_cumulative(t, fit["p"] * p_mult, fit["q"] * q_mult, fit["m"] * m_mult)
    inc = np.diff(cum, prepend=cum[0] if t0 == 0 else np.nan)
    return pd.DataFrame({"t": t.astype(int), "cumulative": cum, "incremental": inc})


def fit_bass_by_state(
    panel_month: pd.DataFrame,
    value_col: str = "ev_regs",
    state_col: str = "state_code",
    min_total: int = 500,
) -> pd.DataFrame:
    """Fit Bass per state on cumulative monthly adoption; skip tiny markets."""
    rows = []
    for code, grp in panel_month.sort_values(["year", "month"]).groupby(state_col):
        cum = grp[value_col].fillna(0).cumsum()
        if cum.iloc[-1] < min_total:
            continue
        res = fit_bass(cum.reset_index(drop=True))
        res[state_col] = code
        rows.append(res)
    return pd.DataFrame(rows).set_index(state_col)

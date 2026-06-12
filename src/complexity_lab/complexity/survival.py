"""Discrete-time survival analysis of regime switches (Project B, step 5).

Question: what makes a state switch energy regime sooner? We build a risk set —
one row per state-year while the state is still in its origin regime — and fit
a discrete-time hazard model (logit on the switch indicator with standardized
covariates). Odds ratios > 1 mean the covariate accelerates the transition.

This is the standard discrete-time alternative to Cox PH: with yearly data and
~30 states it is the honest specification (ties are everywhere; the
proportional-hazards machinery would add nothing but fragility).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def build_risk_set(
    calendar: pd.DataFrame,
    panel_year: pd.DataFrame,
    covariates: list[str],
    origin_regime: int | None = None,
) -> pd.DataFrame:
    """One row per state-year at risk of *first* regime switch.

    A state contributes rows from its first observed year until (and including)
    the year of its first switch; ``switched`` = 1 only on that final row.
    ``origin_regime``: restrict to states starting in that regime (default: each
    state's own first regime).
    """
    rows = []
    for code, grp in calendar.sort_values("year").groupby("state_code"):
        start_regime = int(grp["regime"].iloc[0])
        if origin_regime is not None and start_regime != origin_regime:
            continue
        for _, r in grp.iterrows():
            switched = int(r["regime"]) != start_regime
            rows.append(
                {
                    "state_code": code,
                    "year": int(r["year"]),
                    "switched": int(switched),
                    "origin_regime": start_regime,
                }
            )
            if switched:
                break
    risk = pd.DataFrame(rows)
    merged = risk.merge(
        panel_year[["state_code", "year", *covariates]], on=["state_code", "year"], how="left"
    )
    return merged


def discrete_hazard_model(
    risk_set: pd.DataFrame, covariates: list[str], add_time_trend: bool = True
) -> dict:
    """Logit hazard: P(switch in year t | at risk) ~ covariates (+ time trend).

    Covariates are z-standardized so odds ratios read 'per 1 SD'.
    """
    d = risk_set.dropna(subset=covariates).copy()
    X = pd.DataFrame(index=d.index)
    for c in covariates:
        col = d[c].astype(float)
        sd = col.std(ddof=0)
        X[c] = (col - col.mean()) / (sd if sd > 0 else 1.0)
    if add_time_trend:
        X["year_c"] = d["year"] - d["year"].mean()
    X = sm.add_constant(X)
    model = sm.Logit(d["switched"].astype(float), X.astype(float))
    res = model.fit(disp=False, maxiter=200)

    params = res.params.drop("const")
    out = pd.DataFrame(
        {
            "coef": params,
            "odds_ratio_per_sd": np.exp(params),
            "p_value": res.pvalues.drop("const"),
        }
    )
    return {
        "table": out,
        "n_obs": int(res.nobs),
        "n_events": int(d["switched"].sum()),
        "llf": float(res.llf),
        "pseudo_r2": float(res.prsquared),
        "result": res,
    }


def kaplan_meier(risk_set: pd.DataFrame) -> pd.DataFrame:
    """Survival curve: fraction of states still in their origin regime by year."""
    rows = []
    for year in sorted(risk_set["year"].unique()):
        at_risk = risk_set[risk_set["year"] == year]
        rows.append(
            {
                "year": int(year),
                "n_at_risk": len(at_risk),
                "n_switched": int(at_risk["switched"].sum()),
            }
        )
    km = pd.DataFrame(rows)
    km["hazard"] = km["n_switched"] / km["n_at_risk"].clip(lower=1)
    km["survival"] = (1 - km["hazard"]).cumprod()
    return km

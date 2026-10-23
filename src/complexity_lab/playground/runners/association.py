"""Association, panel, and break experiments.

p-values are reported against the knob the user set. None of these designs
is a causal claim, and the interpretation says so in the same sentence as the number.
"""

from __future__ import annotations

import warnings

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from complexity_lab.analysis.econometrics import changepoints, granger, panel_ols
from complexity_lab.playground.data import national_month, state_year
from complexity_lab.playground.interpret import (
    association_sentence,
    granger_sentence,
    income_elasticity_sentence,
)
from complexity_lab.playground.models import ExperimentSpec, check
from complexity_lab.playground.registry import playground_experiment
from complexity_lab.playground.runners.common import (
    ALL_INDIA,
    CREDIT,
    FUEL_PRICE,
    INCOME,
    POPULATION,
    blocked,
    finish,
)


def _window_problem(params: dict) -> str | None:
    if "year_start" in params and int(params["year_start"]) > int(params["year_end"]):
        return "The first year is after the last year."
    return None


def _cross_section(con: duckdb.DuckDBPyConnection, params: dict, columns: list[str]) -> pd.DataFrame:
    frame = state_year(con, int(params["year"]), int(params["year"]))
    if "min_regs" in params:
        frame = frame[frame["total_regs"] >= int(params["min_regs"])]
    return frame.dropna(subset=columns)


def _spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int] | None:
    mask = x.notna() & y.notna()
    n = int(mask.sum())
    if n < 8:
        return None
    if x[mask].nunique() < 2 or y[mask].nunique() < 2:
        return None
    rho, p_value = stats.spearmanr(x[mask], y[mask])
    if not np.isfinite(rho) or not np.isfinite(p_value):
        return None
    return float(rho), float(p_value), n


def _dependent_extra() -> str:
    return (
        "State-years are repeated measures, so the p-value treats dependent rows as independent "
        "and is anti-conservative."
    )


@playground_experiment("E01")
def income_ev(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = _cross_section(con, params, ["real_pc_income_inr", "ev_share"])
    found = _spearman(frame["real_pc_income_inr"], frame["ev_share"])
    if found is None:
        return blocked(spec, params, "Not enough states with both real income and an EV share.", notes=(INCOME,))
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_states": n, "alpha": float(params["alpha"])},
        checks=[check("association", True, f"rho={rho:.3f}, p={p_value:.4f}.")],
        interpretation=association_sentence(
            "real per-capita income", "EV share", rho, p_value, float(params["alpha"]), n,
            "Neighbours can share shocks, so the p-value is approximate.",
        ),
        frame=frame[["state_name", "real_pc_income_inr", "ev_share", "income_constant_quality"]],
        chart="scatter", x="real_pc_income_inr", y="ev_share",
        notes=(INCOME,),
    )


@playground_experiment("E02")
def urban_ev(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = _cross_section(con, params, ["urban_pct", "ev_share"])
    found = _spearman(frame["urban_pct"], frame["ev_share"])
    if found is None:
        return blocked(spec, params, "Not enough states with both an urban share and an EV share.", notes=(POPULATION,))
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_states": n},
        checks=[check("association", True, f"rho={rho:.3f}. Urban share does not vary by year.")],
        interpretation=association_sentence(
            "the 2011 urban share", "EV share", rho, p_value, float(params["alpha"]), n,
            "The urban share is held fixed at 2011, so this cannot be a within-state urbanisation effect.",
        ),
        frame=frame[["state_name", "urban_pct", "ev_share"]],
        chart="scatter", x="urban_pct", y="ev_share",
        notes=(POPULATION,),
    )


@playground_experiment("E03")
def petrol_diesel(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    frame = state_year(con, int(params["year_start"]), int(params["year_end"]))
    priced = frame.dropna(subset=["petrol_price_inr", "diesel_share"])
    if bool(params["state_prices_only"]):
        priced = priced[priced["petrol_price_basis"] == "state"]
        sample = "state prices only"
    else:
        sample = "state prices and the Delhi fallback mixed together"
    found = _spearman(priced["petrol_price_inr"], priced["diesel_share"])
    if found is None:
        return blocked(
            spec, params,
            "Not enough priced state-years for a Spearman correlation.",
            notes=(FUEL_PRICE,),
        )
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_state_years": n, "state_prices_only": bool(params["state_prices_only"])},
        checks=[check("price_sample", True, sample)],
        interpretation=association_sentence(
            "petrol price", "diesel share", rho, p_value, float(params["alpha"]), n,
            f"The sample is {sample}. {_dependent_extra()}",
        ),
        frame=priced[["state_name", "year", "petrol_price_inr", "diesel_share", "petrol_price_basis"]],
        chart="scatter", x="petrol_price_inr", y="diesel_share",
        notes=(FUEL_PRICE,),
    )


@playground_experiment("E04")
def gsdp_growth(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    frame = state_year(con, int(params["year_start"]), int(params["year_end"]))
    found = _spearman(frame["real_gsdp_growth_pct"], frame["yoy_growth"])
    if found is None:
        return blocked(spec, params, "Not enough state-years have both growth rates.")
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_state_years": n},
        checks=[check("calendars_disclosed", True, "GSDP growth is financial-year; registrations are calendar-year.")],
        interpretation=association_sentence(
            "real GSDP growth", "registration growth", rho, p_value, float(params["alpha"]), n,
            "The two growth rates do not share a calendar. " + _dependent_extra(),
        ),
        frame=frame.dropna(subset=["real_gsdp_growth_pct", "yoy_growth"])[
            ["state_name", "year", "real_gsdp_growth_pct", "yoy_growth", "gsdp_quality"]
        ],
        chart="scatter", x="real_gsdp_growth_pct", y="yoy_growth",
    )


@playground_experiment("E05")
def cng_spread(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    frame = state_year(con, int(params["year_start"]), int(params["year_end"]))
    priced = frame[
        (frame["petrol_price_basis"] == "state") & (frame["cng_price_basis"] == "state")
    ].dropna(subset=["petrol_price_inr", "cng_price_inr", "cng_share"])
    priced = priced.copy()
    priced["sticker_gap"] = priced["petrol_price_inr"] - priced["cng_price_inr"]
    found = _spearman(priced["sticker_gap"], priced["cng_share"])
    if found is None:
        return blocked(
            spec, params,
            "Fewer than eight state-years have both a state petrol price and a state CNG price.",
            notes=(FUEL_PRICE,),
        )
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_state_years": n},
        checks=[check("state_prices", True, "Delhi fallback prices were excluded.")],
        interpretation=association_sentence(
            "the petrol-minus-CNG sticker gap", "CNG share", rho, p_value, float(params["alpha"]), n,
            "Petrol is INR per litre and CNG is INR per kg, so the gap is not an energy-equivalent price. "
            + _dependent_extra(),
        ),
        frame=priced[["state_name", "year", "sticker_gap", "cng_share"]],
        chart="scatter", x="sticker_gap", y="cng_share",
        notes=(FUEL_PRICE,),
    )


def _fit_panel(
    frame: pd.DataFrame,
    y: str,
    x: str,
    time_effects: bool,
) -> tuple[object | None, str | None]:
    if frame[x].nunique() < 2 or frame[y].nunique() < 2:
        return None, "The outcome or the driver does not vary."
    if frame["state_code"].nunique() < 8 or len(frame) < 30:
        return None, "Fewer than eight states or thirty state-years remain after dropping missing values."
    if time_effects and frame["year"].nunique() < 3:
        return None, "Year effects need at least three years."
    try:
        fit = panel_ols(
            frame,
            y,
            [x],
            entity_effects=True,
            time_effects=time_effects,
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        return None, f"The fixed-effects regression did not solve ({exc})."
    if x not in fit.params.index:
        return None, "The driver was absorbed by the fixed effects, so there is no coefficient to report."
    return fit, None


@playground_experiment("E06")
def income_within(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem, notes=(INCOME,))
    frame = state_year(con, int(params["year_start"]), int(params["year_end"]))
    frame = frame[(frame["total_regs"] > 0) & frame["real_pc_income_inr"].notna()].copy()
    frame["log_regs"] = np.log(frame["total_regs"].astype(float))
    frame["log_income"] = np.log(frame["real_pc_income_inr"].astype(float))
    fit, reason = _fit_panel(frame, "log_regs", "log_income", bool(params["time_effects"]))
    if fit is None:
        return blocked(spec, params, reason or "The income regression was not estimated.", notes=(INCOME,))
    coef = float(fit.params["log_income"])
    p_value = float(fit.pvalues["log_income"])
    return finish(
        spec, params, status="ok",
        metrics={
            "elasticity": coef,
            "std_error": float(fit.bse["log_income"]),
            "p_value": p_value,
            "n": int(fit.nobs),
            "n_states": int(frame["state_code"].nunique()),
            "time_effects": bool(params["time_effects"]),
        },
        checks=[check("within_estimator", True, "State fixed effects, standard errors clustered by state.")],
        interpretation=income_elasticity_sentence(
            coef, p_value, float(params["alpha"]), bool(params["time_effects"]),
            int(fit.nobs), int(frame["state_code"].nunique()),
        ),
        frame=frame[["state_name", "year", "log_regs", "log_income"]],
        chart="scatter", x="log_income", y="log_regs",
        notes=(INCOME,),
    )


@playground_experiment("E07")
def ev_price_within(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem, notes=(FUEL_PRICE,))
    frame = state_year(con, int(params["year_start"]), int(params["year_end"]))
    frame = frame.dropna(subset=["ev_share", "petrol_price_inr"]).copy()
    if bool(params["state_prices_only"]):
        frame = frame[frame["petrol_price_basis"] == "state"]
        sample = "state prices only"
    else:
        sample = "state prices mixed with the Delhi fallback"
    frame["ev_share_pp"] = frame["ev_share"] * 100
    fit, reason = _fit_panel(frame, "ev_share_pp", "petrol_price_inr", bool(params["time_effects"]))
    if fit is None:
        return blocked(spec, params, reason or "The price regression was not estimated.", notes=(FUEL_PRICE,))
    coef = float(fit.params["petrol_price_inr"])
    p_value = float(fit.pvalues["petrol_price_inr"])
    alpha = float(params["alpha"])
    decision = "rejects" if p_value < alpha else "does not reject"
    effects = "with year effects" if params["time_effects"] else "without year effects"
    identifying = (
        "Year effects are on, so the national petrol-price cycle is absorbed and only state deviations remain."
        if params["time_effects"]
        else "Year effects are off, so the common national price path remains inside the coefficient."
    )
    return finish(
        spec, params, status="ok",
        metrics={
            "pp_per_rupee": coef,
            "std_error": float(fit.bse["petrol_price_inr"]),
            "p_value": p_value,
            "n": int(fit.nobs),
            "time_effects": bool(params["time_effects"]),
        },
        checks=[check("price_sample", True, sample)],
        interpretation=(
            f"{effects.capitalize()} and using {sample}, a one-rupee higher petrol price is associated "
            f"with {coef:.3f} percentage points of EV share (n={int(fit.nobs)}). "
            f"At alpha {alpha:.2f}, the test {decision} a zero coefficient. {identifying} "
            "Prices are approximate. This is not a tax effect."
        ),
        frame=frame[["state_name", "year", "ev_share_pp", "petrol_price_inr", "petrol_price_basis"]],
        chart="scatter", x="petrol_price_inr", y="ev_share_pp",
        notes=(FUEL_PRICE,),
    )


@playground_experiment("E08")
def diesel_leads_ev(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    monthly = national_month(con).sort_values("date")
    lag = int(params["max_lag"])
    diff = pd.DataFrame(
        {
            "diesel_diff": monthly["diesel_share"].diff(),
            "ev_diff": monthly["ev_share"].diff(),
        }
    ).dropna()
    if len(diff) < lag + 24:
        return blocked(spec, params, "Not enough monthly differences for this lag.", notes=(ALL_INDIA,))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            forward = granger(diff, "diesel_diff", "ev_diff", maxlag=lag)
            reverse = granger(diff, "ev_diff", "diesel_diff", maxlag=lag)
        except (ValueError, np.linalg.LinAlgError) as exc:
            return blocked(spec, params, f"The lead-lag test did not solve ({exc}).", notes=(ALL_INDIA,))
    forward_p = float(forward.loc[lag, "f_pvalue"])
    reverse_p = float(reverse.loc[lag, "f_pvalue"])
    return finish(
        spec, params, status="ok",
        metrics={"forward_p": forward_p, "reverse_p": reverse_p, "lag": lag, "n_differences": int(len(diff))},
        checks=[check("both_directions", True, "The reverse test is reported beside the tested direction.")],
        interpretation=granger_sentence(
            "the diesel share", "the EV share", forward_p, reverse_p, lag, float(params["alpha"])
        ),
        frame=diff.reset_index(drop=True).assign(step=lambda frame: np.arange(len(frame))),
        chart="line", x="step", y="ev_diff",
        notes=(ALL_INDIA, "Both series are first differences of All India shares."),
    )


@playground_experiment("E09")
def ev_breaks(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    monthly = national_month(con).sort_values("date")
    series = monthly.set_index("date")["ev_share"].astype(float)
    penalty = float(params["penalty"])
    try:
        positions = changepoints(series, penalty=penalty)
    except (ValueError, np.linalg.LinAlgError) as exc:
        return blocked(spec, params, f"Changepoint detection failed ({exc}).", notes=(ALL_INDIA,))
    dates = [str(series.index[position].date()) for position in positions]
    shown = ", ".join(dates) if dates else "none"
    return finish(
        spec, params, status="ok",
        metrics={"n_breaks": len(dates), "penalty": penalty},
        checks=[check("breaks_reported", True, f"Breaks: {shown}.")],
        interpretation=(
            f"At PELT penalty {penalty:.1f}, the monthly All India EV share has {len(dates)} "
            f"interior break(s): {shown}. A higher penalty finds fewer breaks or the same breaks. "
            "A break is a change in the statistical path. It is not, by itself, the name of a policy."
        ),
        frame=monthly[["date", "ev_share"]],
        chart="line", x="date", y="ev_share",
        notes=(ALL_INDIA,),
    )


@playground_experiment("E10")
def income_split(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = state_year(con, int(params["year"]), int(params["year"]))
    frame = frame.dropna(subset=["real_pc_income_inr", "ev_share"])
    if len(frame) < 10:
        return blocked(spec, params, "Fewer than ten states have both income and EV share.", notes=(INCOME,))
    percentile = int(params["income_percentile"])
    cut = float(np.quantile(frame["real_pc_income_inr"], percentile / 100))
    high = frame[frame["real_pc_income_inr"] >= cut]["ev_share"]
    low = frame[frame["real_pc_income_inr"] < cut]["ev_share"]
    if len(high) < 5 or len(low) < 5:
        return blocked(
            spec, params,
            "The percentile puts fewer than five states on one side. Choose a less extreme split.",
            notes=(INCOME,),
        )
    statistic, p_value = stats.mannwhitneyu(high, low, alternative="two-sided")
    alpha = float(params["alpha"])
    decision = "rejects" if p_value < alpha else "does not reject"
    gap_pp = (float(high.median()) - float(low.median())) * 100
    return finish(
        spec, params, status="ok",
        metrics={
            "income_cut_inr": cut,
            "n_high": int(len(high)),
            "n_low": int(len(low)),
            "median_gap_pp": gap_pp,
            "u_statistic": float(statistic),
            "p_value": float(p_value),
        },
        checks=[check("split", True, f"High group is the top {100 - percentile}% by the chosen percentile rule.")],
        interpretation=(
            f"At the {percentile}th percentile of real income in {int(params['year'])} "
            f"(₹{cut:,.0f}), the high group's median EV share is {gap_pp:+.2f} percentage points "
            f"from the low group's median ({len(high)} versus {len(low)} states). "
            f"Mann-Whitney p={p_value:.4f}. At alpha {alpha:.2f}, the test {decision} equal distributions. "
            "The percentile is a choice. It is not an income threshold the data discovered, "
            "and the difference is not an effect of income."
        ),
        frame=frame[["state_name", "real_pc_income_inr", "ev_share"]],
        chart="scatter", x="real_pc_income_inr", y="ev_share",
        notes=(INCOME,),
    )


@playground_experiment("E11")
def around_april_2020(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    monthly = national_month(con).sort_values("date")
    event = pd.Timestamp("2020-04-01")
    window = int(params["window_months"])
    pre_start = event - pd.DateOffset(months=window)
    post_end = event + pd.DateOffset(months=window)
    pre = monthly[(monthly["date"] >= pre_start) & (monthly["date"] < event)]
    post = monthly[(monthly["date"] >= event) & (monthly["date"] < post_end)]
    if len(pre) < window or len(post) < window:
        return blocked(spec, params, "The window is not fully observed on both sides of April 2020.", notes=(ALL_INDIA,))
    pre_share = float(pre["diesel_share"].mean())
    post_share = float(post["diesel_share"].mean())
    march = monthly[monthly["date"] == pd.Timestamp("2020-03-01")]
    february = monthly[monthly["date"] == pd.Timestamp("2020-02-01")]
    march_regs = float(march["total_regs"].iloc[0]) if not march.empty else np.nan
    february_regs = float(february["total_regs"].iloc[0]) if not february.empty else np.nan
    change_pp = (post_share - pre_share) * 100
    frame = pd.DataFrame(
        {"period": [f"{window} months before", f"{window} months after"], "mean_diesel_share": [pre_share, post_share]}
    )
    return finish(
        spec, params, status="ok",
        metrics={
            "pre_diesel_share": pre_share,
            "post_diesel_share": post_share,
            "change_pp": change_pp,
            "march_2020_regs": march_regs,
            "february_2020_regs": february_regs,
            "window_months": window,
        },
        checks=[
            check(
                "shock_not_separated",
                True,
                "April 2020 combines BS6 and the lockdown. The check records that limit; it does not remove it.",
            )
        ],
        interpretation=(
            f"Mean All India diesel share is {pre_share:.1%} in the {window} months before April 2020 "
            f"and {post_share:.1%} in the {window} months after, {change_pp:+.2f} percentage points. "
            f"March 2020 registrations are {march_regs:,.0f} against {february_regs:,.0f} in February. "
            "The share gap and the March volume spike are different facts. "
            "A longer window mixes in more of the later recovery. "
            "Neither number separates BS6 from the lockdown."
        ),
        frame=frame, chart="bar", x="period", y="mean_diesel_share",
        notes=(ALL_INDIA,),
    )


@playground_experiment("E12")
def credit_ev(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = _cross_section(con, params, ["broad_credit_per_capita_inr", "ev_share"])
    found = _spearman(frame["broad_credit_per_capita_inr"], frame["ev_share"])
    if found is None:
        return blocked(spec, params, "Not enough states have both credit depth and an EV share.", notes=(CREDIT,))
    rho, p_value, n = found
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": rho, "p_value": p_value, "n_states": n},
        checks=[check("not_auto_finance", True, "The driver is personal-loan depth, not vehicle finance.")],
        interpretation=association_sentence(
            "personal loans per estimated person", "EV share", rho, p_value, float(params["alpha"]), n,
            "EV share is not divided by population, so the two measures do not share a denominator. "
            "The credit series is still not auto-loan penetration.",
        ),
        frame=frame[["state_name", "broad_credit_per_capita_inr", "ev_share", "credit_depth_quality"]],
        chart="scatter", x="broad_credit_per_capita_inr", y="ev_share",
        notes=(CREDIT,),
    )

"""Forecast backtests and explicitly simulated scenarios.

A backtest that does not beat the seasonal naive is reported as such.
A scenario records the assumption and is never labelled as a forecast.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from complexity_lab.analysis.forecast import backtest, seasonal_naive
from complexity_lab.playground.data import monthly_state, national_month, national_year, state_codes
from complexity_lab.playground.interpret import (
    bias_sentence,
    coverage_sentence,
    scenario_shock_sentence,
    skill_sentence,
)
from complexity_lab.playground.models import ExperimentSpec, check
from complexity_lab.playground.registry import playground_experiment
from complexity_lab.playground.runners.common import ALL_INDIA, blocked, finish

FAST_MODELS = ("seasonal_naive", "holt_winters")


def _score(series: pd.Series, horizon: int, n_origins: int, include_sarima: bool) -> pd.DataFrame:
    models = list(FAST_MODELS)
    if include_sarima:
        models.append("sarima")
    rows = []
    for model in models:
        result = backtest(series, model, horizon=horizon, n_origins=n_origins)
        naive_row = next((item for item in rows if item["model"] == "seasonal_naive"), None)
        naive_mape = naive_row["mape"] if naive_row else result["mape"]
        skill = (
            float(1 - result["mape"] / naive_mape)
            if naive_mape and np.isfinite(naive_mape) and np.isfinite(result["mape"])
            else np.nan
        )
        rows.append(
            {
                "model": model,
                "mape": result["mape"],
                "wape": result["wape"],
                "bias": result["bias"],
                "interval_coverage": result["interval_coverage"],
                "n_origins": result["n_origins"],
                "n_predictions": int(result["detail"]["n_predictions"].sum()) if not result["detail"].empty else 0,
                "skill_vs_naive": 0.0 if model == "seasonal_naive" else skill,
            }
        )
    return pd.DataFrame(rows)


def _series_or_block(con, spec, params, state_code: str, column: str):
    if state_code != "ALL" and state_code not in state_codes(con):
        return None, blocked(
            spec, params,
            f"{state_code} is not a state code in the registration extract. Telangana is not inferred from Andhra Pradesh.",
        )
    series = monthly_state(con, state_code, column).dropna()
    if len(series) < 36:
        return None, blocked(spec, params, "Fewer than 36 monthly observations, so the backtest is refused.")
    return series, None


def _backtest_result(spec, params, table: pd.DataFrame, subject: str, notes: tuple[str, ...]):
    if table.empty or int(table["n_origins"].max()) == 0:
        return blocked(spec, params, "No rolling origin produced a score.", notes=notes)
    naive = table.loc[table["model"] == "seasonal_naive"].iloc[0]
    contenders = table[table["model"] != "seasonal_naive"].dropna(subset=["mape"])
    if contenders.empty:
        champion = "seasonal_naive"
        beats = False
    else:
        best = contenders.loc[contenders["mape"].idxmin()]
        champion = str(best["model"])
        beats = bool(best["mape"] < naive["mape"])
    sarima_text = (
        "SARIMA is included."
        if params.get("include_sarima")
        else "SARIMA is off, so it is absent from the comparison rather than given a placeholder error."
    )
    naive_mape = float(naive["mape"])
    best_mape = float(table.loc[table["model"] == champion, "mape"].iloc[0])
    naive_text = f"{naive_mape:.1%}" if np.isfinite(naive_mape) else "not scored"
    return finish(
        spec, params, status="ok",
        metrics={
            "naive_mape": None if not np.isfinite(naive_mape) else naive_mape,
            "best_model": champion,
            "best_mape": None if not np.isfinite(best_mape) else best_mape,
            "beats_naive": beats,
            "n_origins": int(naive["n_origins"]),
        },
        checks=[check("naive_present", True, "The seasonal naive is the benchmark, not an optional extra.")],
        interpretation=(
            f"On {subject}, the seasonal naive MAPE is {naive_text} over {int(naive['n_origins'])} origins. "
            f"The lowest-error model in this run is {champion}, and it "
            f"{'beats' if beats else 'does not beat'} the naive on MAPE. {sarima_text} "
            "A loss to the naive is a result. It is not replaced with a more impressive model."
        ),
        frame=table,
        chart="bar", x="model", y="mape",
        notes=notes,
    )


@playground_experiment("F01")
def national_backtest(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, "ALL", "total_regs")
    if refusal:
        return refusal
    table = _score(series, int(params["horizon"]), int(params["n_origins"]), bool(params["include_sarima"]))
    return _backtest_result(spec, params, table, "All India monthly registrations", (ALL_INDIA,))


@playground_experiment("F02")
def ev_backtest(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, "ALL", "ev_regs")
    if refusal:
        return refusal
    table = _score(series, int(params["horizon"]), int(params["n_origins"]), bool(params["include_sarima"]))
    result = _backtest_result(spec, params, table, "All India monthly EV registrations", (ALL_INDIA,))
    if result.status != "ok":
        return result
    naive_mape = result.metrics["naive_mape"]
    readable = bool(np.isfinite(naive_mape) and naive_mape < 1)
    result.checks.append(
        check(
            "mape_readable",
            readable,
            "MAPE above 100% usually means early EV counts were near zero. Use WAPE in the table.",
        )
    )
    if not readable:
        result.interpretation += " MAPE is above 100% here, so WAPE in the table is the more stable error."
    return result


@playground_experiment("F03")
def state_backtest(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, str(params["state_code"]), "total_regs")
    if refusal:
        return refusal
    table = _score(series, int(params["horizon"]), int(params["n_origins"]), bool(params["include_sarima"]))
    return _backtest_result(
        spec, params, table, f"{params['state_code']} monthly registrations",
        ("This is one state series. It is not the national result.",),
    )


@playground_experiment("F04")
def skill_bar(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, "ALL", "total_regs")
    if refusal:
        return refusal
    table = _score(series, int(params["horizon"]), int(params["n_origins"]), bool(params["include_sarima"]))
    contenders = table[table["model"] != "seasonal_naive"].dropna(subset=["skill_vs_naive"])
    if contenders.empty:
        return blocked(spec, params, "No non-naive model produced a skill score.", notes=(ALL_INDIA,))
    best = contenders.loc[contenders["skill_vs_naive"].idxmax()]
    bar = float(params["minimum_skill"])
    return finish(
        spec, params, status="ok",
        metrics={"best_model": str(best["model"]), "skill": float(best["skill_vs_naive"]), "skill_bar": bar},
        checks=[check("skill_bar", bool(best["skill_vs_naive"] > bar), f"Bar is {bar:.2f}.")],
        interpretation=skill_sentence(str(best["model"]), float(best["skill_vs_naive"]), bar),
        frame=table, chart="bar", x="model", y="skill_vs_naive",
        notes=(ALL_INDIA,),
    )


@playground_experiment("F05")
def interval_coverage(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, "ALL", "total_regs")
    if refusal:
        return refusal
    result = backtest(series, "holt_winters", horizon=int(params["horizon"]), n_origins=int(params["n_origins"]))
    if not result["n_origins"]:
        return blocked(spec, params, "Holt-Winters produced no scored origins.", notes=(ALL_INDIA,))
    coverage = float(result["interval_coverage"])
    nominal = float(params["nominal_coverage"])
    n_predictions = int(result["detail"]["n_predictions"].sum())
    return finish(
        spec, params, status="ok",
        metrics={"coverage": coverage, "nominal": nominal, "n_predictions": n_predictions},
        checks=[check("coverage_measured", True, f"Coverage {coverage:.3f} versus nominal {nominal:.2f}.")],
        interpretation=coverage_sentence(coverage, nominal, n_predictions),
        frame=result["detail"],
        notes=(ALL_INDIA,),
    )


@playground_experiment("F06")
def signed_bias(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series, refusal = _series_or_block(con, spec, params, "ALL", "total_regs")
    if refusal:
        return refusal
    model = str(params["model"])
    if model not in FAST_MODELS:
        return blocked(spec, params, f"{model} is not in the bias check. Choose the seasonal naive or Holt-Winters.")
    result = backtest(series, model, horizon=int(params["horizon"]), n_origins=int(params["n_origins"]))
    if not result["n_origins"] or not np.isfinite(result["bias"]):
        return blocked(spec, params, f"{model} produced no bias.", notes=(ALL_INDIA,))
    return finish(
        spec, params, status="ok",
        metrics={"model": model, "bias": float(result["bias"]), "mape": float(result["mape"]), "n_origins": int(result["n_origins"])},
        checks=[check("bias_signed", True, "Bias is predicted minus actual and keeps its sign.")],
        interpretation=bias_sentence(model, float(result["bias"])),
        frame=result["detail"],
        notes=(ALL_INDIA,),
    )


@playground_experiment("F07")
def demand_shock(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series = monthly_state(con, "ALL", "total_regs").dropna()
    horizon = int(params["horizon"])
    shock = float(params["shock_pct"])
    if len(series) < 24:
        return blocked(spec, params, "Not enough history for a seasonal path.", notes=(ALL_INDIA,))
    baseline = seasonal_naive(series, horizon)
    scenario = baseline["mean"] * (1 + shock / 100)
    baseline_sum = float(baseline["mean"].sum())
    gap = float(scenario.sum() - baseline_sum)
    frame = pd.DataFrame(
        {
            "step": np.arange(1, horizon + 1),
            "seasonal_naive": baseline["mean"].to_numpy(),
            "scenario": scenario.to_numpy(),
        }
    )
    return finish(
        spec, params, status="ok",
        metrics={"shock_pct": shock, "baseline_registrations": baseline_sum, "scenario_gap": gap, "horizon": horizon},
        checks=[
            check(
                "labelled_simulation",
                abs(shock) < 1e-9 or abs(gap) > 0,
                "A non-zero shock must move the path. A zero shock must not invent a gap.",
            )
        ],
        interpretation=scenario_shock_sentence(shock, horizon, baseline_sum, gap),
        frame=frame, chart="line", x="step", y="scenario",
        notes=(ALL_INDIA, "The seasonal path includes the model's trailing drift. The shock is extra and assumed."),
    )


@playground_experiment("F08")
def imposed_ev_path(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["base_year"])
    months = national_month(con)
    observed = months[months["year"] == year]["month"].nunique()
    if observed < 12:
        return blocked(
            spec, params,
            f"{year} has {observed} months. An imposed path needs a complete base year and was not built on a partial year.",
            notes=(ALL_INDIA,),
        )
    annual = national_year(con)
    base = annual[annual["year"] == year]
    if base.empty:
        return blocked(spec, params, f"All India has no annual total in {year}.", notes=(ALL_INDIA,))
    total = float(base["total_regs"].iloc[0])
    observed_share = float(base["ev_share"].iloc[0])
    growth = float(params["annual_growth"])
    share = float(params["ev_share"])
    horizon = int(params["horizon_years"])
    rows = []
    for step in range(1, horizon + 1):
        future_total = total * (1 + growth) ** step
        rows.append(
            {
                "year": year + step,
                "imposed_total": future_total,
                "imposed_ev_regs": future_total * share,
                "imposed_ev_share": share,
            }
        )
    frame = pd.DataFrame(rows)
    distance = share - observed_share
    outside = abs(distance) > 0.20
    return finish(
        spec, params, status="ok",
        metrics={
            "base_total": total,
            "observed_ev_share": observed_share,
            "imposed_ev_share": share,
            "annual_growth": growth,
            "final_ev_regs": float(frame["imposed_ev_regs"].iloc[-1]),
        },
        checks=[
            check("complete_base_year", True, f"{year} has 12 months."),
            check(
                "share_near_history",
                not outside,
                f"Imposed share is {distance:+.1%} away from the {year} EV share.",
            ),
        ],
        interpretation=(
            f"Starting from the observed {year} total of {total:,.0f} (EV share {observed_share:.1%}), "
            f"this path applies growth of {growth:.1%} a year and holds the EV share at {share:.1%}. "
            f"In {int(frame['year'].iloc[-1])} the imposed EV count is {frame['imposed_ev_regs'].iloc[-1]:,.0f}. "
            + (
                "That share is more than 20 percentage points from the base year, so it is outside recent history. "
                if outside
                else "The share is within 20 percentage points of the base year. "
            )
            + "Growth and share were typed in. They were not fitted, and the path is not a forecast."
        ),
        frame=frame, chart="line", x="year", y="imposed_ev_regs",
        notes=(ALL_INDIA, "No price, supply constraint, or substitution is in this calculation."),
    )

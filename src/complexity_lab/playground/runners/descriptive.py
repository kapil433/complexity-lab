"""Descriptive experiments. Shares and ranks are derived from observed counts."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from complexity_lab.analysis.distributions import gini, zipf_exponent
from complexity_lab.data.public_macro import gdp_growth_for_year
from complexity_lab.playground.data import national_month, national_year, state_year
from complexity_lab.playground.interpret import zipf_sentence
from complexity_lab.playground.models import ExperimentSpec, check
from complexity_lab.playground.registry import playground_experiment
from complexity_lab.playground.runners.common import ALL_INDIA, POPULATION, blocked, finish

MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _window_ok(params: dict) -> str | None:
    if int(params.get("year_start", 0)) > int(params.get("year_end", 0)):
        return "The first year is after the last year."
    return None


@playground_experiment("D01")
def national_scale(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    through = int(params["through_month"])
    monthly = national_month(con)
    current = monthly[(monthly["year"] == year) & (monthly["month"] <= through)]
    prior = monthly[(monthly["year"] == year - 1) & (monthly["month"] <= through)]
    if current["month"].nunique() < through or prior["month"].nunique() < through:
        return blocked(
            spec,
            params,
            f"Month {through} is not present in both {year - 1} and {year}, so growth is not defined.",
            notes=(ALL_INDIA,),
        )
    current_sum = float(current["total_regs"].sum())
    prior_sum = float(prior["total_regs"].sum())
    growth = current_sum / prior_sum - 1 if prior_sum else np.nan
    gdp = gdp_growth_for_year(year)
    chart = pd.concat(
        [
            current.assign(series=str(year)),
            prior.assign(series=str(year - 1)),
        ],
        ignore_index=True,
    )
    gdp_sentence = (
        f"World Bank real GDP growth for calendar {year} is {gdp:.2f}% "
        "(national accounts, not a state driver and not a cause of this registration change)."
        if gdp is not None
        else (
            f"World Bank real GDP growth for calendar {year} is not in the local cache, "
            "so it was not joined and not filled from state GSDP."
        )
    )
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "registrations": current_sum,
            "prior_registrations": prior_sum,
            "matched_growth": float(growth),
            "through_month": through,
            "world_bank_real_gdp_growth_pct": gdp,
        },
        checks=[
            check("matched_months", True, f"Both years have months 1–{through}."),
            check(
                "gdp_not_imputed",
                True,
                "A missing national GDP figure stays missing.",
            ),
        ],
        interpretation=(
            f"All India registrations in months 1–{through} of {year} are {current_sum:,.0f}, "
            f"{growth:+.1%} versus the same months of {year - 1}. {gdp_sentence}"
        ),
        frame=chart[["month", "series", "total_regs"]],
        chart="line",
        x="month",
        y="total_regs",
        color="series",
        notes=(ALL_INDIA,),
    )


@playground_experiment("D02")
def fuel_mix(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    row = national_year(con)
    row = row[row["year"] == year]
    if row.empty or float(row["total_regs"].iloc[0]) <= 0:
        return blocked(spec, params, f"All India has no registrations in {year}.", notes=(ALL_INDIA,))
    item = row.iloc[0]
    fuels = [
        ("Petrol", item["petrol_regs"]),
        ("Diesel", item["diesel_regs"]),
        ("CNG", item["cng_regs"]),
        ("EV", item["ev_regs"]),
        ("Strong Hybrid", item["hybrid_regs"]),
    ]
    frame = pd.DataFrame(fuels, columns=["fuel", "registrations"])
    frame["share"] = frame["registrations"] / float(item["total_regs"])
    hybrid_note = (
        "Strong Hybrid is shown because it is in the source. Its share is not comparable with years before 2024."
        if year >= 2024
        else "Strong Hybrid is near zero before the 2024 classification break. Do not read that as absence of hybrid vehicles."
    )
    return finish(
        spec,
        params,
        status="ok",
        metrics={fuel: float(share) for fuel, share in frame[["fuel", "share"]].itertuples(index=False)},
        checks=[check("shares_sum", bool(np.isclose(frame["share"].sum(), 1.0)), "The five shares use the All India total.")],
        interpretation=(
            f"In {year}, All India registrations are {float(item['total_regs']):,.0f}. "
            + ", ".join(f"{name} {share:.1%}" for name, share in frame[["fuel", "share"]].itertuples(index=False))
            + f". {hybrid_note}"
        ),
        frame=frame,
        chart="bar",
        x="fuel",
        y="share",
        notes=(ALL_INDIA, hybrid_note),
    )


@playground_experiment("D03")
def concentration(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_ok(params)
    if problem:
        return blocked(spec, params, problem)
    frame = national_year(con)
    frame = frame[frame["year"].between(int(params["year_start"]), int(params["year_end"]))]
    frame = frame.dropna(subset=["hhi_oem", "entropy_oem"])
    if len(frame) < 3:
        return blocked(spec, params, "Fewer than three annual observations in the window.", notes=(ALL_INDIA,))
    first, last = frame.iloc[0], frame.iloc[-1]
    hhi_change = float(last["hhi_oem"] - first["hhi_oem"])
    entropy_change = float(last["entropy_oem"] - first["entropy_oem"])
    if hhi_change > 0 and entropy_change < 0:
        movement = (
            "HHI rose while entropy fell, so the national OEM share vector became more concentrated."
        )
    elif hhi_change < 0 and entropy_change > 0:
        movement = (
            "HHI fell while entropy rose, so the national OEM share vector became less concentrated."
        )
    elif hhi_change == 0 and entropy_change == 0:
        movement = "Neither HHI nor entropy moved between the window endpoints."
    else:
        movement = (
            "HHI and entropy did not move as opposite summaries of the same share vector. "
            "Treat that disagreement as a check on the window, not as a concentration story."
        )
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "hhi_start": float(first["hhi_oem"]),
            "hhi_end": float(last["hhi_oem"]),
            "entropy_start": float(first["entropy_oem"]),
            "entropy_end": float(last["entropy_oem"]),
            "hhi_change": hhi_change,
            "entropy_change": entropy_change,
        },
        checks=[check("window", True, f"{len(frame)} annual observations.")],
        interpretation=(
            f"From {int(first['year'])} to {int(last['year'])}, All India OEM HHI moves from "
            f"{first['hhi_oem']:.0f} to {last['hhi_oem']:.0f} and OEM entropy from "
            f"{first['entropy_oem']:.3f} to {last['entropy_oem']:.3f} nats. "
            f"{movement} The window chooses which change you see."
        ),
        frame=frame[["year", "hhi_oem", "entropy_oem"]],
        chart="line",
        x="year",
        y="hhi_oem",
        notes=(ALL_INDIA,),
    )


@playground_experiment("D04")
def rank_size(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    states = state_year(con, year, year)
    fit = zipf_exponent(states["total_regs"])
    if not np.isfinite(fit["slope"]):
        return blocked(spec, params, "Not enough positive state volumes to fit a rank-size slope.")
    ordered = states.sort_values("total_regs", ascending=False).reset_index(drop=True)
    ordered.insert(0, "rank", np.arange(1, len(ordered) + 1))
    return finish(
        spec,
        params,
        status="ok",
        metrics={"slope": fit["slope"], "r_squared": fit["r2"], "n_states": fit["n"], "tolerance": float(params["tolerance"])},
        checks=[check("fit", True, f"Slope {fit['slope']:.3f} on {fit['n']} states.")],
        interpretation=zipf_sentence(fit["slope"], fit["r2"], fit["n"], float(params["tolerance"])),
        frame=ordered[["rank", "state_name", "total_regs"]],
        chart="scatter",
        x="rank",
        y="total_regs",
    )


@playground_experiment("D05")
def volume_gini(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    states = state_year(con, year, year)
    value = gini(states["total_regs"])
    if not np.isfinite(value):
        return blocked(spec, params, f"No positive state volumes in {year}.")
    frame = states.sort_values("total_regs", ascending=False)[["state_name", "total_regs"]]
    return finish(
        spec,
        params,
        status="ok",
        metrics={"gini": float(value), "n_states": int(len(states))},
        checks=[check("gini", True, f"Gini {value:.3f}.")],
        interpretation=(
            f"The Gini coefficient of state registration volumes in {year} is {value:.3f} "
            f"across {len(states)} states. Zero would mean equal volumes. One would mean one state "
            "has all the registrations. This uses counts, not population and not income."
        ),
        frame=frame.head(15),
        chart="bar",
        x="state_name",
        y="total_regs",
    )


@playground_experiment("D06")
def seasonality(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    monthly = national_month(con)
    counts = monthly.groupby("year")["month"].nunique()
    complete_years = set(counts[counts == 12].index)
    sample = monthly[monthly["year"].isin(complete_years)]
    if sample.empty:
        return blocked(spec, params, "No complete calendar year is available.", notes=(ALL_INDIA,))
    profile = sample.groupby("month", as_index=False)["total_regs"].mean()
    profile["index"] = profile["total_regs"] / profile["total_regs"].mean()
    profile["month_name"] = profile["month"].map(lambda value: MONTHS[int(value)])
    month = int(params["month"])
    chosen = profile.loc[profile["month"] == month].iloc[0]
    direction = "above" if chosen["index"] > 1 else "below" if chosen["index"] < 1 else "at"
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "month": month,
            "seasonal_index": float(chosen["index"]),
            "complete_years": int(len(complete_years)),
        },
        checks=[check("complete_years", True, f"Index uses {len(complete_years)} complete years.")],
        interpretation=(
            f"{MONTHS[month]} averages {chosen['index']:.2f} times a typical month "
            f"({direction} the mean) across {len(complete_years)} complete years. "
            "March often reflects the financial-year end, and October–November the festive season. "
            "The index describes the calendar. Changing the month changes which part of that calendar you read."
        ),
        frame=profile,
        chart="bar",
        x="month_name",
        y="index",
        notes=(ALL_INDIA,),
    )


@playground_experiment("D07")
def ev_distribution(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    states = state_year(con, year, year).dropna(subset=["ev_share"])
    kept = states[states["total_regs"] >= int(params["min_regs"])]
    if len(kept) < 5:
        return blocked(spec, params, "Fewer than five states meet the volume floor.")
    share = kept["ev_share"]
    top = kept.loc[share.idxmax()]
    bottom = kept.loc[share.idxmin()]
    excluded = int(len(states) - len(kept))
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "n_states": int(len(kept)),
            "excluded_states": excluded,
            "mean_ev_share": float(share.mean()),
            "median_ev_share": float(share.median()),
            "p10_ev_share": float(share.quantile(0.10)),
            "p90_ev_share": float(share.quantile(0.90)),
        },
        checks=[check("sample", True, f"{len(kept)} states kept, {excluded} excluded by the volume floor.")],
        interpretation=(
            f"In {year}, among {len(kept)} states with at least {int(params['min_regs']):,} registrations, "
            f"the median EV share is {share.median():.1%} and the mean is {share.mean():.1%}. "
            f"{top['state_name']} is highest at {top['ev_share']:.1%}; "
            f"{bottom['state_name']} is lowest at {bottom['ev_share']:.1%}. "
            f"The volume floor excludes {excluded} states. Raising it can change who sits at the top. "
            "Dispersion is not a ranking of policy success."
        ),
        frame=kept.sort_values("ev_share", ascending=False)[["state_name", "ev_share", "total_regs"]],
        chart="bar",
        x="state_name",
        y="ev_share",
    )


@playground_experiment("D08")
def growth_normality(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    states = state_year(con, year, year).dropna(subset=["yoy_growth"])
    values = states["yoy_growth"].to_numpy(dtype=float)
    if len(values) < 8:
        return blocked(spec, params, "Fewer than eight states have a growth rate.")
    statistic, p_value = stats.shapiro(values)
    alpha = float(params["alpha"])
    rejects = bool(p_value < alpha)
    decision = "rejects" if rejects else "does not reject"
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "n_states": int(len(values)),
            "shapiro_w": float(statistic),
            "p_value": float(p_value),
            "alpha": alpha,
            "mean_growth": float(np.mean(values)),
            "skewness": float(stats.skew(values)),
        },
        checks=[check("normality_null", not rejects, f"Shapiro-Wilk p={p_value:.4f} at alpha {alpha:.2f}.")],
        interpretation=(
            f"Across {len(values)} states in {year}, Shapiro-Wilk W is {statistic:.3f} and p is {p_value:.4f}. "
            f"At alpha {alpha:.2f}, the test {decision} normality of registration growth. "
            "A rejection means normal-errors language is a poor description of this cross-section. "
            "It is not a finding about why states grew. A stricter alpha can reverse the decision."
        ),
        frame=states.sort_values("yoy_growth")[["state_name", "yoy_growth"]],
        chart="bar",
        x="state_name",
        y="yoy_growth",
    )


@playground_experiment("D09")
def diesel_windows(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    early = range(int(params["early_start"]), int(params["early_end"]) + 1)
    late = range(int(params["late_start"]), int(params["late_end"]) + 1)
    if not early or not late:
        return blocked(spec, params, "A window runs backwards.")
    if set(early) & set(late):
        return blocked(spec, params, "The early and late windows overlap, so the comparison is refused.")
    annual = national_year(con)
    early_share = annual.loc[annual["year"].isin(early), "diesel_share"].dropna()
    late_share = annual.loc[annual["year"].isin(late), "diesel_share"].dropna()
    if early_share.empty or late_share.empty:
        return blocked(spec, params, "One of the windows has no diesel share.", notes=(ALL_INDIA,))
    change_pp = (float(late_share.mean()) - float(early_share.mean())) * 100
    frame = pd.DataFrame(
        {
            "window": ["Early", "Late"],
            "mean_diesel_share": [float(early_share.mean()), float(late_share.mean())],
        }
    )
    direction = "lower" if change_pp < 0 else "higher" if change_pp > 0 else "unchanged"
    return finish(
        spec,
        params,
        status="ok",
        metrics={
            "early_mean_share": float(early_share.mean()),
            "late_mean_share": float(late_share.mean()),
            "change_pp": change_pp,
        },
        checks=[check("windows_disjoint", True, "The two year windows do not overlap.")],
        interpretation=(
            f"Mean All India diesel share is {early_share.mean():.1%} in "
            f"{int(params['early_start'])}–{int(params['early_end'])} and {late_share.mean():.1%} in "
            f"{int(params['late_start'])}–{int(params['late_end'])}, {change_pp:+.1f} percentage points "
            f"({direction} later). Moving either window changes the comparison. "
            "This is not the April 2020 break and it is not a named policy effect."
        ),
        frame=frame,
        chart="bar",
        x="window",
        y="mean_diesel_share",
        notes=(ALL_INDIA,),
    )


@playground_experiment("D10")
def per_capita_rank(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    states = state_year(con, year, year).dropna(subset=["total_regs", "regs_per_1000_population"])
    states = states[states["regs_per_1000_population"] > 0]
    if len(states) < 8:
        return blocked(spec, params, "Fewer than eight states have both a volume and a population denominator.")
    rho, p_value = stats.spearmanr(states["total_regs"], states["regs_per_1000_population"])
    bar = float(params["agreement_bar"])
    similar = bool(rho > bar)
    verdict = (
        f"above the agreement bar of {bar:.2f}, so the two rankings are treated as similar"
        if similar
        else f"at or below the agreement bar of {bar:.2f}, so scaling by estimated population reorders the states"
    )
    return finish(
        spec,
        params,
        status="ok",
        metrics={"spearman_rho": float(rho), "p_value": float(p_value), "n_states": int(len(states)), "agreement_bar": bar},
        checks=[check("ranks_compared", True, f"Spearman rho {rho:.3f}.")],
        interpretation=(
            f"In {year}, Spearman agreement between raw registration rank and registrations per 1,000 "
            f"estimated people is {rho:.2f} on {len(states)} states, {verdict}. "
            "The denominator is an estimate. Changing the bar changes the words, not the registrations."
        ),
        frame=states[["state_name", "total_regs", "regs_per_1000_population", "population_quality"]],
        chart="scatter",
        x="total_regs",
        y="regs_per_1000_population",
        notes=(POPULATION,),
    )

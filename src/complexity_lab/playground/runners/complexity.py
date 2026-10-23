"""Complexity experiments. Thresholds and seeds are part of the result, not hidden settings."""

from __future__ import annotations

import duckdb
import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

from complexity_lab.complexity.dynamics import early_warning_signals, kendall_tau_trend
from complexity_lab.complexity.entropy import complexity_indices, fuel_mix_entropy, rca_matrix
from complexity_lab.complexity.transitions import (
    absorbing_regimes,
    classify_regimes,
    critical_threshold,
    percolation_curve,
    regime_transition_matrix,
    threshold_scan,
)
from complexity_lab.networks.metrics import communities
from complexity_lab.playground.data import (
    adjacency,
    national_month,
    national_year,
    oem_edges,
    state_year,
)
from complexity_lab.playground.interpret import absorption_sentence, association_sentence
from complexity_lab.playground.models import ExperimentSpec, check
from complexity_lab.playground.registry import playground_experiment
from complexity_lab.playground.runners.common import ALL_INDIA, INCOME, blocked, finish


def _window_problem(params: dict) -> str | None:
    if int(params["year_start"]) > int(params["year_end"]):
        return "The first year is after the last year."
    return None


def _morans_i(values: pd.Series, edges: pd.DataFrame) -> tuple[float, list[str]]:
    nodes = [node for node in values.index if pd.notna(values.loc[node])]
    index = {code: position for position, code in enumerate(nodes)}
    weights = np.zeros((len(nodes), len(nodes)))
    for state_a, state_b in edges.itertuples(index=False):
        if state_a in index and state_b in index:
            weights[index[state_a], index[state_b]] = 1
            weights[index[state_b], index[state_a]] = 1
    connected = weights.sum(axis=1) > 0
    kept = [node for node, flag in zip(nodes, connected, strict=True) if flag]
    weights = weights[np.ix_(connected, connected)]
    row_sum = weights.sum(axis=1, keepdims=True)
    weights = np.divide(weights, row_sum, out=np.zeros_like(weights), where=row_sum > 0)
    y = values.loc[kept].to_numpy(dtype=float)
    z = y - y.mean()
    denominator = float(z @ z)
    if denominator == 0 or not kept:
        return np.nan, kept
    return float(z @ weights @ z / denominator), kept


@playground_experiment("C01")
def fuel_entropy(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    frame = national_year(con)
    frame = frame[frame["year"].between(int(params["year_start"]), int(params["year_end"]))].copy()
    if len(frame) < 3:
        return blocked(spec, params, "Fewer than three annual fuel mixes in the window.", notes=(ALL_INDIA,))
    frame["fuel_entropy"] = fuel_mix_entropy(frame).to_numpy()
    change = float(frame["fuel_entropy"].iloc[-1] - frame["fuel_entropy"].iloc[0])
    direction = "rose" if change > 0.01 else "fell" if change < -0.01 else "barely changed"
    includes_break = bool((frame["year"] >= 2024).any())
    return finish(
        spec, params, status="ok",
        metrics={
            "entropy_start": float(frame["fuel_entropy"].iloc[0]),
            "entropy_end": float(frame["fuel_entropy"].iloc[-1]),
            "change": change,
        },
        checks=[
            check(
                "hybrid_break_excluded",
                not includes_break,
                "The window includes 2024 or later, so the hybrid classification break can lift entropy."
                if includes_break
                else "The window ends before the 2024 hybrid classification break.",
            )
        ],
        interpretation=(
            f"All India fuel-mix entropy {direction} by {change:+.3f} nats, from "
            f"{frame['fuel_entropy'].iloc[0]:.3f} in {int(frame['year'].iloc[0])} to "
            f"{frame['fuel_entropy'].iloc[-1]:.3f} in {int(frame['year'].iloc[-1])}. "
            "Higher entropy means the fuel counts are less concentrated. It is not a welfare score. "
            "A window that crosses 2024 mixes a real fuel shift with the hybrid reporting break."
        ),
        frame=frame[["year", "fuel_entropy"]],
        chart="line", x="year", y="fuel_entropy",
        notes=(ALL_INDIA,),
    )


def _complexity_frame(con: duckdb.DuckDBPyConnection, year: int, threshold: float) -> pd.DataFrame | None:
    edges = oem_edges(con, year)
    if edges.empty:
        return None
    rca = rca_matrix(edges)
    indices = complexity_indices(rca, threshold=threshold)
    complexity = indices["state_complexity"].rename("complexity").reset_index()
    if "state_code" not in complexity.columns:
        complexity = complexity.rename(columns={complexity.columns[0]: "state_code"})
    names = state_year(con, year, year)[["state_code", "state_name", "real_pc_income_inr"]]
    return complexity.merge(names, on="state_code", how="left")


@playground_experiment("C02")
def state_complexity(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = _complexity_frame(con, int(params["year"]), float(params["rca_threshold"]))
    if frame is None or frame["complexity"].notna().sum() < 5:
        return blocked(
            spec, params,
            "The RCA threshold leaves too few state-OEM links to compute a complexity index.",
        )
    ordered = frame.dropna(subset=["complexity"]).sort_values("complexity", ascending=False)
    top = ordered.iloc[0]
    bottom = ordered.iloc[-1]
    return finish(
        spec, params, status="ok",
        metrics={
            "n_states": int(len(ordered)),
            "rca_threshold": float(params["rca_threshold"]),
            "highest_state": str(top["state_name"]),
            "lowest_state": str(bottom["state_name"]),
        },
        checks=[check("index_computed", True, f"{len(ordered)} states received an index.")],
        interpretation=(
            f"At an RCA threshold of {float(params['rca_threshold']):.1f} in {int(params['year'])}, "
            f"{top['state_name']} has the highest portfolio complexity and {bottom['state_name']} the lowest, "
            f"among {len(ordered)} states. Raising the threshold drops weaker OEM links and can reorder the list. "
            "The index describes the shape of the car market. It is not a development ranking."
        ),
        frame=ordered[["state_name", "complexity"]],
        chart="bar", x="state_name", y="complexity",
    )


@playground_experiment("C03")
def complexity_income(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = _complexity_frame(con, int(params["year"]), float(params["rca_threshold"]))
    if frame is None:
        return blocked(spec, params, "The complexity index could not be built at this threshold.", notes=(INCOME,))
    usable = frame.dropna(subset=["complexity", "real_pc_income_inr"])
    if len(usable) < 8 or usable["complexity"].nunique() < 2:
        return blocked(spec, params, "Not enough states have both complexity and real income.", notes=(INCOME,))
    rho, p_value = stats.spearmanr(usable["complexity"], usable["real_pc_income_inr"])
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": float(rho), "p_value": float(p_value), "n_states": int(len(usable))},
        checks=[check("threshold_disclosed", True, f"RCA threshold {float(params['rca_threshold']):.1f}.")],
        interpretation=association_sentence(
            "state complexity", "real per-capita income", float(rho), float(p_value),
            float(params["alpha"]), int(len(usable)),
            f"The index uses RCA threshold {float(params['rca_threshold']):.1f}. A different threshold is a different index.",
        ),
        frame=usable[["state_name", "complexity", "real_pc_income_inr"]],
        chart="scatter", x="complexity", y="real_pc_income_inr",
        notes=(INCOME,),
    )


@playground_experiment("C04")
def percolation(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    edges = oem_edges(con, int(params["year"]))
    if edges.empty:
        return blocked(spec, params, f"No OEM-state edges in {int(params['year'])}.")
    curve = percolation_curve(edges)
    tau = critical_threshold(curve)
    if not np.isfinite(tau):
        return blocked(spec, params, "The giant-component curve has no steepest drop.")
    return finish(
        spec, params, status="ok",
        metrics={"critical_share": float(tau), "year": int(params["year"])},
        checks=[check("curve", True, f"Steepest drop at share {tau:.3f}.")],
        interpretation=(
            f"In {int(params['year'])}, the steepest drop in the OEM-state giant component is at an "
            f"OEM share of {tau:.1%}. That is a description of this snapshot. Another year can move it. "
            "It is not a minimum viable share for a product launch."
        ),
        frame=curve, chart="line", x="threshold", y="giant_frac",
    )


@playground_experiment("C05")
def modularity(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    edges = oem_edges(con, int(params["year"]))
    if edges.empty:
        return blocked(spec, params, "No OEM-state edges in the chosen year.")
    edges = edges.copy()
    edges["share"] = edges["regs"] / edges.groupby("state_code")["regs"].transform("sum")
    kept = edges[edges["share"] >= float(params["min_share"])]
    graph = nx.Graph()
    for row in kept.itertuples(index=False):
        graph.add_node(row.maker, kind="oem")
        graph.add_node(row.state_code, kind="state")
        graph.add_edge(row.maker, row.state_code, weight=float(row.share))
    if graph.number_of_edges() < 5:
        return blocked(
            spec, params,
            f"Only {graph.number_of_edges()} edges survive a minimum share of {float(params['min_share']):.3f}.",
        )
    membership = communities(graph, seed=int(params["seed"]))
    score = float(membership.attrs["modularity"])
    n_communities = int(membership.attrs["n_communities"])
    summary = (
        membership.reset_index()
        .groupby("community")
        .size()
        .rename("members")
        .reset_index()
    )
    return finish(
        spec, params, status="ok",
        metrics={
            "modularity": score,
            "n_communities": n_communities,
            "n_edges": int(graph.number_of_edges()),
            "min_share": float(params["min_share"]),
            "seed": int(params["seed"]),
        },
        checks=[check("seed_fixed", True, f"Louvain seed {int(params['seed'])}.")],
        interpretation=(
            f"At a minimum OEM share of {float(params['min_share']):.3f} in {int(params['year'])}, "
            f"Louvain modularity is {score:.3f} with {n_communities} communities "
            f"({graph.number_of_edges()} edges, seed {int(params['seed'])}). "
            "A higher share threshold deletes edges before the partition, so the score can rise or fall. "
            "Modularity is a partition score, not a recommended sales territory."
        ),
        frame=summary, chart="bar", x="community", y="members",
    )


@playground_experiment("C06")
def spatial_ev(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    year = int(params["year"])
    values = state_year(con, year, year).dropna(subset=["ev_share"]).set_index("state_code")["ev_share"]
    edges = adjacency(con)
    observed, kept = _morans_i(values, edges)
    if not np.isfinite(observed) or len(kept) < 8:
        return blocked(spec, params, "Too few bordered states have an EV share.")
    generator = np.random.default_rng(int(params["seed"]))
    perms = int(params["n_permutations"])
    null = np.empty(perms)
    base = values.loc[kept].to_numpy()
    for draw in range(perms):
        shuffled = values.copy()
        shuffled.loc[kept] = generator.permutation(base)
        null[draw], _ = _morans_i(shuffled, edges)
    exceedances = int(np.sum(np.abs(null) >= abs(observed)))
    p_value = (exceedances + 1) / (perms + 1)
    alpha = float(params["alpha"])
    decision = "rejects" if p_value < alpha else "does not reject"
    return finish(
        spec, params, status="ok",
        metrics={
            "morans_i": float(observed),
            "p_value": float(p_value),
            "n_states": len(kept),
            "n_permutations": perms,
        },
        checks=[check("permutation_null", True, f"{perms} relabellings, seed {int(params['seed'])}.")],
        interpretation=(
            f"Moran's I for {year} EV shares on the land-border graph is {observed:.3f} "
            f"across {len(kept)} states with a neighbour. The permutation p-value is {p_value:.3f} "
            f"({perms} draws, seed {int(params['seed'])}). At alpha {alpha:.2f}, the test {decision} "
            "the null of no spatial synchrony. A positive value means neighbours look more alike than "
            "a shuffle. It does not mean one state caused the other's registrations. "
            "Islands without a land border are left out."
        ),
        notes=("Telangana is in the border file but not in Vahan, so it is not a node in this test.",),
    )


@playground_experiment("C07")
def diesel_warning(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    series = national_month(con).set_index("date")["diesel_share"].astype(float)
    window = int(params["window"])
    signals = early_warning_signals(series, window=window)
    trend = kendall_tau_trend(signals["variance"])
    if not np.isfinite(trend["tau"]):
        return blocked(spec, params, "The variance series is too short for Kendall's tau.", notes=(ALL_INDIA,))
    alpha = float(params["alpha"])
    rising = bool(trend["tau"] > 0 and trend["pvalue"] < alpha)
    decision = "supports" if rising else "does not support"
    frame = signals.reset_index()
    return finish(
        spec, params, status="ok",
        metrics={"kendall_tau": trend["tau"], "p_value": trend["pvalue"], "n": trend["n"], "window": window},
        checks=[check("early_warning", rising, f"tau={trend['tau']:.3f}, p={trend['pvalue']:.4f}.")],
        interpretation=(
            f"With a {window}-month window, Kendall's tau of diesel-share variance against time is "
            f"{trend['tau']:.3f} (p={trend['pvalue']:.4f}, n={trend['n']}). At alpha {alpha:.2f}, this "
            f"{decision} a rising-variance early warning. A shorter or longer window rebuilds the variance "
            "series. Rising variance is a diagnostic. It does not date a regime shift."
        ),
        frame=frame[["date", "variance"]],
        chart="line", x="date", y="variance",
        notes=(ALL_INDIA,),
    )


@playground_experiment("C08")
def absorbing(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    panel = state_year(con, int(params["year_start"]), int(params["year_end"]))
    if panel["state_code"].nunique() < 5 or panel["year"].nunique() < 3:
        return blocked(spec, params, "The window is too short for a transition matrix.")
    regimes = classify_regimes(panel)
    matrix = regime_transition_matrix(regimes)
    names = absorbing_regimes(matrix, threshold=float(params["threshold"]))
    shown = matrix.reset_index().rename(columns={"regime": "from_regime"})
    return finish(
        spec, params, status="ok",
        metrics={"n_absorbing": len(names), "threshold": float(params["threshold"]), "absorbing": ", ".join(names)},
        checks=[check("rules_fixed", True, "Regime rules stay at EV 5%, CNG 15%, and entropy 1 nat.")],
        interpretation=absorption_sentence(float(params["threshold"]), names)
        + (
            " This window includes 2024, so the strong-hybrid classification break can change fuel entropy and the regime label."
            if int(params["year_end"]) >= 2024
            else ""
        ),
        frame=shown,
        notes=("The self-transition bar is a choice. Lowering it reclassifies stickiness.",),
    )


@playground_experiment("C09")
def ev_hinge(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    annual = national_year(con)
    annual = annual[annual["year"] <= 2025].sort_values("year")
    share = annual.set_index("year")["ev_share"].astype(float)
    result = threshold_scan(share, min_side=int(params["min_side"]))
    gain = result.get("sse_gain", np.nan)
    hinge = result.get("hinge_coef", np.nan)
    if not np.isfinite(gain):
        return blocked(
            spec, params,
            "The annual EV series is too short for a hinge with this minimum number of years on each side. "
            "No hinge was invented.",
            notes=(ALL_INDIA,),
        )
    material = float(params["material_gain"])
    steeper = bool(np.isfinite(hinge) and hinge > 0)
    gain_clears = bool(gain >= material)
    accelerates = steeper and gain_clears
    hinge_text = f"{hinge:.3f}" if np.isfinite(hinge) else "not estimated"
    if accelerates:
        claim = (
            f"The hinge coefficient is {hinge_text}. The SSE gain is {gain:.1%}, "
            f"which clears the {material:.0%} bar, and the slope is steeper above the hinge."
        )
    elif not steeper:
        claim = (
            f"The hinge coefficient is {hinge_text}, so the slope is not steeper above the hinge. "
            f"The SSE gain is {gain:.1%} against a material-gain bar of {material:.0%}. "
            "A better in-sample fit is not an acceleration."
        )
    else:
        claim = (
            f"The hinge coefficient is {hinge_text}, but the SSE gain is {gain:.1%}, "
            f"below the material-gain bar of {material:.0%}. "
            "The hinge is not treated as an acceleration."
        )
    return finish(
        spec, params, status="ok",
        metrics={
            "tau": result.get("tau"),
            "hinge_coef": hinge if np.isfinite(hinge) else None,
            "sse_gain": float(gain),
            "n": result.get("n"),
            "material_gain": material,
        },
        checks=[check("material_hinge", accelerates, claim)],
        interpretation=(
            f"On {int(result.get('n', 0))} annual changes, the scan places a hinge at EV share "
            f"{result.get('tau'):.1%}. {claim} "
            "About a dozen annual points sit behind this fit. Raising the gain bar can withdraw the claim. "
            "The hinge is not a tipping point caused by chargers or subsidies."
        ),
        frame=annual[["year", "ev_share"]],
        chart="line", x="year", y="ev_share",
        notes=(ALL_INDIA, "Partial 2026 is excluded from this annual scan."),
    )


@playground_experiment("C10")
def hhi_entropy_sign(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    problem = _window_problem(params)
    if problem:
        return blocked(spec, params, problem)
    frame = national_year(con)
    frame = frame[frame["year"].between(int(params["year_start"]), int(params["year_end"]))]
    frame = frame.dropna(subset=["hhi_oem", "entropy_oem"])
    if len(frame) < 5:
        return blocked(spec, params, "Fewer than five years have both HHI and entropy.", notes=(ALL_INDIA,))
    rho, p_value = stats.spearmanr(frame["hhi_oem"], frame["entropy_oem"])
    passed = bool(rho < 0)
    return finish(
        spec, params, status="ok",
        metrics={"spearman_rho": float(rho), "p_value": float(p_value), "n_years": int(len(frame))},
        checks=[check("opposite_directions", passed, f"Spearman rho is {rho:.3f}.")],
        interpretation=(
            f"Across {len(frame)} All India years, Spearman rho between OEM HHI and OEM entropy is {rho:.2f}. "
            + (
                "The negative sign is what two summaries of the same share vector should do."
                if passed
                else "The sign is not negative. That is a system alarm: the two concentration measures disagree, and the disagreement is reported rather than averaged away."
            )
        ),
        frame=frame[["year", "hhi_oem", "entropy_oem"]],
        chart="line", x="year", y="hhi_oem",
        notes=(ALL_INDIA,),
    )

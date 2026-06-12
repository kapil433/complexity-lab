"""Built-in experiments — also the canonical examples for writing new ones."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from complexity_lab.analysis import descriptive, distributions
from complexity_lab.experiments.registry import experiment
from complexity_lab.networks import build as nb
from complexity_lab.networks import metrics as nm
from complexity_lab.simulation.diffusion import fit_bass_by_state


@experiment(
    "descriptive-baseline",
    description="Market size, growth, fuel mix, seasonality and OEM concentration — the baseline every other experiment builds on.",
)
def descriptive_baseline(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    year_panel = con.execute("SELECT * FROM panel_state_year").df()
    month_panel = con.execute(
        "SELECT * FROM panel_state_month WHERE state_code = 'ALL' ORDER BY year, month"
    ).df()

    summary = descriptive.summary_table(year_panel[year_panel["state_code"] != "ALL"])
    summary.to_parquet(out_dir / "state_summary.parquet")

    seasonality = descriptive.seasonality_profile(
        month_panel[month_panel["year"].between(2013, 2025)]
    )
    seasonality.to_parquet(out_dir / "seasonality_all_india.parquet")

    edges = con.execute("SELECT * FROM oem_state_edges").df()
    conc = descriptive.concentration_series(edges, "year", "maker")
    conc.to_parquet(out_dir / "oem_concentration_by_year.parquet")

    latest = year_panel[(year_panel["state_code"] != "ALL")]
    latest_year = int(latest["year"].max()) - 1
    sizes = latest[latest["year"] == latest_year].set_index("state_code")["total_regs"]
    zipf = distributions.zipf_exponent(sizes)
    gini = distributions.gini(sizes)

    return {
        "latest_full_year": latest_year,
        "state_gini": round(gini, 4),
        "zipf_slope": round(zipf["slope"], 4),
        "zipf_r2": round(zipf["r2"], 4),
        "hhi_latest": round(float(conc["hhi"].iloc[-2]), 1),
    }


@experiment(
    "ev-diffusion-states",
    description="Bass diffusion fits of EV adoption per state; parameters vs income/infrastructure covariates.",
)
def ev_diffusion_states(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    month_panel = con.execute(
        "SELECT * FROM panel_state_month WHERE state_code <> 'ALL' ORDER BY state_code, year, month"
    ).df()
    fits = fit_bass_by_state(month_panel, value_col="ev_regs", min_total=params.get("min_total", 1000))
    fits.to_parquet(out_dir / "bass_fits_by_state.parquet")

    year_panel = con.execute(
        "SELECT state_code, year, pc_income_inr, ev_chargers, urban_pct "
        "FROM panel_state_year WHERE state_code <> 'ALL'"
    ).df()
    latest_cov = (
        year_panel.dropna(subset=["pc_income_inr"])
        .sort_values("year")
        .groupby("state_code")
        .tail(1)
        .set_index("state_code")
    )
    joined = fits.join(latest_cov, how="left")
    joined.to_parquet(out_dir / "bass_fits_with_covariates.parquet")

    ok = joined.dropna(subset=["q", "pc_income_inr"])
    corr_q_income = float(ok["q"].corr(ok["pc_income_inr"], method="spearman")) if len(ok) > 4 else None
    return {
        "n_states_fit": int(fits["q"].notna().sum()),
        "median_p": round(float(fits["p"].median()), 5),
        "median_q": round(float(fits["q"].median()), 4),
        "spearman_q_vs_income": round(corr_q_income, 3) if corr_q_income is not None else None,
    }


@experiment(
    "phase-transitions",
    description="Percolation transition of the OEM-state network and Markov dynamics of state fuel regimes.",
)
def phase_transitions(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.complexity import transitions as tr

    edges = con.execute("SELECT * FROM oem_state_edges").df()
    latest_year = int(edges["year"].max()) - 1

    curve = tr.percolation_curve(edges[edges["year"] == latest_year])
    curve.to_parquet(out_dir / "percolation_curve.parquet")
    tau_c = tr.critical_threshold(curve)

    # percolation point per year — has the market's cohesion scale moved?
    tau_by_year = {
        int(y): tr.critical_threshold(tr.percolation_curve(g))
        for y, g in edges.groupby("year")
        if int(y) <= latest_year
    }
    pd.Series(tau_by_year, name="tau_c").rename_axis("year").to_frame().to_parquet(
        out_dir / "critical_threshold_by_year.parquet"
    )

    panel_year = con.execute(
        "SELECT * FROM panel_state_year WHERE state_code <> 'ALL'"
    ).df()
    regimes = tr.classify_regimes(panel_year[panel_year["year"] <= latest_year])
    regimes.to_parquet(out_dir / "fuel_regimes.parquet")
    matrix = tr.regime_transition_matrix(regimes)
    matrix.to_parquet(out_dir / "regime_transition_matrix.parquet")
    absorbing = tr.absorbing_regimes(matrix, threshold=params.get("absorbing_threshold", 0.9))

    return {
        "latest_year": latest_year,
        "critical_threshold": round(tau_c, 4),
        "absorbing_regimes": absorbing,
        "n_ev_emerging_states": int((regimes[regimes["year"] == latest_year]["regime"] == "ev_emerging").sum()),
    }


@experiment(
    "ev-threshold",
    description="EV tipping-point scan: piecewise threshold regression of adoption growth per state.",
)
def ev_threshold(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.complexity.transitions import tipping_summary

    month_panel = con.execute(
        "SELECT state_code, year, month, ev_share FROM panel_state_month "
        "WHERE state_code <> 'ALL' ORDER BY state_code, year, month"
    ).df()
    min_share = params.get("min_share", 0.01)

    # Full series vs subsidy era (FAME-II ran until March 2024): comparing the
    # two scans separates genuine tipping from the post-subsidy plateau.
    tips = tipping_summary(month_panel, "ev_share", min_share_reached=min_share)
    tips.to_parquet(out_dir / "ev_tipping_by_state.parquet")
    policy_era = month_panel[
        (month_panel["year"] < 2024) | ((month_panel["year"] == 2024) & (month_panel["month"] <= 3))
    ]
    tips_policy = tipping_summary(policy_era, "ev_share", min_share_reached=min_share)
    tips_policy.to_parquet(out_dir / "ev_tipping_policy_era.parquet")

    cov = con.execute(
        "SELECT state_code, MAX(pc_income_inr) pc_income_inr, MAX(ev_chargers) ev_chargers "
        "FROM panel_state_year WHERE state_code <> 'ALL' GROUP BY state_code"
    ).df().set_index("state_code")
    joined = tips.join(cov, how="left")
    joined.to_parquet(out_dir / "ev_tipping_with_covariates.parquet")

    accelerating = tips_policy[(tips_policy["hinge_coef"] > 0) & (tips_policy["sse_gain"] > 0.1)]
    return {
        "n_states_scanned": len(tips),
        "full_series": {
            "n_accelerating": int(((tips["hinge_coef"] > 0) & (tips["sse_gain"] > 0.1)).sum()),
            "n_saturating": int((tips["hinge_coef"] < 0).sum()),
        },
        "policy_era_to_2024_03": {
            "n_accelerating": len(accelerating),
            "n_saturating": int((tips_policy["hinge_coef"] < 0).sum()),
            "median_tau_accelerating": round(float(accelerating["tau"].median()), 4)
            if len(accelerating)
            else None,
        },
    }


@experiment(
    "wholesale-retail-nowcast",
    description="Wholesale dispatches vs retail registrations: lead/lag structure, channel-inventory ratio, and an out-of-sample nowcast of registrations.",
)
def wholesale_retail_nowcast(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.analysis.nowcast import cross_correlation, nowcast_eval

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "wholesale" not in tables:
        raise RuntimeError("wholesale table missing — run `uv run lab wholesale` first")

    rw = con.execute("SELECT * FROM retail_wholesale_month ORDER BY date").df()
    rw.to_parquet(out_dir / "retail_wholesale_month.parquet")

    xc = cross_correlation(rw.set_index("date")["retail"], rw.set_index("date")["wholesale"])
    xc.to_parquet(out_dir / "cross_correlation.parquet")

    res = nowcast_eval(rw, test_months=params.get("test_months", 12))
    res["predictions"].to_parquet(out_dir / "nowcast_oos_predictions.parquet")

    seg = con.execute(
        "SELECT segment5, year, SUM(wholesale) AS units FROM ws_segment_month "
        "WHERE year >= 2022 GROUP BY segment5, year ORDER BY year, units DESC"
    ).df()
    seg.to_parquet(out_dir / "segment_mix_by_year.parquet")

    best_lead = int(xc["corr"].idxmax())
    return {
        "months_joined": len(rw),
        "mean_ws_retail_ratio": round(float(rw["ws_retail_ratio"].mean()), 3),
        "best_corr_lag": best_lead,
        "best_corr": round(float(xc["corr"].max()), 3),
        "mape_nowcast": round(res["mape_nowcast"], 4),
        "mape_baseline": round(res["mape_baseline"], 4),
        "n_oos_months": res.get("n_oos", 0),
    }


@experiment(
    "ev-contagion",
    description="EV adoption as contagion on the state-adjacency network: Moran's I, observed cascade, threshold-fit and seed influence.",
)
def ev_contagion(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.networks.contagion import (
        fit_tau,
        load_adjacency,
        morans_i,
        observed_adoption_years,
        seed_influence,
    )

    threshold = params.get("threshold", 0.02)
    g = load_adjacency(con)
    panel = con.execute(
        "SELECT state_code, year, ev_share FROM panel_state_year WHERE state_code <> 'ALL'"
    ).df()
    latest_full = int(panel["year"].max()) - 1

    latest = panel[panel["year"] == latest_full].set_index("state_code")["ev_share"]
    moran = morans_i(latest, g)

    observed = observed_adoption_years(panel, threshold=threshold)
    observed.to_frame().to_parquet(out_dir / "observed_adoption_years.parquet")

    fits = fit_tau(g, observed)
    fits.to_parquet(out_dir / "tau_sweep.parquet")
    best_tau = float(fits["spearman_rho"].idxmax())

    influence = seed_influence(g, best_tau)
    influence.to_parquet(out_dir / "seed_influence.parquet")

    return {
        "threshold": threshold,
        "latest_full_year": latest_full,
        "morans_i": round(moran["I"], 3),
        "morans_p": round(moran["p_value"], 4),
        "n_states_crossed": int(observed.notna().sum()),
        "best_tau": best_tau,
        "best_tau_rho": round(float(fits["spearman_rho"].max()), 3),
        "top_seed": influence.index[0],
    }


@experiment(
    "fuel-regimes",
    description="Hidden-Markov energy regimes: K latent fuel-mix regimes shared across states, regime calendar, transition matrix, policy alignment.",
)
def fuel_regimes(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.complexity.regimes import fit_fuel_regimes, transition_years

    panel = con.execute(
        "SELECT state_code, year, petrol_share, diesel_share, cng_share, ev_share, hybrid_share "
        "FROM panel_state_year WHERE year < (SELECT MAX(year) FROM panel_state_year) "
        "ORDER BY state_code, year"
    ).df()
    res = fit_fuel_regimes(panel, k_range=tuple(params.get("k_range", (2, 3, 4))))

    res["calendar"].to_parquet(out_dir / "regime_calendar.parquet")
    res["regime_means"].to_parquet(out_dir / "regime_means.parquet")
    res["transition_matrix"].to_parquet(out_dir / "transition_matrix.parquet")
    res["selection"].to_parquet(out_dir / "model_selection.parquet")
    trans = transition_years(res["calendar"])
    trans.to_parquet(out_dir / "transition_years.parquet")

    diag = res["transition_matrix"].to_numpy().diagonal()
    return {
        "best_k": int(res["selection"]["bic"].idxmin()),
        "n_states_fit": res["n_states_fit"],
        "regime_labels": list(res["regime_means"]["regime_label"]),
        "stickiest_regime_persistence": round(float(diag.max()), 3),
        "n_transitions_observed": len(trans),
        "modal_transition_year": int(trans["year"].mode().iloc[0]) if not trans.empty else None,
    }


@experiment(
    "adoption-network-horserace",
    description="Which latent network best explains EV adoption timing — geography, economic similarity, or noise-filtered co-adoption?",
)
def adoption_network_horserace(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.networks.contagion import load_adjacency, observed_adoption_years
    from complexity_lab.networks.inference import (
        coadoption_graph,
        economic_similarity_graph,
        horserace,
    )

    threshold = params.get("threshold", 0.02)
    panel = con.execute(
        "SELECT state_code, year, ev_share, pc_income_inr, urban_pct, ev_chargers, cng_stations "
        "FROM panel_state_year WHERE state_code <> 'ALL'"
    ).df()

    observed = observed_adoption_years(panel, threshold=threshold)

    g_geo = load_adjacency(con)
    latest_cov = (
        panel.sort_values("year")
        .groupby("state_code")[["pc_income_inr", "urban_pct", "ev_chargers", "cng_stations"]]
        .last()
    )
    g_econ = economic_similarity_graph(latest_cov, k=params.get("k_nearest", 4))
    shares = panel.pivot_table(index="year", columns="state_code", values="ev_share")
    g_coad = coadoption_graph(shares, alpha=params.get("alpha", 0.05))

    race = horserace(
        {"geographic": g_geo, "economic_similarity": g_econ, "co_adoption": g_coad}, observed
    )
    race.to_parquet(out_dir / "horserace.parquet")
    import networkx as nx

    nx.write_gexf(g_coad, out_dir / "coadoption_network.gexf")

    winner = race["mae_years"].idxmin()
    return {
        "threshold": threshold,
        "winner": winner,
        "mae_winner_years": round(float(race.loc[winner, "mae_years"]), 2),
        "table": {k: round(float(v), 2) for k, v in race["mae_years"].dropna().items()},
        "coadoption_edges": g_coad.number_of_edges(),
    }


@experiment(
    "oem-state-network",
    description="Bipartite OEM–state network: centrality, communities and temporal evolution across BS6/COVID/EV eras.",
)
def oem_state_network(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    edges = con.execute("SELECT * FROM oem_state_edges").df()

    graphs = nb.temporal_graphs(edges, time_col="year")
    evolution = nm.temporal_metric_series(graphs)
    evolution.to_parquet(out_dir / "network_evolution_by_year.parquet")

    latest_year = int(edges["year"].max()) - 1
    g = nb.share_weighted_graph(edges[edges["year"] == latest_year])
    cent = nm.centrality_table(g)
    cent.to_parquet(out_dir / "centrality_latest.parquet")
    comm = nm.communities(g)
    comm.to_parquet(out_dir / "communities_latest.parquet")
    nm.export_gexf(g, out_dir / f"oem_state_{latest_year}.gexf")

    sim = nb.state_similarity_graph(edges[edges["year"] == latest_year])
    nm.export_gexf(sim, out_dir / f"state_similarity_{latest_year}.gexf")

    (out_dir / "top_nodes.json").write_text(
        json.dumps(cent.head(15).reset_index().to_dict(orient="records"), indent=2, default=str)
    )
    return {
        "latest_year": latest_year,
        "modularity_latest": round(float(comm.attrs["modularity"]), 4),
        "n_communities_latest": int(comm.attrs["n_communities"]),
        "density_trend_first": round(float(evolution["density"].iloc[0]), 4),
        "density_trend_last": round(float(evolution["density"].iloc[-1]), 4),
    }

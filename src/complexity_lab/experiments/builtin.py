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
    year_panel = con.execute("SELECT * FROM experiment_state_year").df()
    month_panel = con.execute(
        "SELECT * FROM panel_state_month WHERE state_code = 'ALL' ORDER BY year, month"
    ).df()

    summary = descriptive.summary_table(year_panel)
    summary.to_parquet(out_dir / "state_summary.parquet")
    context = con.execute("SELECT * FROM experiment_state_context").df()
    context.to_parquet(out_dir / "state_reference_context.parquet")

    seasonality = descriptive.seasonality_profile(
        month_panel[month_panel["year"].between(2013, 2025)]
    )
    seasonality.to_parquet(out_dir / "seasonality_all_india.parquet")

    edges = con.execute("SELECT * FROM oem_state_edges").df()
    conc = descriptive.concentration_series(edges, "year", "maker")
    conc.to_parquet(out_dir / "oem_concentration_by_year.parquet")

    latest = year_panel
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

    latest_cov = con.execute(
        """SELECT state_code, real_pc_income_inr, urban_pct,
                  ev_chargers_2025, broad_credit_per_capita_inr,
                  latest_real_gsdp_growth_pct
           FROM experiment_state_context"""
    ).df().set_index("state_code")
    joined = fits.join(latest_cov, how="left")
    joined.to_parquet(out_dir / "bass_fits_with_covariates.parquet")

    ok = joined.dropna(subset=["q", "real_pc_income_inr"])
    corr_q_income = (
        float(ok["q"].corr(ok["real_pc_income_inr"], method="spearman"))
        if len(ok) > 4
        else None
    )
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
        "SELECT * FROM experiment_state_year"
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
        """SELECT state_code, real_pc_income_inr, ev_chargers_2025,
                  broad_credit_per_capita_inr, latest_real_gsdp_growth_pct
           FROM experiment_state_context"""
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
        "SELECT state_code, year, ev_share FROM experiment_state_year"
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
        "FROM experiment_state_year WHERE year < (SELECT MAX(year) FROM experiment_state_year) "
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
        "SELECT state_code, year, ev_share FROM experiment_state_year"
    ).df()

    observed = observed_adoption_years(panel, threshold=threshold)

    g_geo = load_adjacency(con)
    latest_cov = con.execute(
        """SELECT state_code, real_pc_income_inr, real_gsdp_lakh,
                  broad_credit_per_capita_inr, urban_pct,
                  ev_chargers_2025, cng_stations_2024
           FROM experiment_state_context"""
    ).df().set_index("state_code")
    g_econ = economic_similarity_graph(latest_cov, k=params.get("k_nearest", 4))
    shares = panel.pivot_table(index="year", columns="state_code", values="ev_share")
    g_coad = coadoption_graph(shares, alpha=params.get("alpha", 0.05))

    race = horserace(
        {"geographic": g_geo, "economic_similarity": g_econ, "co_adoption": g_coad}, observed
    )
    race.to_parquet(out_dir / "horserace.parquet")
    import networkx as nx

    nx.write_gexf(g_coad, out_dir / "coadoption_network.gexf")

    # Out-of-sample: networks built from pre-split data predict post-split adopters
    from complexity_lab.networks.inference import rewiring_null_test, temporal_holdout_horserace

    split = params.get("split_year", 2022)
    g_coad_pre = coadoption_graph(shares.loc[shares.index <= split], alpha=params.get("alpha", 0.05))
    oos = temporal_holdout_horserace(
        {"geographic": g_geo, "economic_similarity": g_econ, "co_adoption_pre": g_coad_pre},
        observed,
        split_year=split,
    )
    oos.to_parquet(out_dir / "oos_horserace.parquet")

    null = rewiring_null_test(g_coad, observed, n_rewires=params.get("n_rewires", 200))

    winner = race["mae_years"].idxmin()
    return {
        "threshold": threshold,
        "winner": winner,
        "mae_winner_years": round(float(race.loc[winner, "mae_years"]), 2),
        "table": {k: round(float(v), 2) for k, v in race["mae_years"].dropna().items()},
        "coadoption_edges": g_coad.number_of_edges(),
        "oos_split_year": split,
        "oos_table": {k: round(float(v), 2) for k, v in oos["mae_years"].dropna().items()},
        "rewiring_null_p": round(null["p_value"], 3),
        "rewiring_null_mean_mae": round(null["null_mean_mae"], 2),
    }


@experiment(
    "shev-isolation",
    description="Strong hybrids as the structurally isolated technology: adoption vs EV/CNG, policy-incentive mapping, and the UP tax-waiver natural experiment.",
)
def shev_isolation(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.analysis.econometrics import did

    shares = con.execute(
        "SELECT date, ev_share, cng_share, hybrid_share FROM panel_state_month "
        "WHERE state_code = 'ALL' AND year >= 2021 ORDER BY date"
    ).df()
    shares.to_parquet(out_dir / "national_shares_monthly.parquet")

    # Policy-incentive mapping: which technologies do policy events actually touch?
    pol = con.execute(
        "SELECT label, detail, category FROM ref_policy_events_canonical"
    ).df()
    text = (pol["label"].fillna("") + " " + pol["detail"].fillna("")).str.lower()
    counts = {
        "EV": int(text.str.contains("ev|electric").sum()),
        "CNG": int(text.str.contains("cng").sum()),
        "Hybrid": int(text.str.contains("hybrid").sum()),
    }
    tax_context = con.execute(
        """SELECT state_code, ev_tax_rate_pct, hybrid_tax_rate_pct,
                  ice_tax_rate_pct, tax_as_of
           FROM experiment_state_context
           WHERE hybrid_tax_rate_pct IS NOT NULL"""
    ).df()
    tax_context.to_parquet(out_dir / "state_tax_context.parquet")

    # UP strong-hybrid registration-tax waiver (July 2024) as natural experiment
    mp = con.execute(
        "SELECT state_code, date, hybrid_share FROM panel_state_month "
        "WHERE year >= 2023 ORDER BY date"
    ).df()
    res_did = did(
        mp,
        treated="UP",
        controls=params.get("controls", ["RJ", "MP", "BR", "WB"]),
        event_date="2024-07-01",
        value_col="hybrid_share",
        pre_months=params.get("pre_months", 6),
        post_months=params.get("post_months", 8),
    )

    ws_hybrid_start = None
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "wholesale" in tables:
        wsf = con.execute(
            "SELECT date, fuel, wholesale FROM ws_fuel_month WHERE fuel = 'Hybrid' ORDER BY date"
        ).df()
        if not wsf.empty:
            wsf.to_parquet(out_dir / "wholesale_hybrid_monthly.parquet")
            ws_hybrid_start = str(wsf["date"].min())[:7]

    latest = shares.dropna().iloc[-2]
    return {
        "policy_mentions": counts,
        "latest_shares_pct": {
            "hybrid": round(100 * float(latest["hybrid_share"]), 2),
            "ev": round(100 * float(latest["ev_share"]), 2),
            "cng": round(100 * float(latest["cng_share"]), 2),
        },
        "up_did_att_pp": round(100 * res_did["att"], 3),
        "up_did_placebo_rank_p": round(res_did["placebo_rank_p"], 3),
        "wholesale_hybrid_visible_from": ws_hybrid_start,
        "vahan_hybrid_visible_from": "2024-01 (fuel-classification break: zero before 2024)",
    }


@experiment(
    "regime-survival",
    description="Discrete-time hazard model of regime-switch timing: which covariates accelerate a state's energy transition?",
)
def regime_survival(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.complexity.regimes import fit_fuel_regimes
    from complexity_lab.complexity.survival import (
        build_risk_set,
        discrete_hazard_model,
        kaplan_meier,
    )

    panel = con.execute(
        "SELECT state_code, year, petrol_share, diesel_share, cng_share, ev_share, hybrid_share, "
        "real_pc_income_inr, real_gsdp_growth_pct, broad_credit_per_capita_inr "
        "FROM experiment_state_year "
        "WHERE year < (SELECT MAX(year) FROM experiment_state_year) "
        "ORDER BY state_code, year"
    ).df()
    regimes = fit_fuel_regimes(panel)
    covs = params.get(
        "covariates",
        [
            "real_pc_income_inr",
            "real_gsdp_growth_pct",
            "broad_credit_per_capita_inr",
        ],
    )
    risk = build_risk_set(regimes["calendar"], panel, covs)
    risk.to_parquet(out_dir / "risk_set.parquet")

    model = discrete_hazard_model(risk, covs)
    model["table"].to_parquet(out_dir / "hazard_table.parquet")
    km = kaplan_meier(risk)
    km.to_parquet(out_dir / "kaplan_meier.parquet")

    tbl = model["table"]
    return {
        "covariates": covs,
        "n_state_years_at_risk": model["n_obs"],
        "n_switches": model["n_events"],
        "odds_ratios_per_sd": {i: round(float(v), 2) for i, v in tbl["odds_ratio_per_sd"].items()},
        "p_values": {i: round(float(v), 3) for i, v in tbl["p_value"].items()},
        "pseudo_r2": round(model["pseudo_r2"], 3),
        "survival_latest": round(float(km["survival"].iloc[-1]), 3),
    }


@experiment(
    "suv-transition",
    description="The hatchback→SUV structural shift as a complex transition: tipping points per state/city, OEM mover classes, state archetypes (SEG-K01).",
)
def suv_transition(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    from complexity_lab.analysis import segments as seg
    from complexity_lab.complexity.transitions import tipping_summary

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "wholesale" not in tables:
        raise RuntimeError("wholesale table missing — run `uv run lab wholesale` first")

    mix = seg.segment_mix(con)
    mix.to_parquet(out_dir / "segment_mix_year.parquet")

    # State-grain tipping (full era) + city-grain tipping (9-year panel cities)
    st_series = seg.suv_share_series(con, grain="state")
    st_tips = tipping_summary(
        st_series.rename(columns={"entity": "state_code"}), "suv_share",
        min_share_reached=0.10,
    )
    st_tips.to_parquet(out_dir / "state_tipping.parquet")

    cities = seg.panel_cities(con)
    city_series = seg.suv_share_series(con, grain="city", cities=cities)
    city_tips = tipping_summary(
        city_series.rename(columns={"entity": "state_code"}), "suv_share",
        min_share_reached=0.10,
    )
    city_tips.to_parquet(out_dir / "panel_city_tipping.parquet")

    traj = seg.oem_suv_trajectories(con)
    traj.to_parquet(out_dir / "oem_suv_trajectories.parquet")
    movers = seg.classify_movers(traj)
    movers.to_parquet(out_dir / "oem_mover_classes.parquet")

    latest_full = int(st_series["year"].max()) - 1
    arch = seg.state_archetypes(con, year=latest_full, k=params.get("k", 4))
    arch.to_parquet(out_dir / "state_archetypes.parquet")

    tipping_city = city_tips[city_tips["hinge_coef"] > 0]
    return {
        "panel_cities": len(cities),
        "latest_full_year": latest_full,
        "n_states_tipping_up": int((st_tips["hinge_coef"] > 0).sum()),
        "n_cities_tipping_up": int(len(tipping_city)),
        "median_city_tau": round(float(tipping_city["tau"].median()), 3) if len(tipping_city) else None,
        "early_movers": movers[movers["class"] == "early mover"].index.tolist(),
        "segment_locked": movers[movers["class"] == "segment-locked"].index.tolist(),
        "archetype_counts": arch["archetype"].value_counts().to_dict(),
    }


@experiment(
    "shev-counterfactual",
    description="Bass counterfactual: what would SHEV adoption look like at EV-equivalent taxation (GST 43%→5%)? Scenario band, assumption-labelled.",
)
def shev_counterfactual(con: duckdb.DuckDBPyConnection, out_dir: Path, **params) -> dict:
    import numpy as np

    from complexity_lab.simulation.diffusion import bass_cumulative, fit_bass, project_bass

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "wholesale" not in tables:
        raise RuntimeError("wholesale table missing — run `uv run lab wholesale` first")

    ws = con.execute(
        "SELECT date, wholesale FROM ws_fuel_month WHERE fuel = 'Hybrid' "
        "AND date >= '2022-04-01' ORDER BY date"
    ).df()
    cum = ws["wholesale"].fillna(0).cumsum()
    fit = fit_bass(cum.reset_index(drop=True))
    if not np.isfinite(fit.get("m", float("nan"))):
        raise RuntimeError("Bass fit failed on hybrid series")

    # Price scenario: effective tax 43% -> 5% lowers consumer price ~26.6%;
    # with demand elasticity assumptions e ∈ {-1, -1.5, -2} the accessible
    # market scales by (1 + 0.266·|e|). q uplift 1.2 = parity visibility.
    horizon = params.get("horizon", 60)
    scenarios = {}
    for e in params.get("elasticities", (1.0, 1.5, 2.0)):
        m_mult = 1 + 0.266 * e
        proj = project_bass(fit, horizon=horizon, m_mult=m_mult, q_mult=1.2)
        scenarios[f"elasticity_{e:g}"] = proj
        proj.to_parquet(out_dir / f"scenario_e{e:g}.parquet")

    base_proj = project_bass(fit, horizon=horizon)
    base_proj.to_parquet(out_dir / "scenario_baseline.parquet")
    ws.to_parquet(out_dir / "hybrid_actual_monthly.parquet")

    y5 = {k: float(v["cumulative"].iloc[-1]) for k, v in scenarios.items()}
    base5 = float(base_proj["cumulative"].iloc[-1])
    _ = bass_cumulative  # re-exported for the notebook
    return {
        "fit": {k: round(float(fit[k]), 5) for k in ("p", "q", "m", "r2") if k in fit},
        "baseline_cum_5y": round(base5),
        "scenario_cum_5y": {k: round(v) for k, v in y5.items()},
        "uplift_x_at_e1_5": round(y5.get("elasticity_1.5", float("nan")) / base5, 2),
        "assumptions": "GST 43%→5% ⇒ −26.6% price; m·(1+0.266·|e|), q·1.2; NOT a forecast",
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

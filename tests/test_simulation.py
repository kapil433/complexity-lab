import numpy as np
import pandas as pd
import pytest

from complexity_lab.complexity.entropy import complexity_indices, fuel_mix_entropy, rca_matrix
from complexity_lab.simulation.abm import ABMConfig, adoption_summary, run_abm
from complexity_lab.simulation.diffusion import bass_cumulative, fit_bass, project_bass


def test_bass_fit_recovers_known_parameters():
    p, q, m = 0.01, 0.4, 10_000
    t = np.arange(60, dtype=float)
    y = bass_cumulative(t, p, q, m)
    fit = fit_bass(pd.Series(y))
    assert fit["p"] == pytest.approx(p, rel=0.05)
    assert fit["q"] == pytest.approx(q, rel=0.05)
    assert fit["m"] == pytest.approx(m, rel=0.05)
    assert fit["r2"] > 0.999


def test_bass_peak_time_formula():
    fit = {"p": 0.01, "q": 0.4, "m": 1000.0}
    proj = project_bass(fit, horizon=120)
    peak_step = proj.loc[proj["incremental"].idxmax(), "t"]
    expected = np.log(0.4 / 0.01) / 0.41
    assert peak_step == pytest.approx(expected, abs=2)


def test_project_bass_scenario_scales_market():
    fit = {"p": 0.01, "q": 0.4, "m": 1000.0}
    base = project_bass(fit, horizon=300)
    big = project_bass(fit, horizon=300, m_mult=2.0)
    assert big["cumulative"].iloc[-1] == pytest.approx(2 * base["cumulative"].iloc[-1], rel=0.01)


def test_abm_social_contagion_accelerates_adoption():
    base_cfg = ABMConfig(n_agents_per_state=500, n_steps=80, social_weight=0.0, seed=7,
                         state_income={"X": 0.5}, state_infra={"X": 0.5})
    social_cfg = ABMConfig(n_agents_per_state=500, n_steps=80, social_weight=0.3, seed=7,
                           state_income={"X": 0.5}, state_infra={"X": 0.5})
    base = run_abm(base_cfg)
    social = run_abm(social_cfg)
    assert social["adoption_rate"].iloc[-1] > base["adoption_rate"].iloc[-1]


def test_abm_summary_orders_by_adoption():
    cfg = ABMConfig(
        n_agents_per_state=400, n_steps=60, seed=3,
        state_income={"RICH": 1.0, "POOR": 0.0},
        state_infra={"RICH": 1.0, "POOR": 0.0},
    )
    summary = adoption_summary(run_abm(cfg))
    assert summary.index[0] == "RICH"


def test_fuel_mix_entropy_extremes():
    panel = pd.DataFrame(
        {
            "petrol_regs": [100, 20],
            "diesel_regs": [0, 20],
            "cng_regs": [0, 20],
            "ev_regs": [0, 20],
            "hybrid_regs": [0, 20],
        }
    )
    h = fuel_mix_entropy(panel)
    assert h.iloc[0] == pytest.approx(0.0)
    assert h.iloc[1] == pytest.approx(np.log(5))


def test_rca_and_complexity_indices():
    edges = pd.DataFrame(
        {
            "state_code": ["S1", "S1", "S2", "S2", "S3"],
            "maker": ["A", "B", "A", "C", "A"],
            "regs": [50, 50, 80, 20, 100],
        }
    )
    rca = rca_matrix(edges)
    assert rca.shape == (3, 3)
    # S3 sells only A -> strong specialisation in A
    assert rca.loc["S3", "A"] > 1
    idx = complexity_indices(rca)
    assert set(idx) == {"state_complexity", "product_ubiquity", "diversity", "ubiquity"}
    assert idx["diversity"].loc["S1"] >= idx["diversity"].loc["S3"]

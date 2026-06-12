import networkx as nx
import numpy as np
import pandas as pd

from complexity_lab.networks.contagion import (
    fit_tau,
    morans_i,
    observed_adoption_years,
    threshold_cascade,
)


def _line_graph(n=10):
    g = nx.path_graph(n)
    return nx.relabel_nodes(g, {i: f"S{i}" for i in range(n)})


def test_morans_i_detects_clustering():
    g = _line_graph(20)
    clustered = pd.Series({f"S{i}": 1.0 if i < 10 else 0.0 for i in range(20)})
    res = morans_i(clustered, g, n_permutations=499)
    assert res["I"] > 0.5
    assert res["p_value"] < 0.05

    rng = np.random.default_rng(0)
    random_vals = pd.Series({f"S{i}": rng.random() for i in range(20)})
    res_rand = morans_i(random_vals, g, n_permutations=499)
    assert abs(res_rand["I"]) < 0.5


def test_threshold_cascade_spreads_on_line():
    g = _line_graph(6)
    # tau=0.5: S1 has neighbours S0(adopted),S2 -> 1/2 >= 0.5 adopts at step 1, etc.
    sim = threshold_cascade(g, seeds=["S0"], tau=0.5)
    assert sim["S0"] == 0
    assert sim["S1"] == 1
    assert sim["S5"] == 5


def test_threshold_cascade_blocked_by_high_tau():
    g = _line_graph(6)
    sim = threshold_cascade(g, seeds=["S0"], tau=0.9)  # interior nodes need both neighbours
    assert sim.notna().sum() == 1  # only the seed


def test_observed_adoption_years():
    panel = pd.DataFrame(
        {
            "state_code": ["A", "A", "A", "B", "B"],
            "year": [2019, 2020, 2021, 2020, 2021],
            "ev_share": [0.01, 0.025, 0.04, 0.01, 0.015],
        }
    )
    yrs = observed_adoption_years(panel, threshold=0.02)
    assert yrs["A"] == 2020
    assert "B" not in yrs.index


def test_fit_tau_recovers_contagion_order():
    g = _line_graph(12)
    # ground truth: a perfect left-to-right contagion observed as crossing years
    observed = pd.Series({f"S{i}": 2014 + i for i in range(12)}, name="adoption_year", dtype=float)
    fits = fit_tau(g, observed, n_seeds=1)
    best = fits["spearman_rho"].idxmax()
    assert fits.loc[best, "spearman_rho"] > 0.95
    assert best <= 0.5  # a line cascade requires tau <= 1/2

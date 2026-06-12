import networkx as nx
import numpy as np
import pandas as pd

from complexity_lab.networks.inference import (
    coadoption_graph,
    economic_similarity_graph,
    horserace,
    predict_adoption_years,
    rewiring_null_test,
    temporal_holdout_horserace,
)


def test_economic_similarity_knn():
    feats = pd.DataFrame(
        {"income": [100, 98, 95, 10, 12, 11], "urban": [50, 48, 52, 20, 18, 22]},
        index=list("ABCDEF"),
    )
    g = economic_similarity_graph(feats, k=2)
    # rich states should link to rich states, poor to poor
    assert g.has_edge("A", "B") or g.has_edge("A", "C")
    assert g.has_edge("D", "E") or g.has_edge("D", "F")
    assert not g.has_edge("A", "D")


def test_coadoption_graph_recovers_planted_pair():
    rng = np.random.default_rng(3)
    t = 14
    common = rng.normal(0, 1, t).cumsum()
    a = common + rng.normal(0, 0.1, t)
    b = common + rng.normal(0, 0.1, t)
    others = {f"X{i}": rng.normal(0, 1, t).cumsum() for i in range(4)}
    shares = pd.DataFrame({"A": a, "B": b, **others}, index=range(2012, 2012 + t))
    g = coadoption_graph(shares, alpha=0.05, n_permutations=300)
    assert g.has_edge("A", "B")


def test_temporal_holdout_scores_true_network():
    # Adoption sweeps diagonally across a 4x4 grid: year = 2014 + 2(i+j).
    # After split 2021, frontier nodes (i+j = 4) border trained adopters.
    rng = np.random.default_rng(11)
    grid = nx.grid_2d_graph(4, 4)
    g_true = nx.relabel_nodes(grid, {n: f"S{n[0]}{n[1]}" for n in grid.nodes})
    observed = pd.Series(
        {f"S{i}{j}": 2014 + 2 * (i + j) + rng.normal(0, 0.2)
         for i in range(4) for j in range(4)}
    )
    g_random = nx.relabel_nodes(
        nx.gnm_random_graph(16, 24, seed=5),
        dict(enumerate([f"S{i}{j}" for i in range(4) for j in range(4)])),
    )
    res = temporal_holdout_horserace({"true": g_true, "rand": g_random}, observed, split_year=2021)
    assert res.loc["true", "n_test"] >= 3
    assert res.loc["true", "mae_years"] < res.loc["rand", "mae_years"]


def test_rewiring_null_detects_real_wiring():
    rng = np.random.default_rng(13)
    g_true = nx.relabel_nodes(nx.path_graph(16), {i: f"S{i}" for i in range(16)})
    observed = pd.Series({f"S{i}": 2012 + i + rng.normal(0, 0.2) for i in range(16)})
    res = rewiring_null_test(g_true, observed, n_rewires=60, seed=1)
    assert res["observed_mae"] < res["null_mean_mae"]
    assert res["p_value"] < 0.1


def test_horserace_ranks_true_network_first():
    rng = np.random.default_rng(7)
    g_true = nx.relabel_nodes(nx.path_graph(12), {i: f"S{i}" for i in range(12)})
    # adoption year = position along the path + noise -> neighbours are informative
    observed = pd.Series({f"S{i}": 2014 + i + rng.normal(0, 0.3) for i in range(12)})
    g_random = nx.relabel_nodes(
        nx.gnm_random_graph(12, 11, seed=9), {i: f"S{i}" for i in range(12)}
    )
    race = horserace({"true": g_true, "random": g_random}, observed)
    assert race.index[0] == "true"
    assert race.loc["true", "mae_years"] < race.loc["random", "mae_years"]
    preds = predict_adoption_years(g_true, observed)
    assert len(preds) == 12

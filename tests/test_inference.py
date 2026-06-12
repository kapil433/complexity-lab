import networkx as nx
import numpy as np
import pandas as pd

from complexity_lab.networks.inference import (
    coadoption_graph,
    economic_similarity_graph,
    horserace,
    predict_adoption_years,
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

import networkx as nx
import pandas as pd

from complexity_lab.networks import build as nb
from complexity_lab.networks import metrics as nm


def edges_fixture() -> pd.DataFrame:
    # Two clusters: OEMs A,B serve states S1,S2; OEMs C,D serve states S3,S4.
    rows = []
    for maker, state, regs in [
        ("A", "S1", 100), ("A", "S2", 80), ("B", "S1", 60), ("B", "S2", 90),
        ("C", "S3", 100), ("C", "S4", 70), ("D", "S3", 50), ("D", "S4", 120),
        ("A", "S3", 1),  # weak bridge
    ]:
        rows.append({"maker": maker, "state_code": state, "regs": regs, "year": 2024})
    return pd.DataFrame(rows)


def test_bipartite_graph_structure():
    g = nb.bipartite_graph(edges_fixture())
    assert g.number_of_nodes() == 8
    kinds = nx.get_node_attributes(g, "kind")
    assert kinds["A"] == "oem" and kinds["S1"] == "state"
    assert g["A"]["S1"]["weight"] == 100


def test_share_weighted_graph_drops_below_threshold():
    g = nb.share_weighted_graph(edges_fixture(), min_share=0.05)
    # A->S3 has share 1/151 < 5% and must be pruned
    assert not g.has_edge("A", "S3")
    assert g.has_edge("A", "S1")


def test_louvain_finds_planted_partition():
    g = nb.bipartite_graph(edges_fixture(), min_weight=5)  # prune the weak bridge
    comm = nm.communities(g)
    assert comm.attrs["n_communities"] == 2
    assert comm.loc["A", "community"] == comm.loc["S1", "community"]
    assert comm.loc["C", "community"] == comm.loc["S3", "community"]
    assert comm.loc["A", "community"] != comm.loc["C", "community"]


def test_centrality_table_has_all_nodes():
    g = nb.bipartite_graph(edges_fixture())
    cent = nm.centrality_table(g)
    assert len(cent) == g.number_of_nodes()
    assert {"degree", "strength", "betweenness", "eigenvector"} <= set(cent.columns)


def test_state_similarity_graph_clusters():
    g = nb.state_similarity_graph(edges_fixture(), min_similarity=0.8)
    # S1,S2 share the same OEM mix direction; S3,S4 likewise (cosine ~0.84)
    assert g.has_edge("S1", "S2")
    assert g.has_edge("S3", "S4")
    assert not g.has_edge("S1", "S3")


def test_temporal_metric_series():
    edges = edges_fixture()
    g2 = edges.copy()
    g2["year"] = 2025
    series = nm.temporal_metric_series(nb.temporal_graphs(pd.concat([edges, g2])))
    assert list(series.index) == [2024, 2025]
    assert "modularity" in series.columns


def test_community_summary_and_cross_links_are_explicit():
    g = nb.bipartite_graph(edges_fixture())
    comm = nm.communities(g)

    summary = nm.community_summary(g, comm)
    links = nm.cross_community_edges(g, comm)
    flows = nm.community_flow_matrix(g, comm)

    assert len(summary) == comm.attrs["n_communities"]
    assert {"oems", "states", "cross_share"} <= set(summary.columns)
    assert ((links["oem"] == "A") & (links["state"] == "S3")).any()
    assert flows.to_numpy().sum() > 0


def test_edge_changes_reports_births_and_deaths():
    before = nb.bipartite_graph(edges_fixture(), min_weight=5)
    after_edges = edges_fixture()
    after_edges.loc[len(after_edges)] = {
        "maker": "B",
        "state_code": "S3",
        "regs": 20,
        "year": 2024,
    }
    after = nb.bipartite_graph(after_edges, min_weight=5)

    changes = nm.edge_changes(before, after)

    assert ((changes["status"] == "born") & (changes["after"] == 20)).any()

"""Network metrics: centrality, communities, temporal comparison, exports."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd


def centrality_table(g: nx.Graph, weight: str = "weight") -> pd.DataFrame:
    """Degree / strength / betweenness / eigenvector centralities per node."""
    degree = dict(g.degree())
    strength = dict(g.degree(weight=weight))
    betweenness = nx.betweenness_centrality(g, weight=weight)
    try:
        eigen = nx.eigenvector_centrality_numpy(g, weight=weight)
    except (nx.NetworkXException, ValueError):
        eigen = dict.fromkeys(g.nodes, float("nan"))
    df = pd.DataFrame(
        {
            "degree": degree,
            "strength": strength,
            "betweenness": betweenness,
            "eigenvector": eigen,
        }
    )
    df.index.name = "node"
    kinds = nx.get_node_attributes(g, "kind")
    if kinds:
        df["kind"] = pd.Series(kinds)
    return df.sort_values("strength", ascending=False)


def communities(g: nx.Graph, weight: str = "weight", seed: int = 42) -> pd.DataFrame:
    """Louvain communities; returns node → community id with modularity attached."""
    comms = nx.community.louvain_communities(g, weight=weight, seed=seed)
    mod = nx.community.modularity(g, comms, weight=weight)
    rows = [
        {"node": node, "community": cid}
        for cid, members in enumerate(comms)
        for node in members
    ]
    df = pd.DataFrame(rows).set_index("node")
    df.attrs["modularity"] = mod
    df.attrs["n_communities"] = len(comms)
    return df


def temporal_metric_series(
    graphs: dict, metric_fn=None, weight: str = "weight"
) -> pd.DataFrame:
    """Apply a graph-level metric function over a dict of {period: graph}.

    Default metrics: density, modularity of Louvain partition, mean strength.
    """
    rows = []
    for t, g in sorted(graphs.items()):
        if metric_fn is not None:
            rows.append({"period": t, **metric_fn(g)})
            continue
        comms = nx.community.louvain_communities(g, weight=weight, seed=42)
        rows.append(
            {
                "period": t,
                "n_nodes": g.number_of_nodes(),
                "n_edges": g.number_of_edges(),
                "density": nx.density(g),
                "modularity": nx.community.modularity(g, comms, weight=weight),
                "n_communities": len(comms),
            }
        )
    return pd.DataFrame(rows).set_index("period")


def export_gexf(g: nx.Graph, path: str | Path) -> Path:
    """Export for Gephi (ForceAtlas2 + community colouring)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(g, path)
    return path

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


def community_summary(
    g: nx.Graph,
    membership: pd.DataFrame | None = None,
    weight: str = "weight",
) -> pd.DataFrame:
    """One readable row per community with OEMs, states, and internal/cross weight."""
    membership = membership if membership is not None else communities(g, weight=weight)
    community_by_node = membership["community"].to_dict()
    rows = []
    for community_id, members in membership.groupby("community"):
        nodes = members.index.tolist()
        oems = sorted(node for node in nodes if g.nodes[node].get("kind") == "oem")
        states = sorted(node for node in nodes if g.nodes[node].get("kind") == "state")
        internal_weight = 0.0
        cross_weight = 0.0
        for node in nodes:
            for neighbor, attrs in g[node].items():
                edge_weight = float(attrs.get(weight, 1.0))
                if community_by_node.get(neighbor) == community_id:
                    internal_weight += edge_weight / 2
                else:
                    cross_weight += edge_weight
        rows.append(
            {
                "community": int(community_id),
                "n_oems": len(oems),
                "n_states": len(states),
                "oems": ", ".join(oems),
                "states": ", ".join(states),
                "internal_weight": internal_weight,
                "cross_weight": cross_weight,
                "cross_share": cross_weight / max(internal_weight + cross_weight, 1e-12),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["n_states", "n_oems", "internal_weight"], ascending=False
    )


def cross_community_edges(
    g: nx.Graph,
    membership: pd.DataFrame | None = None,
    weight: str = "weight",
) -> pd.DataFrame:
    """List edges connecting nodes assigned to different communities."""
    membership = membership if membership is not None else communities(g, weight=weight)
    community_by_node = membership["community"].to_dict()
    rows = []
    for source, target, attrs in g.edges(data=True):
        source_community = community_by_node.get(source)
        target_community = community_by_node.get(target)
        if source_community == target_community:
            continue
        if g.nodes[source].get("kind") == "state":
            source, target = target, source
            source_community, target_community = target_community, source_community
        rows.append(
            {
                "oem": source,
                "state": target,
                "oem_community": int(source_community),
                "state_community": int(target_community),
                "weight": float(attrs.get(weight, 1.0)),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["oem", "state", "oem_community", "state_community", "weight"]
        )
    return pd.DataFrame(rows).sort_values("weight", ascending=False).reset_index(drop=True)


def community_flow_matrix(
    g: nx.Graph,
    membership: pd.DataFrame | None = None,
    weight: str = "weight",
) -> pd.DataFrame:
    """Community-to-community cross-link weight matrix."""
    membership = membership if membership is not None else communities(g, weight=weight)
    links = cross_community_edges(g, membership, weight=weight)
    community_ids = sorted(membership["community"].unique())
    if links.empty:
        return pd.DataFrame(0.0, index=community_ids, columns=community_ids)
    matrix = links.pivot_table(
        index="oem_community",
        columns="state_community",
        values="weight",
        aggfunc="sum",
        fill_value=0,
    )
    return matrix.reindex(index=community_ids, columns=community_ids, fill_value=0)


def edge_changes(
    previous: nx.Graph,
    current: nx.Graph,
    weight: str = "weight",
) -> pd.DataFrame:
    """Births, deaths, and weight changes between two graph vintages."""
    previous_edges = {
        frozenset((source, target)): float(attrs.get(weight, 1.0))
        for source, target, attrs in previous.edges(data=True)
    }
    current_edges = {
        frozenset((source, target)): float(attrs.get(weight, 1.0))
        for source, target, attrs in current.edges(data=True)
    }
    rows = []
    for edge in previous_edges.keys() | current_edges.keys():
        nodes = sorted(edge)
        before = previous_edges.get(edge, 0.0)
        after = current_edges.get(edge, 0.0)
        status = "born" if before == 0 else "died" if after == 0 else "changed"
        rows.append(
            {
                "node_a": nodes[0],
                "node_b": nodes[1],
                "before": before,
                "after": after,
                "change": after - before,
                "status": status,
            }
        )
    return pd.DataFrame(rows).sort_values("change", key=abs, ascending=False)


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

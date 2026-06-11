"""Build bipartite OEM–state graphs and their projections from edge tables.

Input convention: an edge dataframe with columns ``maker``, ``state_code``
(or ``state_name``) and ``regs`` — exactly what the ``oem_state_edges`` DuckDB
view yields, optionally filtered by year/fy.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd


def bipartite_graph(
    edges: pd.DataFrame,
    state_col: str = "state_code",
    maker_col: str = "maker",
    weight_col: str = "regs",
    min_weight: float = 0,
) -> nx.Graph:
    """Weighted bipartite graph: OEM nodes (bipartite=0) ↔ state nodes (bipartite=1)."""
    g = nx.Graph()
    agg = edges.groupby([maker_col, state_col])[weight_col].sum().reset_index()
    agg = agg[agg[weight_col] > min_weight]
    g.add_nodes_from(agg[maker_col].unique(), bipartite=0, kind="oem")
    g.add_nodes_from(agg[state_col].unique(), bipartite=1, kind="state")
    g.add_weighted_edges_from(agg[[maker_col, state_col, weight_col]].itertuples(index=False))
    return g


def share_weighted_graph(
    edges: pd.DataFrame,
    state_col: str = "state_code",
    maker_col: str = "maker",
    weight_col: str = "regs",
    min_share: float = 0.005,
) -> nx.Graph:
    """Bipartite graph weighted by *within-state share* rather than raw volume.

    Removes the size-of-state confound: an edge exists if the OEM holds at
    least ``min_share`` of that state's registrations.
    """
    d = edges.groupby([maker_col, state_col])[weight_col].sum().reset_index()
    d["share"] = d[weight_col] / d.groupby(state_col)[weight_col].transform("sum")
    d = d[d["share"] >= min_share]
    g = nx.Graph()
    g.add_nodes_from(d[maker_col].unique(), bipartite=0, kind="oem")
    g.add_nodes_from(d[state_col].unique(), bipartite=1, kind="state")
    g.add_weighted_edges_from(d[[maker_col, state_col, "share"]].itertuples(index=False))
    return g


def project_states(g: nx.Graph) -> nx.Graph:
    """Project the bipartite graph onto state nodes (weighted by shared OEMs)."""
    states = [n for n, d in g.nodes(data=True) if d.get("bipartite") == 1]
    return nx.bipartite.weighted_projected_graph(g, states)


def project_oems(g: nx.Graph) -> nx.Graph:
    """Project the bipartite graph onto OEM nodes (weighted by shared states)."""
    oems = [n for n, d in g.nodes(data=True) if d.get("bipartite") == 0]
    return nx.bipartite.weighted_projected_graph(g, oems)


def temporal_graphs(
    edges: pd.DataFrame, time_col: str = "year", **kwargs
) -> dict[int | str, nx.Graph]:
    """One bipartite graph per time period — the unit of temporal analysis."""
    return {t: bipartite_graph(grp, **kwargs) for t, grp in edges.groupby(time_col)}


def state_similarity_graph(
    edges: pd.DataFrame,
    state_col: str = "state_code",
    maker_col: str = "maker",
    weight_col: str = "regs",
    min_similarity: float = 0.5,
) -> nx.Graph:
    """States connected by cosine similarity of their OEM-mix vectors.

    The complexity-science view: states with similar market composition are
    'close' in market-structure space regardless of geography.
    """
    import numpy as np

    pivot = edges.pivot_table(
        index=state_col, columns=maker_col, values=weight_col, aggfunc="sum", fill_value=0
    )
    shares = pivot.div(pivot.sum(axis=1), axis=0)
    m = shares.to_numpy()
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    sim = (m @ m.T) / (norms @ norms.T)
    g = nx.Graph()
    g.add_nodes_from(shares.index)
    idx = shares.index.to_list()
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            if sim[i, j] >= min_similarity:
                g.add_edge(idx[i], idx[j], weight=float(sim[i, j]))
    return g

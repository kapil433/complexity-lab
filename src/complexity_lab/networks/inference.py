"""Adoption-network inference (blueprint Project A, pragmatic core).

We never observe how states influence each other's EV adoption — only outcomes.
This module builds three candidate influence networks and races them on a
prediction task:

1. **Geographic** — shared land borders (``ref_state_adjacency``).
2. **Economic similarity** — k-nearest-neighbour cosine similarity on slow
   covariates (income, urbanization, infrastructure).
3. **Co-adoption** — correlation of EV-share *changes*, filtered against a
   circular-shift permutation null so only co-movement beyond autocorrelation
   noise survives. (A statistically-validated network in spirit; full
   maximum-entropy BiCM/NEMtropy is the published-paper upgrade.)

Horse race: leave-one-out — predict each state's threshold-crossing year from
its network neighbours' years; score MAE and Spearman. The network that
predicts best is the better model of the latent influence structure.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def economic_similarity_graph(features: pd.DataFrame, k: int = 4) -> nx.Graph:
    """kNN graph on cosine similarity of standardized state feature vectors.

    ``features``: rows = states, columns = numeric covariates (NaNs imputed
    with column medians).
    """
    x = features.astype("float64")
    x = x.fillna(x.median(numeric_only=True))
    z = (x - x.mean()) / x.std(ddof=0).replace(0, 1)
    m = z.to_numpy(dtype=float)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    sim = (m @ m.T) / (norms @ norms.T)
    np.fill_diagonal(sim, -np.inf)
    g = nx.Graph()
    g.add_nodes_from(features.index)
    idx = features.index.to_list()
    for i, state in enumerate(idx):
        for j in np.argsort(sim[i])[::-1][:k]:
            g.add_edge(state, idx[int(j)], weight=float(sim[i, int(j)]))
    return g


def coadoption_graph(
    shares: pd.DataFrame,
    alpha: float = 0.05,
    n_permutations: int = 500,
    seed: int = 42,
) -> nx.Graph:
    """States linked when their EV-share changes co-move beyond a circular-shift null.

    ``shares``: wide frame, index = year (sorted), columns = state codes.
    Circular shifts preserve each series' autocorrelation, so surviving edges
    reflect genuine cross-state synchrony, not shared smoothness.
    """
    chg = shares.sort_index().diff().dropna(how="all")
    cols = [c for c in chg.columns if chg[c].notna().sum() >= 6]
    data = chg[cols].to_numpy(dtype=float)
    t, n = data.shape
    rng = np.random.default_rng(seed)

    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        mask = ~(np.isnan(a) | np.isnan(b))
        if mask.sum() < 5:
            return np.nan
        return float(np.corrcoef(a[mask], b[mask])[0, 1])

    g = nx.Graph()
    g.add_nodes_from(cols)
    for i in range(n):
        for j in range(i + 1, n):
            obs = _corr(data[:, i], data[:, j])
            if not np.isfinite(obs):
                continue
            shifts = rng.integers(1, t - 1, size=n_permutations)
            null = np.array([_corr(data[:, i], np.roll(data[:, j], s)) for s in shifts])
            null = null[np.isfinite(null)]
            if null.size == 0:
                continue
            p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (null.size + 1)
            if p <= alpha and obs > 0:
                g.add_edge(cols[i], cols[j], weight=obs, p_value=float(p))
    return g


def predict_adoption_years(g: nx.Graph, observed: pd.Series) -> pd.Series:
    """Leave-one-out: each state's predicted crossing year = weighted mean of
    its neighbours' observed years (weights = edge weights if present)."""
    preds = {}
    for node in g.nodes:
        if node not in observed.index or pd.isna(observed[node]):
            continue
        vals, wts = [], []
        for nb in g.neighbors(node):
            y = observed.get(nb, np.nan)
            if pd.notna(y):
                vals.append(float(y))
                wts.append(float(g[node][nb].get("weight", 1.0)))
        if vals:
            preds[node] = float(np.average(vals, weights=wts))
    return pd.Series(preds, name="predicted_year")


def temporal_holdout_horserace(
    networks: dict[str, nx.Graph], observed: pd.Series, split_year: int
) -> pd.DataFrame:
    """Out-of-sample version: predict states that crossed AFTER ``split_year``
    using only neighbours that crossed ON OR BEFORE it.

    For co-adoption networks, build the graph from pre-split data before
    calling this — the function only controls the label split.
    """
    train = observed[observed <= split_year]
    test = observed[observed > split_year]
    rows = []
    for name, g in networks.items():
        preds = {}
        for node in test.index:
            if node not in g:
                continue
            vals, wts = [], []
            for nb in g.neighbors(node):
                y = train.get(nb, np.nan)
                if pd.notna(y):
                    vals.append(float(y))
                    wts.append(float(g[node][nb].get("weight", 1.0)))
            if vals:
                preds[node] = float(np.average(vals, weights=wts))
        pred = pd.Series(preds)
        common = pred.index.intersection(test.index)
        if len(common) < 3:
            rows.append({"network": name, "n_test": len(common), "mae_years": np.nan})
            continue
        err = (pred.loc[common] - test.loc[common]).abs()
        rows.append(
            {
                "network": name,
                "n_test": int(len(common)),
                "n_train_adopters": int(train.notna().sum()),
                "mae_years": float(err.mean()),
            }
        )
    return pd.DataFrame(rows).set_index("network").sort_values("mae_years")


def rewiring_null_test(
    g: nx.Graph, observed: pd.Series, n_rewires: int = 200, seed: int = 42
) -> dict:
    """Does the network's predictive skill survive degree-preserving rewiring?

    Maslov–Sneppen double-edge swaps keep every node's degree but destroy the
    specific wiring; if the real graph's leave-one-out MAE beats most rewired
    versions, the *particular* edges (not just the degree sequence) carry the
    signal. Weights are ignored for a fair comparison.
    """
    g0 = nx.Graph()
    g0.add_nodes_from(g.nodes)
    g0.add_edges_from(g.edges)  # strip weights

    def _mae(graph: nx.Graph) -> float:
        pred = predict_adoption_years(graph, observed)
        common = pred.index.intersection(observed.dropna().index)
        if len(common) < 5:
            return np.nan
        return float((pred.loc[common] - observed.loc[common]).abs().mean())

    obs_mae = _mae(g0)
    rng = np.random.default_rng(seed)
    null_maes = []
    n_swaps = max(g0.number_of_edges() * 4, 10)
    for _ in range(n_rewires):
        gr = g0.copy()
        try:
            nx.double_edge_swap(gr, nswap=n_swaps, max_tries=n_swaps * 30,
                                seed=int(rng.integers(0, 2**31 - 1)))
        except nx.NetworkXError:
            continue  # too few edges to keep swapping — skip this draw
        m = _mae(gr)
        if np.isfinite(m):
            null_maes.append(m)
    null = np.array(null_maes)
    p = float((np.sum(null <= obs_mae) + 1) / (null.size + 1)) if null.size else np.nan
    return {
        "observed_mae": obs_mae,
        "null_mean_mae": float(null.mean()) if null.size else np.nan,
        "null_p5_mae": float(np.percentile(null, 5)) if null.size else np.nan,
        "p_value": p,
        "n_null": int(null.size),
    }


def horserace(networks: dict[str, nx.Graph], observed: pd.Series) -> pd.DataFrame:
    """Score each candidate network on leave-one-out adoption-year prediction."""
    rows = []
    for name, g in networks.items():
        pred = predict_adoption_years(g, observed)
        common = pred.index.intersection(observed.dropna().index)
        if len(common) < 5:
            rows.append({"network": name, "n_predicted": len(common),
                         "mae_years": np.nan, "spearman": np.nan})
            continue
        err = (pred.loc[common] - observed.loc[common]).abs()
        rho, _ = spearmanr(observed.loc[common], pred.loc[common])
        rows.append(
            {
                "network": name,
                "n_predicted": int(len(common)),
                "n_edges": g.number_of_edges(),
                "mae_years": float(err.mean()),
                "spearman": float(rho),
            }
        )
    return pd.DataFrame(rows).set_index("network").sort_values("mae_years")

"""Contagion on the state network: spatial autocorrelation + threshold cascades.

Did EV adoption spread between neighbouring states like a contagion?
Three pieces of evidence, in increasing strength:

1. **Moran's I** — are high-EV states geographically clustered?
2. **Observed cascade** — the year each state crossed an adoption threshold.
3. **Threshold-contagion fit** — simulate "adopt when ≥ τ of neighbours adopted",
   seeded with the actual first adopters; find the τ whose simulated adoption
   order best matches reality (Spearman rank correlation).
"""

from __future__ import annotations

import duckdb
import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def load_adjacency(con: duckdb.DuckDBPyConnection) -> nx.Graph:
    edges = con.execute("SELECT state_a, state_b FROM ref_state_adjacency").df()
    g = nx.Graph()
    g.add_edges_from(edges.itertuples(index=False))
    return g


def morans_i(values: pd.Series, g: nx.Graph, n_permutations: int = 999, seed: int = 42) -> dict:
    """Moran's I with permutation p-value. ``values`` indexed by node id."""
    nodes = [n for n in g.nodes if n in values.index and pd.notna(values[n])]
    x = values.loc[nodes].to_numpy(dtype=float)
    n = len(nodes)
    if n < 5:
        return {"I": np.nan, "p_value": np.nan, "n": n}
    idx = {s: i for i, s in enumerate(nodes)}
    w = np.zeros((n, n))
    for a, b in g.edges:
        if a in idx and b in idx:
            w[idx[a], idx[b]] = w[idx[b], idx[a]] = 1.0

    def _moran(v: np.ndarray) -> float:
        z = v - v.mean()
        denom = (z**2).sum()
        return (n / w.sum()) * float(z @ w @ z) / denom if denom > 0 else np.nan

    obs = _moran(x)
    rng = np.random.default_rng(seed)
    perms = np.array([_moran(rng.permutation(x)) for _ in range(n_permutations)])
    p = float((np.sum(np.abs(perms) >= abs(obs)) + 1) / (n_permutations + 1))
    return {"I": float(obs), "p_value": p, "n": n, "expected_I": -1.0 / (n - 1)}


def observed_adoption_years(
    panel_year: pd.DataFrame, share_col: str = "ev_share", threshold: float = 0.02
) -> pd.Series:
    """First year each state's share crossed the threshold (NaN = not yet)."""
    crossed = panel_year[panel_year[share_col] >= threshold]
    return crossed.groupby("state_code")["year"].min().rename("adoption_year")


def threshold_cascade(
    g: nx.Graph, seeds: list[str], tau: float, max_steps: int = 30
) -> pd.Series:
    """Simulate: a node adopts when ≥ tau of its neighbours have adopted.
    Returns adoption step per node (seeds = 0; NaN = never adopts)."""
    adopted = {s: 0 for s in seeds if s in g}
    for step in range(1, max_steps + 1):
        new = []
        for node in g.nodes:
            if node in adopted:
                continue
            nbrs = list(g.neighbors(node))
            if not nbrs:
                continue
            frac = sum(1 for nb in nbrs if nb in adopted) / len(nbrs)
            if frac >= tau:
                new.append(node)
        if not new:
            break
        for node in new:
            adopted[node] = step
    return pd.Series(adopted, name="sim_step", dtype=float)


def fit_tau(
    g: nx.Graph,
    observed: pd.Series,
    n_seeds: int = 3,
    taus: np.ndarray | None = None,
) -> pd.DataFrame:
    """Sweep τ; score each by Spearman rank-match between simulated adoption order
    and the observed crossing years (states never simulated-adopted are ranked last)."""
    taus = taus if taus is not None else np.round(np.arange(0.05, 0.85, 0.05), 2)
    seeds = observed.dropna().sort_values().head(n_seeds).index.tolist()
    rows = []
    late = observed.dropna().max() + 10
    for tau in taus:
        sim = threshold_cascade(g, seeds, float(tau))
        common = observed.dropna().index.intersection(g.nodes)
        sim_full = pd.Series({s: sim.get(s, np.inf) for s in common})
        obs_full = observed.loc[common].fillna(late)
        finite = np.isfinite(sim_full)
        # rank: never-adopted in sim get a shared worst rank
        sim_rank = sim_full.where(finite, sim_full[finite].max() + 1 if finite.any() else 1)
        rho, p = spearmanr(obs_full, sim_rank)
        rows.append(
            {
                "tau": float(tau),
                "spearman_rho": float(rho),
                "p_value": float(p),
                "cascade_size": int(finite.sum()),
                "n_states": len(common),
                "seeds": ",".join(seeds),
            }
        )
    return pd.DataFrame(rows).set_index("tau")


def seed_influence(g: nx.Graph, tau: float, candidates: list[str] | None = None) -> pd.DataFrame:
    """For each candidate seed state: how large a cascade does it ignite alone at τ?"""
    candidates = candidates or list(g.nodes)
    rows = []
    for seed in candidates:
        sim = threshold_cascade(g, [seed], tau)
        rows.append(
            {
                "seed": seed,
                "cascade_size": int(sim.notna().sum()),
                "mean_step": float(sim.mean()) if sim.notna().any() else np.nan,
            }
        )
    return (
        pd.DataFrame(rows)
        .set_index("seed")
        .sort_values(["cascade_size", "mean_step"], ascending=[False, True])
    )

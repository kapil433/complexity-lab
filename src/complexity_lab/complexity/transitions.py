"""Phase transitions and threshold phenomena in the PV market.

Three lenses, all standard complexity-science instruments:

1. **Percolation** (`percolation_curve`): sweep the minimum-share threshold for
   an OEM–state edge to exist; track the giant connected component. The
   critical threshold where the giant component collapses is the "minimum
   viable presence" scale of the market (blueprint E39).

2. **Adoption tipping points** (`threshold_scan`, `tipping_summary`): piecewise
   (threshold) regression of Δshare on lagged share — finds the share level τ*
   beyond which growth self-accelerates (positive feedback), the signature of
   a phase transition in adoption dynamics (blueprint SEG-K01 / EV threshold).

3. **Fuel regime dynamics** (`classify_regimes`, `regime_transition_matrix`):
   discretise each state-year into a fuel regime and study the empirical
   Markov transition matrix — which regimes are absorbing, which paths
   (fossil → CNG → EV) actually occur (blueprint Project B, rule-based).
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- percolation


def percolation_curve(
    edges: pd.DataFrame,
    thresholds: np.ndarray | None = None,
    state_col: str = "state_code",
    maker_col: str = "maker",
    weight_col: str = "regs",
) -> pd.DataFrame:
    """Giant-component size vs within-state share threshold.

    For each threshold τ, keep edges where the OEM holds ≥ τ share of the
    state's volume; record the largest-connected-component fraction, edge
    count and component count of the bipartite graph.
    """
    d = edges.groupby([maker_col, state_col])[weight_col].sum().reset_index()
    d["share"] = d[weight_col] / d.groupby(state_col)[weight_col].transform("sum")
    n_nodes_full = d[maker_col].nunique() + d[state_col].nunique()
    if thresholds is None:
        thresholds = np.geomspace(0.001, 0.5, 40)

    rows = []
    for tau in thresholds:
        kept = d[d["share"] >= tau]
        g = nx.Graph()
        g.add_edges_from(zip(kept[maker_col], kept[state_col], strict=False))
        if g.number_of_nodes() == 0:
            rows.append({"threshold": tau, "giant_frac": 0.0, "n_edges": 0, "n_components": 0})
            continue
        comps = list(nx.connected_components(g))
        giant = max(len(c) for c in comps)
        rows.append(
            {
                "threshold": tau,
                "giant_frac": giant / n_nodes_full,
                "n_edges": g.number_of_edges(),
                "n_components": len(comps),
            }
        )
    return pd.DataFrame(rows)


def critical_threshold(curve: pd.DataFrame, col: str = "giant_frac") -> float:
    """Threshold of steepest giant-component drop — the percolation point."""
    c = curve.sort_values("threshold").reset_index(drop=True)
    drop = c[col].diff()
    if drop.dropna().empty:
        return float("nan")
    i = drop.idxmin()
    return float(c.loc[i, "threshold"])


# ------------------------------------------------------- adoption tipping point


def threshold_scan(
    share: pd.Series, candidate_taus: np.ndarray | None = None, min_side: int = 5
) -> dict:
    """Fit Δs_t = a + b·s_{t-1} + c·max(0, s_{t-1} − τ) over candidate τ.

    Picks τ* by SSE. A significantly positive ``c`` means growth *accelerates*
    once the share crosses τ* — positive feedback / tipping behaviour.
    Series must be time-ordered (one entity).
    """
    s = share.dropna().astype(float)
    ds = s.diff().dropna()
    lag = s.shift(1).reindex(ds.index)
    if len(ds) < 2 * min_side + 2:
        return {"tau": np.nan, "slope_below": np.nan, "slope_above": np.nan, "sse_gain": np.nan}
    if candidate_taus is None:
        candidate_taus = np.quantile(lag, np.linspace(0.2, 0.8, 25))

    X0 = np.column_stack([np.ones(len(lag)), lag])
    beta0, res0, *_ = np.linalg.lstsq(X0, ds, rcond=None)
    sse0 = float(res0[0]) if len(res0) else float(((ds - X0 @ beta0) ** 2).sum())

    best = {"tau": np.nan, "sse": np.inf, "beta": None}
    for tau in np.unique(candidate_taus):
        hinge = np.maximum(0.0, lag - tau)
        if (hinge > 0).sum() < min_side or (hinge == 0).sum() < min_side:
            continue
        X = np.column_stack([np.ones(len(lag)), lag, hinge])
        beta, res, *_ = np.linalg.lstsq(X, ds, rcond=None)
        sse = float(res[0]) if len(res) else float(((ds - X @ beta) ** 2).sum())
        if sse < best["sse"]:
            best = {"tau": float(tau), "sse": sse, "beta": beta}

    if best["beta"] is None:
        return {"tau": np.nan, "slope_below": np.nan, "slope_above": np.nan, "sse_gain": np.nan}
    b = best["beta"]
    return {
        "tau": best["tau"],
        "slope_below": float(b[1]),
        "slope_above": float(b[1] + b[2]),
        "hinge_coef": float(b[2]),
        "sse_gain": float(1 - best["sse"] / sse0) if sse0 > 0 else np.nan,
        "n": len(ds),
    }


def tipping_summary(
    panel: pd.DataFrame, share_col: str, entity_col: str = "state_code",
    time_cols: tuple[str, ...] = ("year", "month"), min_share_reached: float = 0.01,
    smooth_window: int = 3,
) -> pd.DataFrame:
    """Run threshold_scan per entity; skip entities that never reached
    ``min_share_reached`` (no transition to detect).

    Shares are smoothed with a centred rolling mean first — month-to-month
    noise in a share series otherwise produces mean-reversion artefacts that
    masquerade as saturation (negative hinge).
    """
    rows = []
    for ent, grp in panel.sort_values(list(time_cols)).groupby(entity_col):
        s = grp[share_col].rolling(smooth_window, center=True, min_periods=1).mean()
        if s.max() < min_share_reached:
            continue
        res = threshold_scan(s)
        res[entity_col] = ent
        res["max_share"] = float(s.max())
        rows.append(res)
    return pd.DataFrame(rows).set_index(entity_col) if rows else pd.DataFrame()


# ------------------------------------------------------------- fuel regimes


REGIMES = ["fossil_dominant", "cng_transitioned", "ev_emerging", "multi_fuel"]


def classify_regimes(panel_year: pd.DataFrame) -> pd.DataFrame:
    """Rule-based fuel regime per state-year (transparent, no fitting):

    - ``ev_emerging``     : EV share ≥ 5%
    - ``cng_transitioned``: CNG share ≥ 15% (and EV < 5%)
    - ``multi_fuel``      : fuel entropy ≥ 1.0 nats (diversified, no single story)
    - ``fossil_dominant`` : otherwise (petrol+diesel ≥ ~85%)
    """
    d = panel_year.copy()
    shares = d[["petrol_share", "diesel_share", "cng_share", "ev_share", "hybrid_share"]].fillna(0)
    p = shares.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(p > 0, p * np.log(p), 0.0)
    d["fuel_entropy"] = -terms.sum(axis=1)

    def rule(row) -> str:
        if row["ev_share"] >= 0.05:
            return "ev_emerging"
        if row["cng_share"] >= 0.15:
            return "cng_transitioned"
        if row["fuel_entropy"] >= 1.0:
            return "multi_fuel"
        return "fossil_dominant"

    d["regime"] = d.apply(rule, axis=1)
    return d[["state_code", "state_name", "year", "regime", "fuel_entropy"]]


def regime_transition_matrix(regimes: pd.DataFrame) -> pd.DataFrame:
    """Empirical Markov matrix P(next regime | current regime) across state-years."""
    d = regimes.sort_values(["state_code", "year"])
    d["next_regime"] = d.groupby("state_code")["regime"].shift(-1)
    pairs = d.dropna(subset=["next_regime"])
    counts = pd.crosstab(pairs["regime"], pairs["next_regime"])
    counts = counts.reindex(index=REGIMES, columns=REGIMES, fill_value=0)
    return counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0)


def absorbing_regimes(matrix: pd.DataFrame, threshold: float = 0.95) -> list[str]:
    """Regimes whose self-transition probability exceeds ``threshold``."""
    return [r for r in matrix.index if pd.notna(matrix.loc[r, r]) and matrix.loc[r, r] >= threshold]

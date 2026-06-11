"""Diversity and economic-complexity-style indices for the PV market.

The market is treated as a state × product (OEM or fuel) matrix; we compute
diversity, ubiquity and an iterated complexity index in the spirit of
Hidalgo & Hausmann (2009) — here interpreting 'products' as market segments
an OEM serves rather than export goods.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fuel_mix_entropy(panel: pd.DataFrame) -> pd.Series:
    """Shannon entropy (nats) of the fuel mix per panel row — drivetrain diversity."""
    fuel_cols = ["petrol_regs", "diesel_regs", "cng_regs", "ev_regs", "hybrid_regs"]
    m = panel[fuel_cols].to_numpy(dtype=float)
    totals = m.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(totals > 0, m / totals, 0.0)
        terms = np.where(p > 0, p * np.log(p), 0.0)
    return pd.Series(-terms.sum(axis=1), index=panel.index, name="fuel_entropy")


def rca_matrix(
    edges: pd.DataFrame,
    state_col: str = "state_code",
    product_col: str = "maker",
    value_col: str = "regs",
) -> pd.DataFrame:
    """Revealed comparative advantage (Balassa) matrix: state × product.

    RCA > 1 ⇒ the state is relatively specialised in that product.
    """
    pivot = edges.pivot_table(
        index=state_col, columns=product_col, values=value_col, aggfunc="sum", fill_value=0
    ).astype(float)
    total = pivot.to_numpy().sum()
    row_share = pivot.div(pivot.sum(axis=1), axis=0)
    col_share = pivot.sum(axis=0) / total
    return row_share.div(col_share, axis=1)


def complexity_indices(rca: pd.DataFrame, threshold: float = 1.0, n_iter: int = 18) -> dict:
    """Method-of-reflections complexity indices on the binarised RCA matrix.

    Returns ``state_complexity`` (diversity-corrected sophistication of each
    state's market) and ``product_ubiquity`` series.
    """
    m = (rca >= threshold).astype(float)
    # Drop empty rows/cols to keep iterations well-defined
    m = m.loc[m.sum(axis=1) > 0, m.sum(axis=0) > 0]
    kc = m.sum(axis=1).to_numpy(dtype=float)  # diversity
    kp = m.sum(axis=0).to_numpy(dtype=float)  # ubiquity
    kc_n, kp_n = kc.copy(), kp.copy()
    a = m.to_numpy()
    for _ in range(n_iter):
        kc_next = (a @ kp_n) / kc
        kp_next = (a.T @ kc_n) / kp
        kc_n, kp_n = kc_next, kp_next
    z = lambda v: (v - v.mean()) / v.std() if v.std() > 0 else v * 0  # noqa: E731
    return {
        "state_complexity": pd.Series(z(kc_n), index=m.index, name="eci"),
        "product_ubiquity": pd.Series(z(kp_n), index=m.columns, name="pci"),
        "diversity": pd.Series(kc, index=m.index, name="diversity"),
        "ubiquity": pd.Series(kp, index=m.columns, name="ubiquity"),
    }

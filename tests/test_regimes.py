import numpy as np
import pandas as pd

from complexity_lab.complexity.regimes import (
    FUEL_COLS,
    GaussianHMM,
    fit_fuel_regimes,
    transition_years,
)


def _synthetic_sequences(n_seq=12, t=20, seed=0):
    """Two well-separated regimes with sticky transitions; switch near t/2."""
    rng = np.random.default_rng(seed)
    mean0 = np.array([0.70, 0.25, 0.03, 0.01, 0.01])  # fossil era
    mean1 = np.array([0.45, 0.10, 0.20, 0.22, 0.03])  # transitioned
    seqs, true_paths = [], []
    for _ in range(n_seq):
        switch = rng.integers(t // 3, 2 * t // 3)
        path = np.array([0] * switch + [1] * (t - switch))
        x = np.where(path[:, None] == 0, mean0, mean1) + rng.normal(0, 0.02, size=(t, 5))
        seqs.append(x)
        true_paths.append(path)
    return seqs, true_paths


def test_hmm_recovers_two_regimes():
    seqs, true_paths = _synthetic_sequences()
    m = GaussianHMM(2, seed=1).fit(seqs)
    # match learned states to true regimes by mean EV share (index 3)
    ev_order = np.argsort(m.means_[:, 3])  # low-EV state first
    acc = []
    for seq, truth in zip(seqs, true_paths, strict=True):
        path = m.viterbi(seq)
        mapped = np.where(path == ev_order[1], 1, 0)
        acc.append((mapped == truth).mean())
    assert np.mean(acc) > 0.9
    assert m.transmat_.diagonal().min() > 0.7  # regimes are sticky


def test_bic_prefers_true_k():
    seqs, _ = _synthetic_sequences()
    fits = {k: GaussianHMM(k, seed=2).fit(seqs) for k in (2, 4)}
    assert fits[2].bic() < fits[4].bic()


def test_fit_fuel_regimes_on_panel_frame():
    seqs, _ = _synthetic_sequences(n_seq=6, t=14)
    rows = []
    for i, seq in enumerate(seqs):
        for j, x in enumerate(seq):
            rows.append({"state_code": f"S{i}", "year": 2012 + j,
                         **dict(zip(FUEL_COLS, x, strict=True))})
    panel = pd.DataFrame(rows)
    res = fit_fuel_regimes(panel, k_range=(2, 3), min_years=5, n_restarts=2)
    assert res["n_states_fit"] == 6
    assert set(res["calendar"]["regime"]) <= {0, 1, 2}
    trans = transition_years(res["calendar"])
    # every synthetic state switches exactly once under a good fit; allow some slack
    per_state = trans.groupby("state_code").size()
    assert (per_state <= 3).all() and len(per_state) >= 4

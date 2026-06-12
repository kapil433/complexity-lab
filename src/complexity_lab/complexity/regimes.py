"""Hidden Markov fuel regimes (blueprint Project B).

Each state's yearly fuel-mix vector [petrol, diesel, cng, ev, hybrid] is an
observation; a Gaussian HMM infers K latent *energy regimes* shared across all
states, an EM-fitted transition matrix between them, and (via Viterbi) a
"regime calendar" — which regime each state occupied each year.

The HMM (diagonal-covariance Gaussian emissions, scaled forward–backward EM)
is implemented here directly: ~120 lines of NumPy, no extra dependency, and
every step inspectable — which is the point in a research lab.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FUEL_COLS = ["petrol_share", "diesel_share", "cng_share", "ev_share", "hybrid_share"]
_VAR_FLOOR = 1e-4


class GaussianHMM:
    """Diagonal-covariance Gaussian HMM fitted with EM over multiple sequences."""

    def __init__(self, n_states: int, n_iter: int = 200, tol: float = 1e-5, seed: int = 42):
        self.k = n_states
        self.n_iter = n_iter
        self.tol = tol
        self.rng = np.random.default_rng(seed)
        self.startprob_: np.ndarray | None = None
        self.transmat_: np.ndarray | None = None
        self.means_: np.ndarray | None = None
        self.vars_: np.ndarray | None = None
        self.loglik_: float = -np.inf
        self.n_obs_: int = 0

    # ---------- internals ----------
    def _emission_probs(self, x: np.ndarray) -> np.ndarray:
        """P(obs | state) for every (t, state); diagonal Gaussian."""
        diff = x[:, None, :] - self.means_[None, :, :]          # (T, K, D)
        log_p = -0.5 * (
            np.sum(diff**2 / self.vars_[None], axis=2)
            + np.sum(np.log(2 * np.pi * self.vars_), axis=1)[None, :]
        )
        log_p -= log_p.max(axis=1, keepdims=True)
        b = np.exp(log_p)
        return np.maximum(b, 1e-300)

    def _forward_backward(self, x: np.ndarray):
        T = len(x)
        b = self._emission_probs(x)
        alpha = np.zeros((T, self.k))
        c = np.zeros(T)  # scaling factors
        alpha[0] = self.startprob_ * b[0]
        c[0] = alpha[0].sum()
        alpha[0] /= c[0]
        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ self.transmat_) * b[t]
            c[t] = alpha[t].sum()
            alpha[t] /= c[t]
        beta = np.ones((T, self.k))
        for t in range(T - 2, -1, -1):
            beta[t] = (self.transmat_ @ (b[t + 1] * beta[t + 1])) / c[t + 1]
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)
        xi = np.zeros((self.k, self.k))
        for t in range(T - 1):
            num = alpha[t][:, None] * self.transmat_ * (b[t + 1] * beta[t + 1])[None, :]
            xi += num / num.sum()
        # NOTE: c[t] here is P(x_t | x_1..t-1) up to the emission rescaling done in
        # _emission_probs; loglik is therefore comparable across models of the same
        # data (what AIC/BIC selection needs), not an absolute density.
        return gamma, xi, float(np.log(c).sum())

    # ---------- API ----------
    def fit(self, sequences: list[np.ndarray]) -> GaussianHMM:
        data = np.vstack(sequences)
        d = data.shape[1]
        self.n_obs_ = len(data)
        # init: random distinct observations as means, global variance
        idx = self.rng.choice(len(data), size=self.k, replace=False)
        self.means_ = data[idx].copy()
        self.vars_ = np.tile(np.maximum(data.var(axis=0), _VAR_FLOOR), (self.k, 1))
        self.startprob_ = np.full(self.k, 1 / self.k)
        self.transmat_ = np.full((self.k, self.k), 0.1 / max(self.k - 1, 1))
        np.fill_diagonal(self.transmat_, 0.9)

        prev = -np.inf
        for _ in range(self.n_iter):
            g_all, xi_sum = [], np.zeros((self.k, self.k))
            start_acc = np.zeros(self.k)
            ll = 0.0
            for seq in sequences:
                gamma, xi, seq_ll = self._forward_backward(seq)
                g_all.append(gamma)
                xi_sum += xi
                start_acc += gamma[0]
                ll += seq_ll
            gam = np.vstack(g_all)
            self.startprob_ = start_acc / start_acc.sum()
            self.transmat_ = xi_sum / np.maximum(xi_sum.sum(axis=1, keepdims=True), 1e-12)
            w = gam.sum(axis=0)
            self.means_ = (gam.T @ data) / w[:, None]
            diff2 = (data[:, None, :] - self.means_[None]) ** 2
            self.vars_ = np.maximum(
                np.einsum("tk,tkd->kd", gam, diff2) / w[:, None], _VAR_FLOOR
            )
            self.loglik_ = ll
            if abs(ll - prev) < self.tol * abs(prev if prev != -np.inf else 1.0):
                break
            prev = ll
        _ = d
        return self

    def viterbi(self, x: np.ndarray) -> np.ndarray:
        b = np.log(self._emission_probs(x))
        log_t = np.log(np.maximum(self.transmat_, 1e-300))
        T = len(x)
        delta = np.zeros((T, self.k))
        psi = np.zeros((T, self.k), dtype=int)
        delta[0] = np.log(np.maximum(self.startprob_, 1e-300)) + b[0]
        for t in range(1, T):
            cand = delta[t - 1][:, None] + log_t
            psi[t] = cand.argmax(axis=0)
            delta[t] = cand.max(axis=0) + b[t]
        path = np.zeros(T, dtype=int)
        path[-1] = delta[-1].argmax()
        for t in range(T - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        return path

    @property
    def n_params(self) -> int:
        k, d = self.k, self.means_.shape[1]
        return (k - 1) + k * (k - 1) + 2 * k * d

    def aic(self) -> float:
        return 2 * self.n_params - 2 * self.loglik_

    def bic(self) -> float:
        return self.n_params * np.log(self.n_obs_) - 2 * self.loglik_


def _label_regimes(means: np.ndarray, cols: list[str]) -> list[str]:
    """Human label per regime from its most distinctive fuel (vs global mean)."""
    global_mean = means.mean(axis=0)
    labels = []
    for m in means:
        rel = m - global_mean
        fuel = cols[int(np.argmax(rel))].replace("_share", "")
        labels.append(f"{fuel}-heavy")
    # de-duplicate while keeping order
    seen: dict[str, int] = {}
    out = []
    for lab in labels:
        seen[lab] = seen.get(lab, 0) + 1
        out.append(lab if seen[lab] == 1 else f"{lab}-{seen[lab]}")
    return out


def fit_fuel_regimes(
    panel_year: pd.DataFrame,
    k_range: tuple[int, ...] = (2, 3, 4),
    min_years: int = 8,
    n_restarts: int = 4,
) -> dict:
    """Fit HMMs over all states' fuel-mix sequences; select K by BIC.

    Returns regime calendar, labelled means, transition matrix and model table.
    """
    d = panel_year[panel_year["state_code"] != "ALL"].dropna(subset=FUEL_COLS)
    sequences, codes = [], []
    for code, grp in d.sort_values("year").groupby("state_code"):
        x = grp[FUEL_COLS].to_numpy(dtype=float)
        if len(x) >= min_years:
            sequences.append(x)
            codes.append(code)

    table = []
    best: GaussianHMM | None = None
    for k in k_range:
        cand: GaussianHMM | None = None
        for r in range(n_restarts):
            m = GaussianHMM(k, seed=42 + r).fit(sequences)
            if cand is None or m.loglik_ > cand.loglik_:
                cand = m
        table.append({"k": k, "loglik": cand.loglik_, "aic": cand.aic(), "bic": cand.bic()})
        if best is None or cand.bic() < best.bic():
            best = cand

    labels = _label_regimes(best.means_, FUEL_COLS)
    rows = []
    for code, seq in zip(codes, sequences, strict=True):
        years = d[d["state_code"] == code].sort_values("year")["year"].to_numpy()
        path = best.viterbi(seq)
        rows.extend(
            {"state_code": code, "year": int(y), "regime": int(s), "regime_label": labels[s]}
            for y, s in zip(years, path, strict=True)
        )
    calendar = pd.DataFrame(rows)

    means = pd.DataFrame(best.means_, columns=FUEL_COLS)
    means.insert(0, "regime_label", labels)
    transmat = pd.DataFrame(
        best.transmat_, index=labels, columns=labels
    )
    return {
        "model": best,
        "selection": pd.DataFrame(table).set_index("k"),
        "calendar": calendar,
        "regime_means": means,
        "transition_matrix": transmat,
        "n_states_fit": len(codes),
    }


def transition_years(calendar: pd.DataFrame) -> pd.DataFrame:
    """Years in which a state switched regime — to align with policy events."""
    rows = []
    for code, grp in calendar.sort_values("year").groupby("state_code"):
        prev = None
        for _, r in grp.iterrows():
            if prev is not None and r["regime"] != prev["regime"]:
                rows.append(
                    {
                        "state_code": code,
                        "year": int(r["year"]),
                        "from_regime": prev["regime_label"],
                        "to_regime": r["regime_label"],
                    }
                )
            prev = r
    return pd.DataFrame(rows)

"""Agent-based EV-adoption model (vectorised NumPy, no framework dependency).

Each agent is a prospective car buyer in a state. Adoption probability each
step combines:
- intrinsic propensity (income-linked),
- social influence (share of adopters in the agent's state — local contagion),
- infrastructure effect (chargers per capita proxy, supplied per state),
- a global policy boost (subsidy on/off scenarios).

This is deliberately simple and transparent — a sandbox for intuition about
threshold effects and state heterogeneity, not a forecasting engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ABMConfig:
    n_agents_per_state: int = 1000
    n_steps: int = 120  # months
    base_rate: float = 0.0005       # intrinsic monthly adoption hazard
    social_weight: float = 0.04     # contagion strength (q-like)
    infra_weight: float = 0.02      # infrastructure pull
    income_weight: float = 0.5      # how strongly income scales propensity
    policy_boost: float = 0.0       # additive hazard during policy window
    policy_window: tuple[int, int] | None = None  # (start_step, end_step)
    seed: int = 42
    state_income: dict[str, float] = field(default_factory=dict)  # normalised 0..1
    state_infra: dict[str, float] = field(default_factory=dict)   # normalised 0..1


def run_abm(config: ABMConfig) -> pd.DataFrame:
    """Run the model; returns long dataframe (step, state, adopters, adoption_rate)."""
    rng = np.random.default_rng(config.seed)
    states = sorted(set(config.state_income) | set(config.state_infra)) or ["S1"]
    n, k = config.n_agents_per_state, len(states)

    income = np.array([config.state_income.get(s, 0.5) for s in states])  # (k,)
    infra = np.array([config.state_infra.get(s, 0.5) for s in states])    # (k,)

    # Agent heterogeneity: propensity ~ lognormal scaled by state income
    propensity = rng.lognormal(mean=0.0, sigma=0.5, size=(k, n))
    propensity *= (1 + config.income_weight * income)[:, None]

    adopted = np.zeros((k, n), dtype=bool)
    records = []
    for step in range(config.n_steps):
        adopter_share = adopted.mean(axis=1)  # (k,)
        hazard = config.base_rate * propensity
        hazard += config.social_weight * adopter_share[:, None] * propensity
        hazard += config.infra_weight * infra[:, None] * propensity
        if config.policy_window and config.policy_window[0] <= step < config.policy_window[1]:
            hazard += config.policy_boost
        hazard = np.clip(hazard, 0, 1)
        new = (~adopted) & (rng.random((k, n)) < hazard)
        adopted |= new
        for i, s in enumerate(states):
            records.append(
                {
                    "step": step,
                    "state": s,
                    "new_adopters": int(new[i].sum()),
                    "adopters": int(adopted[i].sum()),
                    "adoption_rate": float(adopted[i].mean()),
                }
            )
    return pd.DataFrame(records)


def adoption_summary(result: pd.DataFrame) -> pd.DataFrame:
    """Final adoption and time-to-X% per state."""
    rows = []
    for s, grp in result.groupby("state"):
        grp = grp.sort_values("step")
        final = grp["adoption_rate"].iloc[-1]
        t10 = grp.loc[grp["adoption_rate"] >= 0.10, "step"].min()
        t25 = grp.loc[grp["adoption_rate"] >= 0.25, "step"].min()
        rows.append(
            {
                "state": s,
                "final_adoption": final,
                "t_10pct": t10 if pd.notna(t10) else None,
                "t_25pct": t25 if pd.notna(t25) else None,
            }
        )
    return pd.DataFrame(rows).set_index("state").sort_values("final_adoption", ascending=False)

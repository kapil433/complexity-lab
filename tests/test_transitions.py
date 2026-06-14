import numpy as np
import pandas as pd
import pytest

from complexity_lab.complexity.transitions import (
    absorbing_regimes,
    classify_regimes,
    critical_threshold,
    percolation_curve,
    recent_acceleration_summary,
    regime_transition_matrix,
    threshold_scan,
)


def _edges():
    rng = np.random.default_rng(7)
    makers = [f"M{i}" for i in range(10)]
    states = [f"S{j}" for j in range(20)]
    rows = []
    for s in states:
        weights = rng.dirichlet(np.ones(10) * 0.4) * 10000
        rows.extend({"maker": m, "state_code": s, "regs": w} for m, w in zip(makers, weights, strict=True))
    return pd.DataFrame(rows)


def test_percolation_curve_monotone_and_collapses():
    curve = percolation_curve(_edges(), thresholds=np.array([0.001, 0.05, 0.2, 0.6]))
    assert curve["giant_frac"].iloc[0] == 1.0            # everything connected at tiny threshold
    assert curve["giant_frac"].iloc[-1] < 0.5            # collapsed at 60% share requirement
    assert (curve["giant_frac"].diff().dropna() <= 1e-9).all()  # non-increasing
    tau_c = critical_threshold(curve)
    assert 0.001 < tau_c <= 0.6


def test_threshold_scan_finds_tipping_point():
    # piecewise dynamics: slow constant growth below s=0.10, self-accelerating above
    vals = [0.02]
    for _ in range(50):
        s = vals[-1]
        vals.append(s + (0.002 if s < 0.10 else 0.04 * s))
    res = threshold_scan(pd.Series(vals))
    assert res["hinge_coef"] > 0                          # growth accelerates past tau
    assert res["sse_gain"] > 0.3                          # threshold model beats linear
    assert 0.05 < res["tau"] < 0.20                       # found near the true 0.10


def test_threshold_scan_detects_saturation_as_negative_hinge():
    # logistic: growth-vs-share is concave -> hinge coefficient negative (saturation)
    t = np.arange(60)
    s = pd.Series(0.5 / (1 + np.exp(-0.25 * (t - 30))))
    res = threshold_scan(s)
    assert res["hinge_coef"] < 0
    assert res["sse_gain"] > 0.3


def test_recent_acceleration_is_distinct_from_threshold_tipping():
    panel = pd.DataFrame(
        {
            "state_code": ["A"] * 4 + ["B"] * 4,
            "year": [2022, 2023, 2024, 2025] * 2,
            "ev_share": [0.01, 0.02, 0.03, 0.06, 0.01, 0.03, 0.06, 0.08],
        }
    )

    result = recent_acceleration_summary(panel, "ev_share")

    assert result.loc["A", "momentum_verdict"] == "accelerating"
    assert result.loc["A", "acceleration_pp"] == 2.0
    assert result.loc["B", "momentum_verdict"] == "decelerating"
    assert result.loc["B", "acceleration_pp"] == pytest.approx(-1.0)


def test_regime_classification_and_matrix():
    panel = pd.DataFrame(
        {
            "state_code": ["A"] * 3 + ["B"] * 3,
            "state_name": ["A"] * 3 + ["B"] * 3,
            "year": [2020, 2021, 2022] * 2,
            "petrol_share": [0.9, 0.6, 0.5, 0.5, 0.45, 0.42],
            "diesel_share": [0.08, 0.2, 0.2, 0.3, 0.25, 0.2],
            "cng_share": [0.01, 0.17, 0.2, 0.05, 0.05, 0.08],
            "ev_share": [0.01, 0.03, 0.1, 0.05, 0.15, 0.2],
            "hybrid_share": [0.0, 0.0, 0.0, 0.1, 0.1, 0.1],
        }
    )
    reg = classify_regimes(panel)
    assert reg.loc[(reg.state_code == "A") & (reg.year == 2020), "regime"].iloc[0] == "fossil_dominant"
    assert reg.loc[(reg.state_code == "A") & (reg.year == 2021), "regime"].iloc[0] == "cng_transitioned"
    assert reg.loc[(reg.state_code == "A") & (reg.year == 2022), "regime"].iloc[0] == "ev_emerging"
    assert (reg.loc[reg.state_code == "B", "regime"] == "ev_emerging").all()

    m = regime_transition_matrix(reg)
    assert abs(m.loc["ev_emerging", "ev_emerging"] - 1.0) < 1e-9  # B stays, A enters and stays
    assert absorbing_regimes(m) == ["ev_emerging"]

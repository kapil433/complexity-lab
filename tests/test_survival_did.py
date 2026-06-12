import numpy as np
import pandas as pd

from complexity_lab.analysis.econometrics import did
from complexity_lab.complexity.survival import build_risk_set, discrete_hazard_model, kaplan_meier


def _did_panel(effect=0.02, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=18, freq="MS")
    rows = []
    for state in ["T", "C1", "C2", "C3"]:
        base = 0.01 + (0.002 if state == "T" else 0.0)
        for d in dates:
            y = base + rng.normal(0, 0.001)
            if state == "T" and d >= pd.Timestamp("2024-01-01"):
                y += effect
            rows.append({"state_code": state, "date": d, "share": y})
    return pd.DataFrame(rows)


def test_did_recovers_effect():
    panel = _did_panel(effect=0.02)
    res = did(panel, treated="T", controls=["C1", "C2", "C3"],
              event_date="2024-01-01", value_col="share")
    assert abs(res["att"] - 0.02) < 0.005
    assert res["placebo_rank_p"] <= 0.5  # treated effect at least matches placebo extremes


def test_did_null_effect_small():
    panel = _did_panel(effect=0.0, seed=1)
    res = did(panel, treated="T", controls=["C1", "C2", "C3"],
              event_date="2024-01-01", value_col="share")
    assert abs(res["att"]) < 0.002


def _calendar_and_panel(seed=0):
    """States with higher income switch regime earlier (deterministic-ish)."""
    rng = np.random.default_rng(seed)
    rows, prows = [], []
    for i in range(24):
        income = 50_000 + i * 10_000
        switch_year = 2024 - int(i / 3) + int(rng.integers(0, 2))  # richer -> earlier
        for year in range(2012, 2026):
            regime = 1 if year >= switch_year else 0
            rows.append({"state_code": f"S{i}", "year": year, "regime": regime,
                         "regime_label": "post" if regime else "pre"})
            prows.append({"state_code": f"S{i}", "year": year,
                          "pc_income_inr": income * (1.05 ** (year - 2012))})
    return pd.DataFrame(rows), pd.DataFrame(prows)


def test_hazard_model_finds_income_acceleration():
    cal, panel = _calendar_and_panel()
    risk = build_risk_set(cal, panel, ["pc_income_inr"])
    assert risk["switched"].sum() == 24  # every synthetic state eventually switches
    res = discrete_hazard_model(risk, ["pc_income_inr"])
    assert res["table"].loc["pc_income_inr", "odds_ratio_per_sd"] > 1.5
    assert res["table"].loc["pc_income_inr", "p_value"] < 0.05


def test_kaplan_meier_monotone():
    cal, panel = _calendar_and_panel()
    risk = build_risk_set(cal, panel, ["pc_income_inr"])
    km = kaplan_meier(risk)
    surv = km["survival"].to_numpy()
    assert (np.diff(surv) <= 1e-12).all()
    assert surv[-1] < 0.2

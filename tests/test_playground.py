"""Playground contracts: real results, movable interpretations, no invented rows."""

import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from complexity_lab.config import settings
from complexity_lab.data.autiqa import (
    AutiqaContractError,
    autiqa_status,
    pull_registrations,
    validate_autiqa_registrations,
)
from complexity_lab.data.public_macro import assert_plausible, parse_world_bank_page
from complexity_lab.playground.catalog import experiments
from complexity_lab.playground.interpret import (
    absorption_sentence,
    income_elasticity_sentence,
    scenario_shock_sentence,
    skill_sentence,
    zipf_sentence,
)
from complexity_lab.playground.registry import RUNNERS
from complexity_lab.playground.service import run_experiment, run_validation_suite

ROOT = Path(__file__).parents[1]


def test_fifty_experiments_are_registered_once():
    specs = experiments()
    ids = [spec.experiment_id for spec in specs]

    assert len(specs) == 50
    assert len(ids) == len(set(ids))
    assert set(ids) == set(RUNNERS)
    assert [sum(spec.tier.startswith(prefix) for spec in specs) for prefix in ("1.", "2.", "3.", "4.", "5.")] == [
        10,
        10,
        12,
        8,
        10,
    ]
    for spec in specs:
        assert spec.hypothesis and spec.null_hypothesis and spec.method and spec.do_not_infer
        assert spec.evidence in {"Validation", "Derived", "Estimated", "Simulated"}
        assert spec.limitations and spec.variables


def test_interpretations_change_when_the_knob_changes():
    tight = zipf_sentence(-0.70, 0.8, 30, 0.05)
    loose = zipf_sentence(-0.70, 0.8, 30, 0.50)
    assert "outside the tolerance of 0.05" in tight
    assert "within 0.50" in loose
    assert tight != loose

    on = income_elasticity_sentence(0.4, 0.2, 0.05, True, 100, 20)
    off = income_elasticity_sentence(0.4, 0.2, 0.05, False, 100, 20)
    assert "Year effects are on" in on
    assert "Year effects are off" in off
    assert on != off

    untouched = scenario_shock_sentence(0, 12, 1000, 0)
    shocked = scenario_shock_sentence(10, 12, 1000, 100)
    assert "shock is 0%" in untouched
    assert "not an estimated response" in shocked

    assert "strict" in absorption_sentence(0.95, [])
    assert "lenient" in absorption_sentence(0.50, ["fossil_dominant"])
    assert "clears" in skill_sentence("holt_winters", 0.2, 0.0)
    assert "does not clear" in skill_sentence("holt_winters", 0.2, 0.5)


def test_autiqa_missing_credentials_create_no_rows(monkeypatch):
    monkeypatch.delenv("LAB_AUTIQA_SUPABASE_URL", raising=False)
    monkeypatch.delenv("LAB_AUTIQA_SUPABASE_KEY", raising=False)

    status = autiqa_status()

    assert status.status == "not_configured"
    with pytest.raises(AutiqaContractError, match="not configured"):
        pull_registrations({"MH"})


def test_autiqa_contract_rejects_bad_rows_without_relabelling():
    bad = pd.DataFrame(
        [
            {
                "state_code": "ZZ",
                "year": 2024,
                "month": 1,
                "maker": "Example",
                "fuel": "Electric",
                "count": -3,
            }
        ]
    )

    problems = validate_autiqa_registrations(bad, {"MH", "ALL"})

    assert any("Negative" in problem for problem in problems)
    assert any("Electric" in problem for problem in problems)
    assert any("ZZ" in problem for problem in problems)
    assert bad.loc[0, "fuel"] == "Electric"


def test_autiqa_contract_accepts_a_well_formed_frame():
    good = pd.DataFrame(
        [
            {
                "state_code": "MH",
                "year": 2024,
                "month": 1,
                "maker": "Example",
                "fuel": "EV",
                "count": 10,
            }
        ]
    )

    assert validate_autiqa_registrations(good, {"MH", "ALL"}) == []


def test_world_bank_parser_drops_nulls_and_refuses_a_corrupt_population():
    payload = [
        {"page": 1},
        [
            {
                "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                "countryiso3code": "IND",
                "date": "2020",
                "value": 1_396_387_127,
            },
            {
                "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                "countryiso3code": "IND",
                "date": "2021",
                "value": None,
            },
        ],
    ]

    frame = parse_world_bank_page(payload, "2026-10-24T00:00:00+00:00")

    assert list(frame["year"]) == [2020]
    assert frame.loc[0, "value"] == 1_396_387_127
    corrupt = frame.copy()
    corrupt.loc[0, "value"] = 100
    with pytest.raises(ValueError, match="population"):
        assert_plausible(corrupt)


def _db_or_skip():
    if not settings.db_path.exists():
        pytest.skip("lab.duckdb is not built")
    con = duckdb.connect(str(settings.db_path), read_only=True)
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "experiment_state_year" not in tables:
        con.close()
        pytest.skip("panels are not built")
    return con


def test_validation_suite_holds_on_the_verified_extract():
    con = _db_or_skip()
    try:
        results = {item.experiment_id: item for item in run_validation_suite(con)}
    finally:
        con.close()

    assert set(results) == {f"V{i:02d}" for i in range(1, 11)}
    for item in results.values():
        assert item.status == "ok"
        assert item.metrics != {} or item.experiment_id == "V10"
    for experiment_id in ("V01", "V02", "V04", "V05", "V06", "V08", "V09", "V10"):
        failed = [check["name"] for check in results[experiment_id].failed_checks]
        assert failed == [], results[experiment_id].interpretation
    assert "The check holds." in results["V06"].interpretation
    assert "{'holds'" not in results["V06"].interpretation


def test_shock_and_tolerance_change_computed_results():
    con = _db_or_skip()
    try:
        calm = run_experiment(con, "F07", {"shock_pct": 0})
        shocked = run_experiment(con, "F07", {"shock_pct": 10})
        strict = run_experiment(con, "D04", {"tolerance": 0.05})
        loose = run_experiment(con, "D04", {"tolerance": 0.80})
        effects_on = run_experiment(con, "E06", {"time_effects": True})
        effects_off = run_experiment(con, "E06", {"time_effects": False})
    finally:
        con.close()

    assert calm.status == "ok" and shocked.status == "ok"
    assert calm.metrics["scenario_gap"] == 0
    assert shocked.metrics["scenario_gap"] != 0
    assert calm.interpretation != shocked.interpretation
    assert calm.evidence == "Simulated"
    assert strict.metrics["slope"] == loose.metrics["slope"]
    assert strict.interpretation != loose.interpretation
    if effects_on.status == "ok" and effects_off.status == "ok":
        assert effects_on.interpretation != effects_off.interpretation
        assert "not an elasticity identified" in effects_on.interpretation


def test_every_playground_experiment_runs_without_inventing_a_metric():
    con = _db_or_skip()
    try:
        for spec in experiments():
            result = run_experiment(con, spec.experiment_id)
            assert result.status in {"ok", "blocked"}, spec.experiment_id
            assert result.interpretation
            assert result.evidence == spec.evidence
            if result.status == "blocked":
                assert result.metrics == {}, spec.experiment_id
            blob = json.dumps(result.metrics, default=str).lower()
            assert "placeholder" not in blob and "fabricated" not in blob
            if spec.experiment_id == "D03" and result.status == "ok":
                hhi_up = result.metrics["hhi_change"] > 0
                entropy_down = result.metrics["entropy_change"] < 0
                if hhi_up and entropy_down:
                    assert "became more concentrated" in result.interpretation
                    assert "became less concentrated" not in result.interpretation
            if spec.experiment_id == "C09" and result.status == "ok":
                assert "hinge coefficient" in result.interpretation
    finally:
        con.close()


def test_science_playground_page_imports_the_shell():
    source = (ROOT / "app" / "pages" / "15_Science_Playground.py").read_text(encoding="utf-8")
    assert "render_app_shell(" in source
    assert "run_experiment(" in source

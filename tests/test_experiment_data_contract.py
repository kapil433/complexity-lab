"""Enforce canonical reference usage across registered and published experiments."""

import re
from pathlib import Path

from complexity_lab.experiments.registry import list_experiments
from complexity_lab.experiments.runner import _EXPERIMENT_DEPENDENCIES

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_EXPERIMENT_TERMS = {
    r"(?<!real_)pc_income_inr",
    "ref_state_income ",
    "ref_population ",
    "ref_urbanization ",
    "ref_road_tax ",
    "ref_policy_events ",
    "ref_financing ",
    "ref_dealer_counts ",
}


def test_every_registered_experiment_declares_data_dependencies():
    names = {experiment.name for experiment in list_experiments()}
    assert set(_EXPERIMENT_DEPENDENCIES) == names
    assert all(_EXPERIMENT_DEPENDENCIES[name] for name in names)


def test_experiment_code_does_not_use_superseded_references():
    files = [
        ROOT / "src" / "complexity_lab" / "experiments" / "builtin.py",
        *sorted((ROOT / "experiments").glob("[0-9][0-9][0-9]-*.qmd")),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        found = sorted(
            term for term in FORBIDDEN_EXPERIMENT_TERMS if re.search(term, text)
        )
        assert not found, f"{path.name} uses superseded reference terms: {found}"


def test_canonical_experiment_views_if_database_exists():
    from complexity_lab.config import settings
    from complexity_lab.data.ingest import connect

    if not settings.db_path.exists():
        return
    con = connect(read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert {"experiment_state_year", "experiment_state_context"} <= tables
        assert con.execute("SELECT COUNT(*) FROM experiment_state_context").fetchone()[0] == 36
        columns = {
            row[1]
            for row in con.execute("PRAGMA table_info('experiment_state_year')").fetchall()
        }
        assert {
            "real_pc_income_inr",
            "real_gsdp_growth_pct",
            "broad_credit_per_capita_inr",
            "regs_per_1000_population",
        } <= columns
        assert "pc_income_inr" not in columns
    finally:
        con.close()

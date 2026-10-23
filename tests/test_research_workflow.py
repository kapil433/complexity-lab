from pathlib import Path

import pytest

from complexity_lab.app_state import GlobalContext
from complexity_lab.persistence import (
    delete_research_item,
    delete_saved_view,
    export_research_brief_markdown,
    save_research_item,
    save_view,
    update_research_item_notes,
    update_saved_view_notes,
)
from complexity_lab.research_graph import (
    app_page_for_experiment,
    complete_page_graph,
    get_page_node,
)
from complexity_lab.research_session import ResearchSession
from complexity_lab.science_rigor import rigor_for_method


def test_research_session_round_trips_context_and_rerun_metadata():
    context = GlobalContext(
        2022,
        2026,
        states=("MH", "KA"),
        fuels=("EV",),
        oems=("Tata Motors",),
        coverage="available",
    )
    session = ResearchSession(
        page="Diffusion Lab",
        global_context=context,
        page_params={"state": "MH", "fit_start": 2019, "scenario": "policy-era"},
        method_id="ev-diffusion-states",
        evidence="Estimated",
        data_cutoff="April 2026",
        limitations=("Bass fits are descriptive.",),
        rerun_label="Run Bass scenario",
    )

    payload = session.to_payload()
    restored = ResearchSession.from_payload(payload)

    assert restored == session
    assert payload["global_context"]["states"] == ["MH", "KA"]
    assert restored.restore_query_params() == {
        "from": "2022",
        "to": "2026",
        "source": "vahan",
        "coverage": "available",
        "states": "MH,KA",
        "fuels": "EV",
        "oems": "Tata Motors",
        "page": "Diffusion Lab",
        "method": "ev-diffusion-states",
        "p_state": "MH",
        "p_fit_start": "2019",
        "p_scenario": "policy-era",
    }


def test_page_method_graph_covers_all_streamlit_pages_and_experiment_links():
    root = Path(__file__).parents[1]
    page_files = {path.name for path in (root / "app" / "pages").glob("*.py")}

    graph = complete_page_graph(root)

    assert len(graph) == 17
    assert page_files <= {Path(node.app_path).name for node in graph}
    assert get_page_node("Experiment Gallery").experiment_slugs
    assert app_page_for_experiment("ev-contagion").title == "Network Lab"
    assert app_page_for_experiment("forecast-benchmark").title == "Forecast Studio"
    assert all(node.research_actions for node in graph)
    assert all(node.truth_guardrails for node in graph)


def test_research_memory_can_update_delete_and_export_markdown(tmp_path):
    db_path = tmp_path / "user_lab.duckdb"
    view_id = save_view(
        title="EV state comparison",
        page="Compare and Explore",
        payload={"states": ["MH", "KA"], "fuels": ["EV"]},
        data_cutoff="April 2026",
        notes="Initial comparison",
        path=db_path,
    )
    item_id = save_research_item(
        "hypothesis",
        title="EV share tracks charger density",
        parameters={"driver": "ev_chargers_2025", "outcome": "ev_share"},
        result={"coef": 0.42, "label": "screening only"},
        data_cutoff="April 2026",
        notes="Needs robustness",
        path=db_path,
    )

    update_research_item_notes("hypothesis", item_id, "Reviewed; rerun after refresh", path=db_path)
    update_saved_view_notes(view_id, "Use as Maharashtra/Karnataka EV baseline", path=db_path)
    brief = export_research_brief_markdown(path=db_path)

    assert "# Complexity Lab Research Brief" in brief
    assert "EV share tracks charger density" in brief
    assert "Reviewed; rerun after refresh" in brief
    assert "EV state comparison" in brief
    assert "Use as Maharashtra/Karnataka EV baseline" in brief

    assert delete_research_item("hypothesis", item_id, path=db_path)
    assert delete_saved_view(view_id, path=db_path)
    assert not delete_research_item("hypothesis", item_id, path=db_path)


def test_experiment_parameter_presets_validate_known_experiments():
    from complexity_lab.experiments.params import (
        default_params,
        dependency_gate,
        parameter_schema_for,
        preset_options_for,
        validate_params,
    )

    schema = parameter_schema_for("ev-threshold")
    assert schema["min_share"].default == 0.01
    assert preset_options_for("ev-threshold")
    assert default_params("ev-threshold")["min_share"] == 0.01
    assert validate_params("ev-threshold", {"min_share": "0.03"}) == {"min_share": 0.03}

    with pytest.raises(ValueError, match="min_share"):
        validate_params("ev-threshold", {"min_share": -1})

    missing_gate = dependency_gate(
        "suv-transition",
        available_tables={"panel_state_month", "experiment_state_year"},
    )
    assert not missing_gate.available
    assert "ws_segment_month" in missing_gate.message


def test_science_rigor_registry_labels_claim_boundaries_and_robustness():
    causal = rigor_for_method("hypothesis-screen")
    assert causal.claim_type == "observational_screen"
    assert "not causal" in causal.claim_boundary.lower()
    assert causal.robustness_checks

    shock = rigor_for_method("shock-scenario")
    assert shock.evidence == "Simulated"
    assert "assumptions" in shock.claim_boundary.lower()


def test_quarto_template_and_index_expose_research_workflow():
    root = Path(__file__).parents[1]
    template = (root / "experiments" / "_template.qmd").read_text(encoding="utf-8")
    index = (root / "experiments" / "index.qmd").read_text(encoding="utf-8")
    home = (root / "index.qmd").read_text(encoding="utf-8")
    quarto = (root / "_quarto.yml").read_text(encoding="utf-8")

    for heading in (
        "## Data Contract",
        "## Method",
        "## Robustness",
        "## Limits And Do-Not-Claim",
        "## Reproduce",
    ):
        assert heading in template

    assert "App page" in index
    assert "CLI slug" in index
    assert "Interactive lab" in home
    assert "researcher-on-the-go" in home.lower()
    assert "Interactive Lab" in quarto

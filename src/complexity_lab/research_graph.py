"""Research navigation graph connecting app pages, cards, experiments, and notebooks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageNode:
    title: str
    app_path: str
    section: str
    card_ids: tuple[str, ...] = ()
    experiment_slugs: tuple[str, ...] = ()
    notebooks: tuple[str, ...] = ()
    research_actions: tuple[str, ...] = ()
    truth_guardrails: tuple[str, ...] = ()
    page_params: tuple[str, ...] = ()


COMMON_GUARDRAILS = (
    "Use matched YTD for partial-year annual comparisons.",
    "Treat policy events as context unless an identification design is explicit.",
)


PAGE_GRAPH: tuple[PageNode, ...] = (
    PageNode(
        "Market Brief",
        "app/Home.py",
        "Observe",
        card_ids=("descriptive-baseline",),
        experiment_slugs=("descriptive-baseline",),
        notebooks=("experiments/001-descriptive-baseline.qmd",),
        research_actions=("Choose a research path", "Open relevant dossier", "Save the current market brief"),
        truth_guardrails=COMMON_GUARDRAILS,
    ),
    PageNode(
        "Market Pulse",
        "app/pages/0_Macro_Dashboard.py",
        "Observe",
        card_ids=("descriptive-baseline", "phase-transitions"),
        experiment_slugs=("descriptive-baseline", "phase-transitions"),
        notebooks=("experiments/001-descriptive-baseline.qmd", "experiments/005-phase-transitions.qmd"),
        research_actions=("Diagnose market structure", "Drill into state/OEM contributors"),
        truth_guardrails=COMMON_GUARDRAILS,
    ),
    PageNode(
        "Compare and Explore",
        "app/pages/1_Explorer.py",
        "Observe",
        card_ids=("descriptive-baseline", "hypothesis-tester"),
        experiment_slugs=("descriptive-baseline", "hypothesis-screen"),
        research_actions=("Save comparison", "Promote scatter relationship to Causal Lab"),
        truth_guardrails=COMMON_GUARDRAILS,
        page_params=("metric", "normalization", "compare"),
    ),
    PageNode(
        "Network Lab",
        "app/pages/2_Networks.py",
        "Explain",
        card_ids=("oem-state-network", "ev-contagion", "adoption-network-horserace"),
        experiment_slugs=("oem-state-network", "ev-contagion", "adoption-network-horserace"),
        notebooks=(
            "experiments/003-oem-state-network.qmd",
            "experiments/007-ev-contagion.qmd",
            "experiments/009-adoption-network-horserace.qmd",
        ),
        research_actions=("Inspect ego network", "Compare communities across eras", "Run contagion robustness"),
        truth_guardrails=COMMON_GUARDRAILS + ("Network synchrony is not causal spillover.",),
    ),
    PageNode(
        "Diffusion Lab",
        "app/pages/3_Diffusion_Lab.py",
        "Explain",
        card_ids=("ev-diffusion-states", "shev-counterfactual"),
        experiment_slugs=("ev-diffusion-states", "bass-scenario", "shev-counterfactual"),
        notebooks=("experiments/002-ev-diffusion-states.qmd", "experiments/013-shev-counterfactual.qmd"),
        research_actions=("Fit state adoption curve", "Save scenario", "Send assumptions to Forecast Studio"),
        truth_guardrails=COMMON_GUARDRAILS + ("Do not fit Strong Hybrid as a continuous pre-2024 curve.",),
    ),
    PageNode(
        "Causal Lab",
        "app/pages/4_Hypothesis_Tester.py",
        "Explain",
        card_ids=("hypothesis-tester", "shev-isolation"),
        experiment_slugs=("hypothesis-screen", "shev-isolation"),
        notebooks=("experiments/010-shev-isolation.qmd",),
        research_actions=("Screen a panel hypothesis", "Check covariate eligibility", "Save a falsifiable spec"),
        truth_guardrails=COMMON_GUARDRAILS + ("Regression screening is not causal identification.",),
    ),
    PageNode(
        "Wholesale and Channel",
        "app/pages/5_Wholesale.py",
        "Observe",
        card_ids=("wholesale-retail-nowcast", "suv-transition"),
        experiment_slugs=("wholesale-retail-nowcast", "suv-transition"),
        notebooks=("experiments/004-wholesale-retail-nowcast.qmd", "experiments/012-suv-transition.qmd"),
        research_actions=("Nowcast retail", "Diagnose channel stress", "Open SUV transition evidence"),
        truth_guardrails=("Wholesale has no fuel cut.", "Use full coverage from 2022-04 onward."),
    ),
    PageNode(
        "Transitions and Regimes",
        "app/pages/6_Phase_Transitions.py",
        "Explain",
        card_ids=("phase-transitions", "ev-threshold", "fuel-regimes", "regime-survival"),
        experiment_slugs=("phase-transitions", "ev-threshold", "fuel-regimes", "regime-survival"),
        notebooks=(
            "experiments/005-phase-transitions.qmd",
            "experiments/006-ev-threshold.qmd",
            "experiments/008-fuel-regimes.qmd",
            "experiments/011-regime-survival.qmd",
        ),
        research_actions=("Inspect threshold sensitivity", "Compare HMM and rule regimes", "Run survival framing"),
        truth_guardrails=COMMON_GUARDRAILS + ("Do not conflate acceleration, tipping, and causal regime switching.",),
    ),
    PageNode(
        "Forecast Studio",
        "app/pages/7_Forecast_Studio.py",
        "Anticipate",
        card_ids=("forecast",),
        experiment_slugs=("forecast-benchmark",),
        research_actions=("Run rolling-origin benchmark", "Save forecast vintage", "Compare against naive baseline"),
        truth_guardrails=COMMON_GUARDRAILS + ("Forecasts are estimates, not policy counterfactuals.",),
    ),
    PageNode(
        "Scenario and Shock Lab",
        "app/pages/8_Shock_Lab.py",
        "Anticipate",
        card_ids=("shock-lab",),
        experiment_slugs=("shock-scenario",),
        research_actions=("Run scenario preset", "Audit assumptions", "Save Monte Carlo card"),
        truth_guardrails=("Scenarios are simulated assumptions, not forecasts.", "Wholesale calibration remains local-only."),
    ),
    PageNode(
        "Reference Lab",
        "app/pages/9_Reference_Lab.py",
        "System",
        research_actions=("Check covariate eligibility", "Inspect source quality", "Route safe controls to Causal Lab"),
        truth_guardrails=("Reference quality is separate from evidence tier.", "Sparse snapshots are not annual panels."),
    ),
    PageNode(
        "State Intelligence",
        "app/pages/10_State_Intelligence.py",
        "Observe",
        card_ids=("ev-threshold", "ev-diffusion-states", "fuel-regimes"),
        experiment_slugs=("ev-threshold", "ev-diffusion-states", "fuel-regimes"),
        research_actions=("Run state threshold", "Open peer comparison", "Inspect regime history"),
        truth_guardrails=COMMON_GUARDRAILS,
    ),
    PageNode(
        "OEM and Model Intelligence",
        "app/pages/11_OEM_Model_Intelligence.py",
        "Observe",
        card_ids=("oem-state-network", "suv-transition"),
        experiment_slugs=("oem-state-network", "suv-transition"),
        research_actions=("Open OEM ego network", "Inspect state strength", "Review model lifecycle"),
        truth_guardrails=("Wholesale model evidence is dispatch volume, not retail registrations.",),
    ),
    PageNode(
        "Experiment Gallery",
        "app/pages/12_Experiment_Gallery.py",
        "Research",
        experiment_slugs=(
            "descriptive-baseline",
            "ev-diffusion-states",
            "oem-state-network",
            "wholesale-retail-nowcast",
            "phase-transitions",
            "ev-threshold",
            "ev-contagion",
            "fuel-regimes",
            "adoption-network-horserace",
            "shev-isolation",
            "regime-survival",
            "suv-transition",
            "shev-counterfactual",
            "hypothesis-screen",
            "forecast-benchmark",
            "shock-scenario",
            "bass-scenario",
        ),
        research_actions=("Launch preset", "Compare run matrix", "Save result to inbox"),
        truth_guardrails=("Dependency gates must fail closed.", "Private wholesale artifacts stay private."),
    ),
    PageNode(
        "Saved Questions",
        "app/pages/13_Saved_Questions.py",
        "Research",
        research_actions=("Restore context", "Rerun with current cutoff", "Export research brief"),
        truth_guardrails=("Saved cards preserve original cutoff; reruns may change with data vintage.",),
    ),
    PageNode(
        "Data Health and Refresh",
        "app/pages/14_Data_Health.py",
        "System",
        research_actions=("Check freshness", "Inspect dependency gates", "Run refresh checklist"),
        truth_guardrails=("The data truth contract wins over older chart text or comments.",),
    ),
)


def complete_page_graph(root: Path | None = None) -> tuple[PageNode, ...]:
    if root is None:
        return PAGE_GRAPH
    existing = {node.app_path for node in PAGE_GRAPH}
    expected = {"app/Home.py"} | {
        path.relative_to(root).as_posix() for path in (root / "app" / "pages").glob("*.py")
    }
    missing = expected - existing
    if missing:
        raise ValueError(f"Missing page graph entries: {', '.join(sorted(missing))}")
    return PAGE_GRAPH


def get_page_node(title: str) -> PageNode:
    normalized = title.strip().lower()
    for node in PAGE_GRAPH:
        if node.title.lower() == normalized:
            return node
    raise KeyError(f"Unknown page: {title}")


def app_page_for_experiment(slug: str) -> PageNode:
    for node in PAGE_GRAPH:
        if slug in node.experiment_slugs:
            return node
    raise KeyError(f"No app page mapped for experiment: {slug}")


def experiment_to_page_index() -> dict[str, PageNode]:
    return {
        slug: node
        for node in PAGE_GRAPH
        for slug in node.experiment_slugs
    }

"""Claim boundaries and robustness expectations for research methods."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MethodRigor:
    method_id: str
    evidence: str
    claim_type: str
    claim_boundary: str
    robustness_checks: tuple[str, ...]


DEFAULT_RIGOR = MethodRigor(
    method_id="default",
    evidence="Estimated",
    claim_type="model_summary",
    claim_boundary="Model output summarizes observed history and should not be read as causal without an identification design.",
    robustness_checks=("Check sensitivity to period, filters, and data vintage.",),
)


RIGOR: dict[str, MethodRigor] = {
    "descriptive-baseline": MethodRigor(
        "descriptive-baseline",
        "Derived",
        "descriptive_accounting",
        "Describes market structure; does not explain causes of observed movement.",
        ("Matched-YTD comparison", "All-India observed row boundary", "Concentration trend over time"),
    ),
    "hypothesis-screen": MethodRigor(
        "hypothesis-screen",
        "Estimated",
        "observational_screen",
        "Panel regression is not causal identification; use it to prioritize hypotheses.",
        ("Missingness check", "Within-state variation check", "Clustered standard errors", "Lag sensitivity"),
    ),
    "shev-isolation": MethodRigor(
        "shev-isolation",
        "Estimated",
        "natural_experiment_directional",
        "One-state DiD is directional and must be read with placebo and window sensitivity.",
        ("Placebo controls", "Pre/post window sensitivity", "Policy-overlap audit"),
    ),
    "forecast-benchmark": MethodRigor(
        "forecast-benchmark",
        "Estimated",
        "forecast_backtest",
        "Forecasts are evaluated projections, not counterfactual policy claims.",
        ("Seasonal-naive benchmark", "Rolling-origin holdouts", "Interval coverage"),
    ),
    "shock-scenario": MethodRigor(
        "shock-scenario",
        "Simulated",
        "scenario_simulation",
        "Scenario results depend on explicit assumptions and are not forecasts.",
        ("Baseline comparison", "Monte Carlo or parameter sweep", "Calibration-source disclosure"),
    ),
    "ev-threshold": MethodRigor(
        "ev-threshold",
        "Estimated",
        "threshold_diagnostic",
        "Thresholds separate acceleration from feedback; they do not prove causal tipping.",
        ("Era windows", "Smoothing sensitivity", "SSE-gain threshold", "Matched-YTD momentum split"),
    ),
    "ev-contagion": MethodRigor(
        "ev-contagion",
        "Estimated",
        "spatial_synchrony",
        "Moran's I and cascades test synchrony, not causal spillover.",
        ("Threshold sweep", "Spatial null", "Seed sensitivity"),
    ),
    "fuel-regimes": MethodRigor(
        "fuel-regimes",
        "Estimated",
        "latent_state_model",
        "HMM regimes summarize latent market states; labels are model-dependent.",
        ("BIC state selection", "Persistence check", "Policy-event overlay"),
    ),
    "regime-survival": MethodRigor(
        "regime-survival",
        "Estimated",
        "hazard_model",
        "Survival estimates are low-N directional evidence unless intervals are wide and explicit.",
        ("Kaplan-Meier baseline", "Covariate sensitivity", "Event-count disclosure"),
    ),
    "wholesale-retail-nowcast": MethodRigor(
        "wholesale-retail-nowcast",
        "Estimated",
        "nowcast",
        "Wholesale nowcasts retail totals; wholesale has no fuel cut and is local-only.",
        ("Full-coverage era only", "Seasonal-naive benchmark", "Mapped-volume disclosure"),
    ),
    "suv-transition": MethodRigor(
        "suv-transition",
        "Estimated",
        "segment_transition",
        "SUV transition is dispatch-mix evidence, not revealed retail preference.",
        ("Full-coverage era only", "City archetype stability", "OEM mover class sensitivity"),
    ),
    "bass-scenario": MethodRigor(
        "bass-scenario",
        "Estimated",
        "diffusion_fit",
        "Bass parameters are descriptive and sensitive to policy shocks and early adoption noise.",
        ("Fit-window sensitivity", "Holdout comparison", "Minimum-volume threshold"),
    ),
}


ALIASES = {
    "ev-diffusion-states": "bass-scenario",
    "shev-counterfactual": "shock-scenario",
    "phase-transitions": "ev-threshold",
    "adoption-network-horserace": "ev-contagion",
    "oem-state-network": "descriptive-baseline",
}


def rigor_for_method(method_id: str) -> MethodRigor:
    return RIGOR.get(method_id, RIGOR.get(ALIASES.get(method_id, ""), DEFAULT_RIGOR))

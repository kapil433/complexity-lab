"""Typed parameter schemas and presets for interactive experiment launching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from complexity_lab.experiments.runner import _EXPERIMENT_DEPENDENCIES

ParamType = Literal["int", "float", "str", "bool"]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    kind: ParamType
    default: int | float | str | bool
    help: str
    min_value: int | float | None = None
    max_value: int | float | None = None

    def coerce(self, value: Any) -> int | float | str | bool:
        if self.kind == "bool":
            if isinstance(value, bool):
                coerced = value
            elif isinstance(value, str):
                coerced = value.strip().lower() in {"1", "true", "yes", "y"}
            else:
                coerced = bool(value)
        elif self.kind == "int":
            coerced = int(value)
        elif self.kind == "float":
            coerced = float(value)
        else:
            coerced = str(value)

        if isinstance(coerced, (int, float)) and not isinstance(coerced, bool):
            if self.min_value is not None and coerced < self.min_value:
                raise ValueError(f"{self.name} must be at least {self.min_value}")
            if self.max_value is not None and coerced > self.max_value:
                raise ValueError(f"{self.name} must be at most {self.max_value}")
        return coerced


@dataclass(frozen=True)
class ExperimentPreset:
    name: str
    description: str
    params: dict[str, int | float | str | bool]


@dataclass(frozen=True)
class DependencyGate:
    available: bool
    missing: tuple[str, ...]
    message: str


SCHEMAS: dict[str, tuple[ParamSpec, ...]] = {
    "ev-diffusion-states": (
        ParamSpec("min_total", "Minimum EV registrations", "int", 1000, "Exclude states before enough EV evidence exists.", 0),
    ),
    "ev-threshold": (
        ParamSpec("min_share", "Minimum EV share scanned", "float", 0.01, "Smallest share at which a threshold is considered.", 0.0, 1.0),
    ),
    "phase-transitions": (
        ParamSpec("absorbing_threshold", "Absorbing regime threshold", "float", 0.9, "Transition probability used to flag sticky regimes.", 0.5, 1.0),
    ),
    "fuel-regimes": (
        ParamSpec("max_states", "Maximum HMM states", "int", 4, "Upper bound for BIC model selection.", 2, 6),
    ),
    "shev-counterfactual": (
        ParamSpec("tax_elasticity", "Tax elasticity", "float", -1.2, "Assumed response to GST/tax parity.", -5.0, 0.0),
    ),
    "forecast-benchmark": (
        ParamSpec("horizon", "Forecast horizon", "int", 12, "Months held out or projected.", 1, 36),
        ParamSpec("min_train_months", "Minimum train months", "int", 48, "Minimum history before a model can compete.", 24),
    ),
    "shock-scenario": (
        ParamSpec("months", "Scenario months", "int", 12, "Length of simulated shock window.", 1, 36),
        ParamSpec("demand_shock", "Demand shock", "float", -0.15, "Initial demand deviation from baseline.", -1.0, 1.0),
    ),
    "bass-scenario": (
        ParamSpec("min_total", "Minimum registrations", "int", 1000, "Minimum adoption evidence before fitting.", 0),
        ParamSpec("projection_months", "Projection months", "int", 36, "Scenario projection length.", 1, 120),
    ),
    "hypothesis-screen": (
        ParamSpec("min_year", "First panel year", "int", 2015, "Lower bound for screening panel.", 2012, 2026),
    ),
}


PRESETS: dict[str, tuple[ExperimentPreset, ...]] = {
    "ev-threshold": (
        ExperimentPreset("Default threshold scan", "Scan all EV adoption history from 1% share.", {"min_share": 0.01}),
        ExperimentPreset("Stricter signal", "Ignore pre-takeoff noise below 3% EV share.", {"min_share": 0.03}),
    ),
    "ev-diffusion-states": (
        ExperimentPreset("Research default", "Fit states with at least 1,000 EV registrations.", {"min_total": 1000}),
        ExperimentPreset("Early-state scan", "Include smaller states for exploratory review.", {"min_total": 250}),
    ),
    "phase-transitions": (
        ExperimentPreset("Sticky regimes", "Flag regimes that self-transition at 90%+.", {"absorbing_threshold": 0.9}),
    ),
    "forecast-benchmark": (
        ExperimentPreset("12-month benchmark", "Standard annual forecast comparison.", {"horizon": 12, "min_train_months": 48}),
    ),
    "shock-scenario": (
        ExperimentPreset("Demand shock", "Moderate demand drop with one-year recovery window.", {"months": 12, "demand_shock": -0.15}),
    ),
    "bass-scenario": (
        ExperimentPreset("EV launch timing", "Fit adoption and project three years ahead.", {"min_total": 1000, "projection_months": 36}),
    ),
    "hypothesis-screen": (
        ExperimentPreset("Post-2015 panel", "Screen a modern-policy-era panel.", {"min_year": 2015}),
    ),
}


def parameter_schema_for(experiment: str) -> dict[str, ParamSpec]:
    return {spec.name: spec for spec in SCHEMAS.get(experiment, ())}


def preset_options_for(experiment: str) -> tuple[ExperimentPreset, ...]:
    return PRESETS.get(experiment, (ExperimentPreset("No-parameter run", "Use the experiment defaults.", {}),))


def default_params(experiment: str) -> dict[str, int | float | str | bool]:
    return {spec.name: spec.default for spec in SCHEMAS.get(experiment, ())}


def validate_params(experiment: str, params: dict[str, Any]) -> dict[str, int | float | str | bool]:
    schema = parameter_schema_for(experiment)
    validated = default_params(experiment)
    for key, value in params.items():
        if key not in schema:
            raise ValueError(f"Unknown parameter for {experiment}: {key}")
        validated[key] = schema[key].coerce(value)
    return validated


def dependency_gate(experiment: str, available_tables: set[str]) -> DependencyGate:
    dependencies = tuple(_EXPERIMENT_DEPENDENCIES.get(experiment, ()))
    missing = tuple(sorted(dependency for dependency in dependencies if dependency not in available_tables))
    if missing:
        return DependencyGate(
            available=False,
            missing=missing,
            message=f"Missing required table(s): {', '.join(missing)}",
        )
    return DependencyGate(
        available=True,
        missing=(),
        message="All registered data dependencies are available.",
    )

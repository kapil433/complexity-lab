"""Result and parameter types for the science playground.

Every run returns the hypothesis, the numbers actually computed, the checks
that passed or failed, and an interpretation that is allowed to change when
a parameter changes. A blocked run returns the reason and no invented metric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Knob:
    """One control the playground exposes for an experiment."""

    name: str
    label: str
    kind: str
    default: Any
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    help: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    title: str
    tier: str
    hypothesis: str
    null_hypothesis: str
    evidence: str
    method: str
    variables: tuple[str, ...]
    limitations: tuple[str, ...]
    do_not_infer: str
    knobs: tuple[Knob, ...] = ()


@dataclass
class PlaygroundResult:
    experiment_id: str
    title: str
    tier: str
    hypothesis: str
    null_hypothesis: str
    evidence: str
    method: str
    parameters: dict[str, Any]
    status: str
    metrics: dict[str, Any]
    checks: list[dict[str, Any]]
    interpretation: str
    do_not_infer: str
    data_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    chart: str = "table"
    chart_x: str | None = None
    chart_y: str | None = None
    chart_color: str | None = None
    frame: pd.DataFrame | None = field(default=None)

    @property
    def failed_checks(self) -> list[dict[str, Any]]:
        return [item for item in self.checks if not item["passed"]]


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def resolve_params(spec: ExperimentSpec, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge knob defaults with an explicit override. Unknown keys are rejected."""
    params = {knob.name: knob.default for knob in spec.knobs}
    overrides = overrides or {}
    unknown = sorted(set(overrides) - set(params))
    if unknown:
        known = ", ".join(sorted(params)) or "(none)"
        raise ValueError(f"Unknown parameters {unknown} for {spec.experiment_id}. Known: {known}")
    params.update(overrides)
    return params

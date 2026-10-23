"""Run one playground experiment, or the validation suite, against an open database."""

from __future__ import annotations

import duckdb

from complexity_lab.playground.catalog import experiment_by_id, experiments
from complexity_lab.playground.models import PlaygroundResult, resolve_params
from complexity_lab.playground.registry import RUNNERS
from complexity_lab.playground.runners import (
    association,
    complexity,
    descriptive,
    forecast,
    validation,
)

_LOADED = (association, complexity, descriptive, forecast, validation)


def run_experiment(
    con: duckdb.DuckDBPyConnection,
    experiment_id: str,
    overrides: dict | None = None,
) -> PlaygroundResult:
    """Execute one pre-specified experiment. Unknown parameters are rejected."""
    spec = experiment_by_id(experiment_id)
    if experiment_id not in RUNNERS:
        loaded = ", ".join(module.__name__.rsplit(".", 1)[-1] for module in _LOADED)
        raise KeyError(f"No executor is registered for {experiment_id}. Loaded modules: {loaded}")
    params = resolve_params(spec, overrides)
    return RUNNERS[experiment_id](con, spec, params)


def run_validation_suite(con: duckdb.DuckDBPyConnection) -> list[PlaygroundResult]:
    """Run V01–V10 at their default alarm bars."""
    return [
        run_experiment(con, spec.experiment_id)
        for spec in experiments()
        if spec.experiment_id.startswith("V")
    ]

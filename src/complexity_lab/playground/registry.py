"""Registry of playground executors. Importing a runner module registers it."""

from __future__ import annotations

from collections.abc import Callable

from complexity_lab.playground.models import PlaygroundResult

Runner = Callable[..., PlaygroundResult]

RUNNERS: dict[str, Runner] = {}


def playground_experiment(experiment_id: str) -> Callable[[Runner], Runner]:
    def deco(fn: Runner) -> Runner:
        if experiment_id in RUNNERS:
            raise ValueError(f"Playground experiment '{experiment_id}' is already registered")
        RUNNERS[experiment_id] = fn
        return fn

    return deco

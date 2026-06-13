"""Experiment registry.

An experiment is a named function ``fn(con, out_dir, **params) -> dict`` that
reads from the DuckDB connection, writes artifacts (parquet/figures/json)
into ``out_dir`` and returns a metrics dict. Register with the decorator:

    @experiment("my-experiment", description="What it tests")
    def my_experiment(con, out_dir, **params):
        ...
        return {"key_metric": 0.42}
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Experiment:
    name: str
    fn: Callable
    description: str = ""
    data_dependencies: tuple[str, ...] = ()


_REGISTRY: dict[str, Experiment] = {}


def experiment(
    name: str, description: str = "", data_dependencies: tuple[str, ...] = ()
) -> Callable:
    def deco(fn: Callable) -> Callable:
        if name in _REGISTRY:
            raise ValueError(f"Experiment '{name}' already registered")
        _REGISTRY[name] = Experiment(
            name=name,
            fn=fn,
            description=description,
            data_dependencies=data_dependencies,
        )
        return fn

    return deco


def get_experiment(name: str) -> Experiment:
    _ensure_builtins_loaded()
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown experiment '{name}'. Known: {known}")
    return _REGISTRY[name]


def list_experiments() -> list[Experiment]:
    _ensure_builtins_loaded()
    return sorted(_REGISTRY.values(), key=lambda e: e.name)


def _ensure_builtins_loaded() -> None:
    # Import for side effect: registers the built-in experiments.
    from complexity_lab.experiments import builtin  # noqa: F401

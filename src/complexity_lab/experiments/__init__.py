"""Experiment framework: registry + runner producing reproducible artifacts."""

from complexity_lab.experiments.registry import experiment, get_experiment, list_experiments

__all__ = ["experiment", "get_experiment", "list_experiments"]

"""Interactive science playground: hypotheses, knobs, checks, and interpretations."""

from complexity_lab.playground.catalog import experiment_by_id, experiments
from complexity_lab.playground.service import run_experiment, run_validation_suite

__all__ = [
    "experiment_by_id",
    "experiments",
    "run_experiment",
    "run_validation_suite",
]

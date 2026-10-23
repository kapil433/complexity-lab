"""Importing this package registers every playground executor."""

from complexity_lab.playground.runners import (
    association,
    complexity,
    descriptive,
    forecast,
    validation,
)

__all__ = ["association", "complexity", "descriptive", "forecast", "validation"]

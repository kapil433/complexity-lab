"""Shared constructors for playground results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from complexity_lab.playground.models import ExperimentSpec, PlaygroundResult, check

ALL_INDIA = (
    "All India is the pre-aggregated Vahan series. State rows are not added up to replace it."
)
INCOME = (
    "Real per-capita income is RBI Handbook Table 20 at constant 2011-12 prices, "
    "a financial-year series joined to the calendar year in which that financial year starts."
)
POPULATION = (
    "The population denominator is interpolated between anchors and labelled estimate. "
    "The urban share is the 2011 census share held fixed, not an annual urbanisation series."
)
FUEL_PRICE = (
    "State fuel prices are approximate annual averages: a compiled Delhi series plus "
    "era-anchored capital-city differentials. They are not daily pump prices."
)
CREDIT = (
    "Broad credit depth is scheduled-bank personal loans divided by the estimated population. "
    "It is not vehicle-finance penetration, NBFC lending, or captive OEM finance."
)
HYBRID = (
    "Strong Hybrid counts before 2024 are a classification break. Do not read them as a "
    "continuous adoption curve."
)


def partial_note(params: dict[str, Any]) -> tuple[str, bool] | None:
    """Return a note, and whether it should fail a check.

    A panel that sets ``year_end`` to 2026 fails the check. A single-year
    snapshot is labelled and left as a year-to-date view. A matched-month
    comparison (it has ``through_month``) is already explicit.
    """
    message = (
        "2026 is partial in the current Vahan bundle (January–April). "
        "An annual total that includes 2026 is not a full-year total."
    )
    year_end = params.get("year_end")
    if isinstance(year_end, int) and year_end >= 2026:
        return message, True
    year = params.get("year")
    if isinstance(year, int) and year >= 2026 and "through_month" not in params:
        return message, False
    return None


def finish(
    spec: ExperimentSpec,
    params: dict[str, Any],
    *,
    status: str,
    metrics: dict[str, Any],
    checks: list[dict[str, Any]],
    interpretation: str,
    frame: pd.DataFrame | None = None,
    chart: str = "table",
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    notes: Sequence[str] = (),
) -> PlaygroundResult:
    note_list = [note for note in notes if note]
    extra = partial_note(params)
    if extra is not None:
        message, fail = extra
        if message not in note_list:
            note_list.append(message)
        if fail and status == "ok":
            checks = [*checks, check("complete_year", False, message)]
    return PlaygroundResult(
        experiment_id=spec.experiment_id,
        title=spec.title,
        tier=spec.tier,
        hypothesis=spec.hypothesis,
        null_hypothesis=spec.null_hypothesis,
        evidence=spec.evidence,
        method=spec.method,
        parameters=dict(params),
        status=status,
        metrics=metrics,
        checks=list(checks),
        interpretation=interpretation,
        do_not_infer=spec.do_not_infer,
        data_notes=tuple(note_list),
        limitations=spec.limitations,
        chart=chart,
        chart_x=x,
        chart_y=y,
        chart_color=color,
        frame=frame,
    )


def blocked(
    spec: ExperimentSpec,
    params: dict[str, Any],
    reason: str,
    *,
    notes: Sequence[str] = (),
) -> PlaygroundResult:
    return finish(
        spec,
        params,
        status="blocked",
        metrics={},
        checks=[check("estimable", False, reason)],
        interpretation=reason,
        notes=notes,
    )

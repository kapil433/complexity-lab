"""Interpretation sentences.

These functions are pure: the same numbers and the same knob produce the same
sentence, and a different knob is allowed to change the sentence. They do not
upgrade an association, a forecast, or a scenario into a cause.
"""

from __future__ import annotations

import math


def _finite(value: float | None) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def association_sentence(
    x_name: str,
    y_name: str,
    rho: float,
    p_value: float,
    alpha: float,
    n: int,
    extra: str = "",
) -> str:
    if not _finite(rho) or not _finite(p_value):
        return f"The association between {x_name} and {y_name} was not computed."
    if rho > 0.05:
        direction = "positive"
    elif rho < -0.05:
        direction = "negative"
    else:
        direction = "essentially flat"
    magnitude = abs(rho)
    # Cuts are stated in the sentence so the adjective is auditable.
    if magnitude < 0.30:
        strength = "weak"
    elif magnitude < 0.50:
        strength = "moderate"
    else:
        strength = "strong"
    decision = "rejects" if p_value < alpha else "does not reject"
    extra_text = f"{extra} " if extra else ""
    return (
        f"Spearman rho between {x_name} and {y_name} is {rho:.2f} "
        f"({strength} {direction} association; |rho| cuts at 0.30 and 0.50) on {n} observations. "
        f"At alpha {alpha:.2f}, the test {decision} the null of no monotonic association. "
        f"{extra_text}"
        "This is an association. It is not a cause, and the p-value is not a policy effect."
    )


def income_elasticity_sentence(
    coef: float,
    p_value: float,
    alpha: float,
    time_effects: bool,
    n: int,
    n_states: int,
) -> str:
    if not _finite(coef) or not _finite(p_value):
        return "The within-state income coefficient was not estimated."
    effects = "with year effects" if time_effects else "without year effects"
    decision = "rejects" if p_value < alpha else "does not reject"
    if time_effects:
        identifying = (
            "Year effects are on, so the coefficient uses only each state's income "
            "deviation from the common year. It is not the cross-state income gradient."
        )
    else:
        identifying = (
            "Year effects are off, so national shocks that move income and registrations "
            "in the same year remain inside the coefficient."
        )
    return (
        f"{effects.capitalize()}, a 1% higher real per-capita income is associated with "
        f"about {coef:.2f}% higher registrations "
        f"(n={n}, states={n_states}). At alpha {alpha:.2f}, the test {decision} a zero "
        f"coefficient. {identifying} "
        "Fiscal-year income is joined to the calendar year in which that financial year "
        "starts. This is not an elasticity identified by a natural experiment."
    )


def scenario_shock_sentence(shock_pct: float, horizon: int, baseline_sum: float, gap: float) -> str:
    if abs(shock_pct) < 1e-9:
        return (
            f"The demand shock is 0%. Over {horizon} months the scenario is the same "
            f"series as the seasonal-naive path ({baseline_sum:,.0f} registrations). "
            "No scenario departure was applied. This path is still an extrapolation, "
            "not an observation of the future."
        )
    direction = "above" if gap > 0 else "below"
    return (
        f"The demand shock is {shock_pct:.1f}%. That number rescales the seasonal-naive "
        f"path; it is not an estimated response to price, income, or policy. Over "
        f"{horizon} months the scenario sits {abs(gap):,.0f} registrations {direction} "
        f"that path (baseline {baseline_sum:,.0f})."
    )


def absorption_sentence(threshold: float, names: list[str]) -> str:
    bar = "strict" if threshold >= 0.9 else "lenient"
    if not names:
        return (
            f"At a {bar} self-transition bar of {threshold:.2f}, no fuel regime is "
            "classified as absorbing. States are still leaving at least one regime "
            "often enough to miss this bar. A lower bar would reclassify stickiness; "
            "it would not create a new observation."
        )
    listed = ", ".join(names)
    return (
        f"At a {bar} self-transition bar of {threshold:.2f}, the regimes that stay "
        f"put at least that often are: {listed}. "
        "Absorption here means a high empirical self-transition rate in this sample. "
        "It does not mean a state cannot leave the regime under a different policy."
    )


def zipf_sentence(slope: float, r_squared: float, n: int, tolerance: float) -> str:
    if not _finite(slope):
        return "The rank-size slope was not estimated."
    gap = abs(slope - (-1.0))
    if gap <= tolerance:
        verdict = (
            f"The slope is within {tolerance:.2f} of -1, so a Zipf description survives "
            "this tolerance."
        )
    else:
        verdict = (
            f"The slope is {gap:.2f} away from -1, outside the tolerance of {tolerance:.2f}. "
            "State registration volumes are not a pure Zipf ranking at this bar."
        )
    return (
        f"The log-size on log-rank slope is {slope:.2f} (R² {r_squared:.2f}, n={n}). "
        f"{verdict} Tightening the tolerance can withdraw a Zipf claim without changing "
        "the data. The slope describes size inequality. It is not a law of how the "
        "market grows."
    )


def skill_sentence(model: str, skill: float, bar: float) -> str:
    if not _finite(skill):
        return "Skill against the seasonal naive was not computed."
    verdict = "clears" if skill > bar else "does not clear"
    return (
        f"{model} skill versus the seasonal naive is {skill:.3f}, so it {verdict} "
        f"the skill bar of {bar:.2f}. Skill is one minus the ratio of rolling-origin MAPEs. "
        "A model that misses the bar is not treated as a better forecast. Raising the bar "
        "can demote a model without any new observation."
    )


def coverage_sentence(coverage: float, nominal: float, n_predictions: int) -> str:
    if not _finite(coverage):
        return "Interval coverage was not computed."
    if coverage + 0.02 < nominal:
        verdict = "narrower than its nominal level on this backtest"
    elif coverage > nominal + 0.02:
        verdict = "wider than its nominal level on this backtest"
    else:
        verdict = "close to its nominal level on this backtest"
    return (
        f"Holt-Winters interval coverage is {coverage:.2f} on {n_predictions} holdout "
        f"points, against a nominal level of {nominal:.2f}. The interval looks {verdict}. "
        "The band is ±1.96 residual standard deviations. That matches a 95% interval only "
        "if residuals are independent and normal, which monthly registrations are not. "
        "Coverage is a property of this backtest, not a promise about next year."
    )


def bias_sentence(model: str, bias: float) -> str:
    if not _finite(bias):
        return "Forecast bias was not computed."
    if abs(bias) < 1:
        direction = "essentially unbiased in registration units"
    elif bias > 0:
        direction = "high on average: it over-predicts"
    else:
        direction = "low on average: it under-predicts"
    return (
        f"{model} signed error averages {bias:,.0f} registrations per holdout point, "
        f"so the backtest is {direction}. Bias is predicted minus actual. "
        "It is not a policy effect."
    )


def granger_sentence(
    cause: str,
    effect: str,
    forward_p: float,
    reverse_p: float,
    lag: int,
    alpha: float,
) -> str:
    if not _finite(forward_p) or not _finite(reverse_p):
        return "The lead-lag test was not computed."
    forward = forward_p < alpha
    reverse = reverse_p < alpha
    if forward and not reverse:
        claim = f"changes in {cause} lead changes in {effect} at lag {lag}, and the reverse test does not"
    elif forward and reverse:
        claim = f"both directions reject at lag {lag}, so the lead is not one-way"
    elif reverse and not forward:
        claim = f"the tested direction does not lead; the reverse test does, at lag {lag}"
    else:
        claim = f"neither direction rejects the null at lag {lag}"
    return (
        f"On first differences, {claim}. Forward p={forward_p:.3f}, reverse p={reverse_p:.3f}, "
        f"alpha {alpha:.2f}. A Granger lead is a predictive ordering in this sample. "
        "A common shock can produce it. It is not a structural cause."
    )

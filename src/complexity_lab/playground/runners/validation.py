"""System and data-contract experiments. They measure the extract; they do not repair it."""

from __future__ import annotations

import duckdb

from complexity_lab.config import settings
from complexity_lab.data.reference import validate_reference_catalog
from complexity_lab.playground.models import ExperimentSpec, check
from complexity_lab.playground.registry import playground_experiment
from complexity_lab.playground.runners.common import finish


@playground_experiment("V01")
def all_india_gap(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = con.execute(
        """
        WITH annual AS (
            SELECT state_code, year, SUM("count")::DOUBLE AS regs
            FROM registrations
            GROUP BY 1, 2
        )
        SELECT a.year,
               a.regs AS all_india,
               s.state_sum,
               (a.regs - s.state_sum) / NULLIF(a.regs, 0) AS relative_gap
        FROM annual a
        JOIN (
            SELECT year, SUM(regs) AS state_sum
            FROM annual
            WHERE state_code <> 'ALL'
            GROUP BY year
        ) s USING (year)
        WHERE a.state_code = 'ALL'
        ORDER BY year
        """
    ).df()
    if frame.empty:
        return finish(
            spec, params, status="blocked", metrics={},
            checks=[check("estimable", False, "All India annual totals are missing.")],
            interpretation="The gap was not computed because the All India series is missing.",
        )
    frame["abs_gap"] = frame["relative_gap"].abs()
    worst = frame.loc[frame["abs_gap"].idxmax()]
    bar = float(params["max_abs_gap"])
    all_in_experiment = con.execute(
        "SELECT COUNT(*) FROM experiment_state_year WHERE state_code = 'ALL'"
    ).fetchone()[0]
    gap_ok = bool(worst["abs_gap"] <= bar)
    view_ok = all_in_experiment == 0
    interpretation = (
        f"The largest |All India − sum of states| / All India is {worst['abs_gap']:.3%} "
        f"in {int(worst['year'])}. The alarm bar is {bar:.1%}, so the check "
        f"{'holds' if gap_ok else 'fails'}. "
        "The two series are left as they are. A tighter bar can raise an alarm without editing a row."
    )
    return finish(
        spec, params, status="ok",
        metrics={
            "max_abs_relative_gap": float(worst["abs_gap"]),
            "year_of_max_gap": int(worst["year"]),
            "all_india_that_year": float(worst["all_india"]),
            "state_sum_that_year": float(worst["state_sum"]),
            "alarm_bar": bar,
        },
        checks=[
            check("gap_within_bar", gap_ok, f"Maximum absolute relative gap is {worst['abs_gap']:.3%}."),
            check("experiment_view_excludes_all", view_ok, "experiment_state_year must not contain ALL."),
        ],
        interpretation=interpretation,
        frame=frame[["year", "all_india", "state_sum", "relative_gap"]],
        chart="line", x="year", y="relative_gap",
        notes=("All India is not replaced by the state sum.",),
    )


@playground_experiment("V02")
def fuel_identity(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    mismatches = con.execute(
        """
        SELECT year, month, total_regs,
               ev_regs + cng_regs + petrol_regs + diesel_regs + hybrid_regs AS fuel_sum
        FROM panel_state_month
        WHERE state_code = 'ALL'
          AND ev_regs + cng_regs + petrol_regs + diesel_regs + hybrid_regs <> total_regs
        ORDER BY year, month
        """
    ).df()
    allowed = int(params["max_mismatch_rows"])
    passed = len(mismatches) <= allowed
    return finish(
        spec, params, status="ok",
        metrics={"mismatched_months": int(len(mismatches)), "allowed": allowed},
        checks=[check("fuel_identity", passed, f"{len(mismatches)} All India months break the five-fuel sum.")],
        interpretation=(
            f"{len(mismatches)} All India months have fuel counts that do not add up to the total. "
            f"The allowed number is {allowed}, so the check {'holds' if passed else 'fails'}. "
            "Mismatches are reported, not reallocated across fuels."
        ),
        frame=mismatches if not mismatches.empty else None,
    )


@playground_experiment("V03")
def partial_years(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    status = con.execute(
        """
        SELECT period, observed_month_count, expected_month_count, completeness_status
        FROM data_period_status
        WHERE source = 'vahan'
        ORDER BY period
        """
    ).df()
    short = status[status["observed_month_count"] < status["expected_month_count"]]
    mislabeled = short[short["completeness_status"] != "partial"]
    enforce = bool(params["fail_if_mislabeled"])
    passed = (not enforce) or mislabeled.empty
    listed = ", ".join(short["period"].astype(str)) if not short.empty else "none"
    return finish(
        spec, params, status="ok",
        metrics={
            "short_years": int(len(short)),
            "mislabeled_short_years": int(len(mislabeled)),
        },
        checks=[check("short_years_marked_partial", passed, f"Short years: {listed}.")],
        interpretation=(
            f"Years with fewer than 12 months: {listed}. "
            f"{'The alarm is on' if enforce else 'The alarm is off'}, and "
            f"{len(mislabeled)} of those years are marked complete. "
            "Completeness is counted from months present, not from the bundle's own flag."
        ),
        frame=status, chart="bar", x="period", y="observed_month_count",
    )


@playground_experiment("V04")
def telangana_absent(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    found = con.execute(
        """
        SELECT COUNT(*)
        FROM registrations
        WHERE state_code = 'TS' OR lower(state_name) LIKE '%telangana%'
        """
    ).fetchone()[0]
    allowed = int(params["max_rows"])
    passed = int(found) <= allowed
    return finish(
        spec, params, status="ok",
        metrics={"telangana_rows": int(found), "allowed": allowed},
        checks=[check("telangana_absent", passed, f"{found} Telangana registration rows.")],
        interpretation=(
            f"The registration extract has {found} Telangana rows. The allowed count is {allowed}, "
            f"so the check {'holds' if passed else 'fails'}. "
            "Reference tables may still contain Telangana. That does not create a Vahan series."
        ),
    )


@playground_experiment("V05")
def hybrid_break(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = con.execute(
        """
        SELECT year, SUM("count")::DOUBLE AS hybrid_regs
        FROM registrations
        WHERE state_code = 'ALL' AND fuel = 'Strong Hybrid'
        GROUP BY year
        ORDER BY year
        """
    ).df()
    pre = float(frame.loc[frame["year"] < 2024, "hybrid_regs"].sum()) if not frame.empty else 0.0
    post_rows = frame.loc[frame["year"] == 2024, "hybrid_regs"]
    post = float(post_rows.iloc[0]) if not post_rows.empty else 0.0
    pre_max = int(params["pre_max"])
    post_min = int(params["post_min"])
    passed = pre <= pre_max and post >= post_min
    return finish(
        spec, params, status="ok",
        metrics={"pre_2024_hybrid_regs": pre, "hybrid_regs_2024": post, "pre_max": pre_max, "post_min": post_min},
        checks=[check("classification_break", passed, f"Pre-2024 total {pre:.0f}; 2024 total {post:.0f}.")],
        interpretation=(
            f"National strong-hybrid registrations sum to {pre:.0f} before 2024 and {post:.0f} in 2024. "
            f"The bars are pre ≤ {pre_max} and 2024 ≥ {post_min}, so the break "
            f"{'is still visible' if passed else 'no longer has the previously verified shape'}. "
            "If the check fails, inspect the source before fitting any hybrid curve. Do not smooth the jump."
        ),
        frame=frame if not frame.empty else None, chart="bar", x="year", y="hybrid_regs",
        notes=("The 2024 jump is treated as a classification fact to be checked, not removed.",),
    )


@playground_experiment("V06")
def population_labels(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = con.execute(
        "SELECT quality, COUNT(*) AS rows FROM ref_state_population_annual GROUP BY quality"
    ).df()
    labels = set(frame["quality"].astype(str))
    enforce = bool(params["fail_if_not_estimate"])
    passed = (not enforce) or labels == {"estimate"}
    shown = ", ".join(sorted(labels)) if labels else "none"
    return finish(
        spec, params, status="ok",
        metrics={"n_labels": len(labels), "rows": int(frame["rows"].sum()) if not frame.empty else 0},
        checks=[check("labelled_estimate", passed, f"Quality labels: {shown}.")],
        interpretation=(
            f"Population quality labels in the file: {shown}. "
            f"{'The check requires every row to say estimate' if enforce else 'The label alarm is off'}. "
            f"The check {'holds' if passed else 'fails'}. "
            "A pass confirms the label. It does not turn the estimate into a census count."
        ),
        frame=frame,
        notes=("Urban shares inside this file are the 2011 shares, held fixed.",),
    )


@playground_experiment("V07")
def fuel_basis(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    frame = con.execute(
        """
        SELECT COALESCE(petrol_price_basis, '(missing basis)') AS basis,
               COUNT(*)::INTEGER AS rows
        FROM panel_state_year
        WHERE state_code <> 'ALL'
          AND year >= ?
          AND petrol_price_inr IS NOT NULL
        GROUP BY 1
        ORDER BY rows DESC
        """,
        [int(params["min_year"])],
    ).df()
    if frame.empty:
        return finish(
            spec, params, status="blocked", metrics={},
            checks=[check("estimable", False, "No priced state-years in the requested window.")],
            interpretation="There is no petrol price to audit in this window.",
        )
    missing = int(frame.loc[frame["basis"] == "(missing basis)", "rows"].sum())
    total = int(frame["rows"].sum())
    fallback = int(frame.loc[frame["basis"] == "ALL/Delhi fallback", "rows"].sum())
    passed = missing == 0
    return finish(
        spec, params, status="ok",
        metrics={
            "priced_rows": total,
            "missing_basis_rows": missing,
            "delhi_fallback_rows": fallback,
            "fallback_share": fallback / total if total else None,
        },
        checks=[check("basis_present", passed, f"{missing} priced rows have no basis.")],
        interpretation=(
            f"From {int(params['min_year'])} onward, {total} state-years have a petrol price. "
            f"{fallback} use the All India/Delhi fallback ({fallback / total:.1%}), and {missing} "
            "have no basis at all. "
            f"The disclosure check {'holds' if passed else 'fails'}. "
            "A fallback row remains a Delhi proxy even when the check passes."
        ),
        frame=frame, chart="bar", x="basis", y="rows",
        notes=("Changing the first year changes how much of the pre-2017 fallback enters the audit.",),
    )


@playground_experiment("V08")
def unique_keys(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    duplicates = con.execute(
        """
        SELECT state_code, year, COUNT(*) AS rows
        FROM panel_state_year
        GROUP BY 1, 2
        HAVING COUNT(*) > 1
        """
    ).df()
    allowed = int(params["max_duplicate_groups"])
    passed = len(duplicates) <= allowed
    return finish(
        spec, params, status="ok",
        metrics={"duplicate_groups": int(len(duplicates)), "allowed": allowed},
        checks=[check("unique_state_year", passed, f"{len(duplicates)} duplicate state-year groups.")],
        interpretation=(
            f"{len(duplicates)} state-year groups are duplicated. The allowed number is {allowed}, "
            f"so the check {'holds' if passed else 'fails'}. Duplicates are not averaged away."
        ),
        frame=duplicates if not duplicates.empty else None,
    )


@playground_experiment("V09")
def non_negative_counts(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    bad = con.execute(
        'SELECT COUNT(*) FROM registrations WHERE "count" IS NULL OR "count" < 0'
    ).fetchone()[0]
    allowed = int(params["max_bad_rows"])
    passed = int(bad) <= allowed
    return finish(
        spec, params, status="ok",
        metrics={"bad_rows": int(bad), "allowed": allowed},
        checks=[check("non_negative", passed, f"{bad} null or negative counts.")],
        interpretation=(
            f"{bad} registration rows have a null or negative count. The allowed number is {allowed}, "
            f"so the check {'holds' if passed else 'fails'}. Negative rows are not clipped."
        ),
    )


@playground_experiment("V10")
def reference_catalog(con: duckdb.DuckDBPyConnection, spec: ExperimentSpec, params: dict) -> object:
    del con
    require = bool(params["require_catalog"])
    try:
        catalog = validate_reference_catalog(settings.reference_dir)
    except ValueError as exc:
        return finish(
            spec, params, status="ok",
            metrics={"catalog_ok": False},
            checks=[check("catalog_matches_files", not require, str(exc))],
            interpretation=(
                f"The reference catalog failed validation: {exc} "
                f"{'This fails the check.' if require else 'The alarm is off, so the check does not fail.'} "
                "No undeclared file was loaded to paper over the mismatch."
            ),
        )
    present = catalog is not None
    passed = (not require) or present
    rows = 0 if catalog is None else int(len(catalog))
    return finish(
        spec, params, status="ok",
        metrics={"catalog_rows": rows, "catalog_present": present},
        checks=[check("catalog_matches_files", passed, f"Catalog datasets: {rows}.")],
        interpretation=(
            f"The reference catalog {'validates against the files' if present else 'is absent'} "
            f"({rows} datasets). The requirement switch is {'on' if require else 'off'}. "
            "A file that is not listed is not an approved covariate."
        ),
    )

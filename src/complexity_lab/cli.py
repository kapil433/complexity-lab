"""The `lab` command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from complexity_lab.config import settings


def cmd_ingest(_args) -> None:
    from complexity_lab.data.ingest import ingest

    summary = ingest()
    print(json.dumps(summary, indent=2))


def cmd_panel(_args) -> None:
    from complexity_lab.data.panel import build_panels

    print(json.dumps(build_panels(), indent=2))


def cmd_list(_args) -> None:
    from complexity_lab.experiments.registry import list_experiments

    for exp in list_experiments():
        print(f"{exp.name:28s} {exp.description}")


def cmd_run(args) -> None:
    from complexity_lab.experiments.runner import run_experiment

    params = json.loads(args.params) if args.params else {}
    manifest = run_experiment(args.name, params=params)
    print(json.dumps(manifest, indent=2, default=str))


def cmd_wholesale(args) -> None:
    from pathlib import Path

    from complexity_lab.data.ingest import connect
    from complexity_lab.data.wholesale import ingest_wholesale

    con = connect()
    try:
        summary = ingest_wholesale(
            con,
            source=Path(args.source) if args.source else None,
            use_cache=not args.refresh,
        )
    finally:
        con.close()
    print(json.dumps(summary, indent=2))


def cmd_references(_args) -> None:
    from complexity_lab.data.reference import (
        build_reference_availability,
        validate_reference_catalog,
    )

    catalog = validate_reference_catalog(settings.reference_dir)
    if catalog is None:
        raise FileNotFoundError("data/reference/reference_catalog.csv not found")
    report = build_reference_availability(settings.reference_dir, catalog)
    cols = [
        "dataset",
        "status",
        "geography",
        "time_coverage",
        "quality_summary",
        "not_available",
    ]
    print(report[cols].to_string(index=False))


def _print_playground_result(result) -> None:
    payload = {
        "id": result.experiment_id,
        "status": result.status,
        "evidence": result.evidence,
        "metrics": result.metrics,
        "checks": result.checks,
        "interpretation": result.interpretation,
        "do_not_infer": result.do_not_infer,
        "data_notes": result.data_notes,
    }
    print(json.dumps(payload, indent=2, default=str))


def cmd_playground(args) -> None:
    from complexity_lab.data.ingest import connect
    from complexity_lab.playground.catalog import experiments

    if args.list or not (args.run or args.suite):
        for spec in experiments():
            print(f"{spec.experiment_id:4s}  {spec.title}")
        if not (args.run or args.suite):
            return
    from complexity_lab.playground.service import run_experiment, run_validation_suite

    overrides = json.loads(args.params) if args.params else None
    con = connect(read_only=True)
    try:
        if args.suite:
            for result in run_validation_suite(con):
                failed = len(result.failed_checks)
                print(f"{result.experiment_id}  {result.status}  failed_checks={failed}")
        if args.run:
            _print_playground_result(run_experiment(con, args.run, overrides))
    finally:
        con.close()


def cmd_autiqa_status(_args) -> None:
    from complexity_lab.data.autiqa import autiqa_status

    status = autiqa_status()
    print(json.dumps({"status": status.status, "detail": status.detail, "table": status.table}, indent=2))


def cmd_macro_refresh(_args) -> None:
    from complexity_lab.data.public_macro import refresh_world_bank

    result = refresh_world_bank()
    print(json.dumps({"status": result.status, "detail": result.detail, "rows": result.rows, "path": result.path}, indent=2))
    if result.status != "retrieved":
        raise SystemExit(1)


def cmd_app(_args) -> None:
    app_path = settings.root / "app" / "Home.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="lab", description="Complexity Lab CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="Build data/lab.duckdb from raw bundle + reference CSVs").set_defaults(fn=cmd_ingest)
    sub.add_parser("panel", help="Build panel_state_month / panel_state_year").set_defaults(fn=cmd_panel)
    sub.add_parser("list", help="List registered experiments").set_defaults(fn=cmd_list)

    run_p = sub.add_parser("run", help="Run a registered experiment")
    run_p.add_argument("name")
    run_p.add_argument("--params", help='JSON dict of parameters, e.g. \'{"min_total": 500}\'')
    run_p.set_defaults(fn=cmd_run)

    ws_p = sub.add_parser("wholesale", help="Ingest wholesale (city x model x month) data")
    ws_p.add_argument("--source", help="Path to the source XLSB/parquet (defaults to cache, then the configured source)")
    ws_p.add_argument("--refresh", action="store_true", help="Re-read the source instead of the parquet cache")
    ws_p.set_defaults(fn=cmd_wholesale)

    sub.add_parser(
        "references", help="Show reference-data availability, constraints and gaps"
    ).set_defaults(fn=cmd_references)

    sub.add_parser("app", help="Launch the Streamlit lab").set_defaults(fn=cmd_app)

    play = sub.add_parser("playground", help="List or run a science-playground experiment")
    play.add_argument("--list", action="store_true", help="Print the 50 experiment contracts")
    play.add_argument("--run", help="Experiment id, for example D01 or V02")
    play.add_argument("--suite", action="store_true", help="Run the V01–V10 validation suite")
    play.add_argument("--params", help="JSON object of knob overrides")
    play.set_defaults(fn=cmd_playground)

    sub.add_parser("autiqa-status", help="Probe the optional Autiqa Supabase API").set_defaults(
        fn=cmd_autiqa_status
    )
    sub.add_parser(
        "macro-refresh",
        help="Fetch World Bank India annual series and refuse an implausible payload",
    ).set_defaults(fn=cmd_macro_refresh)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

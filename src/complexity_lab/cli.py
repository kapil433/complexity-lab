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


def cmd_app(_args) -> None:
    app_path = settings.root / "app" / "Home.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)


def main() -> None:
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

    sub.add_parser("app", help="Launch the Streamlit lab").set_defaults(fn=cmd_app)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

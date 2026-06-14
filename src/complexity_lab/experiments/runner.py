"""Run registered experiments and publish visual, reproducible result bundles."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from complexity_lab.config import settings
from complexity_lab.data.ingest import connect
from complexity_lab.experiments.cards import get_card
from complexity_lab.experiments.publishing import (
    build_result_pages,
    primary_finding,
)
from complexity_lab.experiments.registry import get_experiment

_EXPERIMENT_DEPENDENCIES = {
    "descriptive-baseline": [
        "panel_state_month",
        "experiment_state_year",
        "experiment_state_context",
        "oem_state_edges",
    ],
    "ev-diffusion-states": ["panel_state_month", "experiment_state_context"],
    "oem-state-network": ["oem_state_edges"],
    "wholesale-retail-nowcast": ["retail_wholesale_month", "ws_segment_month"],
    "phase-transitions": ["oem_state_edges", "experiment_state_year"],
    "ev-threshold": ["panel_state_month", "experiment_state_context"],
    "ev-contagion": ["experiment_state_year", "ref_state_adjacency"],
    "fuel-regimes": ["experiment_state_year", "ref_policy_events_canonical"],
    "adoption-network-horserace": [
        "experiment_state_year",
        "experiment_state_context",
        "ref_state_adjacency",
    ],
    "shev-isolation": [
        "panel_state_month",
        "ref_policy_events_canonical",
        "experiment_state_context",
    ],
    "regime-survival": ["experiment_state_year"],
    "suv-transition": ["ws_segment_month", "ws_state_month", "ws_model_month"],
    "shev-counterfactual": ["panel_state_month"],
}


def _reference_contract() -> dict:
    path = settings.reference_dir / "reference_catalog.csv"
    return {
        "catalog_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "canonical_interfaces": [
            "experiment_state_year",
            "experiment_state_context",
            "ref_policy_events_canonical",
        ],
        "truth_contract": "DATA_TRUTH.md",
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=settings.root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _versions() -> dict[str, str]:
    packages = ["complexity-lab", "duckdb", "pandas", "numpy", "plotly"]
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions


def _data_contract(con, dependencies: list[str]) -> tuple[dict, dict]:
    cutoff_row = con.execute(
        """
        SELECT MAX(freshness_date), MAX(CAST(period AS INTEGER))
            FILTER (WHERE completeness_status = 'complete')
        FROM data_period_status
        WHERE source = 'vahan'
        """
    ).fetchone()
    dependency_facts = {}
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    for dependency in dependencies:
        if dependency not in tables:
            dependency_facts[dependency] = {"available": False}
            continue
        count = con.execute(f'SELECT COUNT(*) FROM "{dependency}"').fetchone()[0]
        dependency_facts[dependency] = {"available": True, "rows": int(count)}
    cutoff = {
        "vahan": str(cutoff_row[0]),
        "latest_complete_year": int(cutoff_row[1]),
        "coverage_policy": "complete periods unless experiment declares otherwise",
    }
    return cutoff, dependency_facts


def _classify_artifacts(out_dir: Path, private: bool) -> list[dict]:
    classification = "private" if private else "public_aggregate"
    rows = []
    for path in sorted(item for item in out_dir.rglob("*") if item.is_file()):
        if path.name == "manifest.json":
            continue
        rows.append(
            {
                "path": path.relative_to(out_dir).as_posix(),
                "type": path.suffix.lstrip(".") or "file",
                "classification": classification,
            }
        )
    return rows


def run_experiment(name: str, params: dict | None = None, out_root: Path | None = None) -> dict:
    """Execute one experiment through validation, analysis, visuals, and publishing."""
    exp = get_experiment(name)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (out_root or settings.outputs_dir) / name / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    stage_times = {"queued": stamp}
    dependencies = _EXPERIMENT_DEPENDENCIES.get(name, list(exp.data_dependencies))

    con = connect(read_only=True)
    t0 = time.perf_counter()
    try:
        stage_times["validate_data_contract"] = datetime.now(UTC).isoformat()
        cutoff, dependency_facts = _data_contract(con, dependencies)
        missing = [key for key, value in dependency_facts.items() if not value["available"]]
        if missing:
            raise RuntimeError(f"Missing experiment dependencies: {', '.join(missing)}")
        stage_times["run_analysis"] = datetime.now(UTC).isoformat()
        metrics = exp.fn(con, out_dir, **(params or {})) or {}
    finally:
        con.close()
    elapsed = time.perf_counter() - t0

    card = get_card(name)
    private = any("wholesale" in dependency or dependency.startswith("ws_") for dependency in dependencies)
    manifest = {
        "experiment": name,
        "description": exp.description,
        "status": "success",
        "stage_timestamps": stage_times,
        "data_dependencies": dependencies,
        "input_facts": dependency_facts,
        "reference_contract": _reference_contract(),
        "data_cutoff": cutoff,
        "git_commit": _git_commit(),
        "package_versions": _versions(),
        "params": params or {},
        "random_seed": (params or {}).get("seed", 42),
        "timestamp_utc": stamp,
        "elapsed_seconds": round(elapsed, 2),
        "metrics": metrics,
        "primary_finding": primary_finding(metrics),
        "limitations": card.limitations,
        "privacy": "private" if private else "public_aggregate",
    }
    stage_times["build_diagnostics"] = datetime.now(UTC).isoformat()
    build_result_pages(out_dir, manifest)
    stage_times["render_charts"] = datetime.now(UTC).isoformat()
    manifest["artifacts"] = _classify_artifacts(out_dir, private)
    if any("classification" not in artifact for artifact in manifest["artifacts"]):
        raise RuntimeError("Publishing failed closed: artifact classification missing")
    stage_times["publish_result"] = datetime.now(UTC).isoformat()
    (out_dir / "run.log").write_text(
        f"{name} completed in {elapsed:.2f}s\n", encoding="utf-8"
    )
    manifest["artifacts"] = _classify_artifacts(out_dir, private)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    return manifest

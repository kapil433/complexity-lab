"""Run registered experiments and persist artifacts + metadata."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from complexity_lab.config import settings
from complexity_lab.data.ingest import connect
from complexity_lab.experiments.registry import get_experiment


def run_experiment(name: str, params: dict | None = None, out_root: Path | None = None) -> dict:
    """Execute one experiment; artifacts land in outputs/<name>/<timestamp>/."""
    exp = get_experiment(name)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (out_root or settings.outputs_dir) / name / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    con = connect(read_only=True)
    t0 = time.perf_counter()
    try:
        metrics = exp.fn(con, out_dir, **(params or {})) or {}
    finally:
        con.close()
    elapsed = time.perf_counter() - t0

    manifest = {
        "experiment": name,
        "description": exp.description,
        "params": params or {},
        "timestamp_utc": stamp,
        "elapsed_seconds": round(elapsed, 2),
        "metrics": metrics,
        "artifacts": sorted(p.name for p in out_dir.iterdir() if p.name != "manifest.json"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest

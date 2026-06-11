"""Wholesale (OEM dispatch) data ingest — stub.

Wholesale data will land in a local folder (see ``settings.wholesale_dir`` /
``LAB_WHOLESALE_DIR``). Once files exist, implement ``ingest_wholesale`` to
normalise them into a ``wholesale`` table with the same grain conventions as
``registrations`` so retail-vs-wholesale (inventory build-up) experiments
become possible.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from complexity_lab.config import settings


def discover_wholesale_files(wholesale_dir: Path | None = None) -> list[Path]:
    d = wholesale_dir or settings.wholesale_dir
    if d is None or not Path(d).exists():
        return []
    return sorted(p for p in Path(d).rglob("*") if p.suffix.lower() in {".csv", ".xlsx", ".json"})


def ingest_wholesale(con: duckdb.DuckDBPyConnection, wholesale_dir: Path | None = None) -> int:
    files = discover_wholesale_files(wholesale_dir)
    if not files:
        return 0
    raise NotImplementedError(
        f"Found {len(files)} wholesale file(s) — implement schema mapping in wholesale.py: "
        f"{[f.name for f in files[:5]]}"
    )

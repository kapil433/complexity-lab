"""Data layer: ingest raw VAHAN bundle + reference CSVs into DuckDB, build panels."""

from complexity_lab.data.ingest import connect, ingest
from complexity_lab.data.panel import build_panels

__all__ = ["connect", "ingest", "build_panels"]

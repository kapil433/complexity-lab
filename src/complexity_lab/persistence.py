"""Local research-memory storage for saved views and watchlists."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from complexity_lab.config import settings


def _path(path: Path | None = None) -> Path:
    return path or (settings.root / "data" / "user_lab.duckdb")


def initialize(path: Path | None = None) -> Path:
    db_path = _path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_view (
                id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                page VARCHAR NOT NULL,
                parameter_payload JSON NOT NULL,
                data_cutoff VARCHAR NOT NULL,
                package_version VARCHAR NOT NULL,
                notes VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_item (
                id VARCHAR PRIMARY KEY,
                item_type VARCHAR NOT NULL,
                item_key VARCHAR NOT NULL,
                label VARCHAR NOT NULL,
                notes VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
    finally:
        con.close()
    return db_path


def save_view(
    *,
    title: str,
    page: str,
    payload: dict[str, object],
    data_cutoff: str,
    notes: str = "",
    package_version: str = "0.1.0",
    path: Path | None = None,
) -> str:
    db_path = initialize(path)
    view_id = uuid4().hex
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO saved_view
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                view_id,
                title.strip(),
                page,
                json.dumps(payload, sort_keys=True),
                data_cutoff,
                package_version,
                notes.strip(),
                datetime.now(UTC).replace(tzinfo=None),
            ],
        )
    finally:
        con.close()
    return view_id


def list_saved_views(path: Path | None = None) -> pd.DataFrame:
    db_path = initialize(path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(
            """
            SELECT id, title, page, parameter_payload, data_cutoff, notes, created_at
            FROM saved_view
            ORDER BY created_at DESC
            """
        ).df()
    finally:
        con.close()

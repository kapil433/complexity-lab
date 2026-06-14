"""Local research-memory storage for views, notes, hypotheses, and model runs."""

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
        for table in (
            "research_note",
            "hypothesis_run",
            "forecast_run",
            "scenario_run",
            "experiment_run",
        ):
            con.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id VARCHAR PRIMARY KEY,
                    title VARCHAR NOT NULL,
                    parameter_payload JSON NOT NULL,
                    result_payload JSON NOT NULL,
                    data_cutoff VARCHAR NOT NULL,
                    method_version VARCHAR NOT NULL,
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


RESEARCH_TABLES = {
    "note": "research_note",
    "hypothesis": "hypothesis_run",
    "forecast": "forecast_run",
    "scenario": "scenario_run",
    "experiment": "experiment_run",
}


def save_research_item(
    kind: str,
    *,
    title: str,
    parameters: dict[str, object],
    result: dict[str, object],
    data_cutoff: str,
    notes: str = "",
    method_version: str = "0.1.0",
    path: Path | None = None,
) -> str:
    table = RESEARCH_TABLES.get(kind)
    if table is None:
        raise ValueError(f"Unknown research item kind: {kind}")
    db_path = initialize(path)
    item_id = uuid4().hex
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            f"""
            INSERT INTO {table}
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                title.strip(),
                json.dumps(parameters, sort_keys=True, default=str),
                json.dumps(result, sort_keys=True, default=str),
                data_cutoff,
                method_version,
                notes.strip(),
                datetime.now(UTC).replace(tzinfo=None),
            ],
        )
    finally:
        con.close()
    return item_id


def list_research_items(path: Path | None = None) -> pd.DataFrame:
    db_path = initialize(path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        frames = []
        for kind, table in RESEARCH_TABLES.items():
            frame = con.execute(
                f"""
                SELECT id, '{kind}' AS kind, title, parameter_payload,
                       result_payload, data_cutoff, method_version, notes, created_at
                FROM {table}
                """
            ).df()
            frames.append(frame)
        saved = con.execute(
            """
            SELECT id, 'view' AS kind, title, parameter_payload,
                   '{}' AS result_payload, data_cutoff,
                   package_version AS method_version, notes, created_at
            FROM saved_view
            """
        ).df()
        frames.append(saved)
        return pd.concat(frames, ignore_index=True).sort_values(
            "created_at", ascending=False
        )
    finally:
        con.close()


def add_watchlist_item(
    *,
    item_type: str,
    item_key: str,
    label: str,
    notes: str = "",
    path: Path | None = None,
) -> str:
    db_path = initialize(path)
    item_id = uuid4().hex
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO watchlist_item
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                item_type,
                item_key,
                label,
                notes,
                datetime.now(UTC).replace(tzinfo=None),
            ],
        )
    finally:
        con.close()
    return item_id


def list_watchlist(path: Path | None = None) -> pd.DataFrame:
    db_path = initialize(path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(
            """
            SELECT *
            FROM watchlist_item
            ORDER BY created_at DESC
            """
        ).df()
    finally:
        con.close()

"""Central configuration: project paths and settings.

Paths default to the repository layout (src-layout, so the project root is
three levels above this file). Every path can be overridden with environment
variables prefixed ``LAB_`` (e.g. ``LAB_DB_PATH``).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAB_")

    root: Path = PROJECT_ROOT
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    reference_dir: Path = PROJECT_ROOT / "data" / "reference"
    db_path: Path = PROJECT_ROOT / "data" / "lab.duckdb"
    outputs_dir: Path = PROJECT_ROOT / "outputs"

    master_bundle: Path = PROJECT_ROOT / "data" / "raw" / "vahan_master.json.gz"
    geojson_path: Path = PROJECT_ROOT / "data" / "raw" / "india_states.geojson"

    # Optional external sources
    wholesale_dir: Path | None = None  # set LAB_WHOLESALE_DIR when wholesale files arrive


settings = Settings()

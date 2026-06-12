"""Wholesale (OEM dispatch) data ingest: city × model × month, FY2017-18 → present.

Source: a single XLSB workbook of monthly model-wise wholesales by city
(columns: Financial Year, Month [Excel serial], CBH zone, New RO, City,
city group, mdl, maker, SumOfQty, Seg-3, Seg-5).

IMPORTANT: this dataset is proprietary market data and is NOT committed to the
repository. Only derived non-sensitive reference data (the city→state mapping)
is version-controlled. The raw file stays outside the repo; a cleaned parquet
cache lives under data/raw/ which is gitignored.

Cleaning performed here:
- quantities coerced to numeric (source has stray text cells),
- Excel serial month → date/year/month,
- maker labels normalised (case chaos + Maruti's ARENA/NEXA channel split) and
  additionally mapped to the VAHAN bundle's canonical OEM names (``maker_vahan``)
  so wholesale and registrations can be joined,
- cities mapped to states via ``data/reference/city_state.csv`` (top ~250 cities,
  ~94% of volume; the rest keep NULL state and are excluded from state views),
- a ``coverage`` flag: rows before 2022-04 come from a ~50-city sample
  (~7% of industry volume); from 2022-04 the data is full-industry. Cross-period
  comparisons must respect this break — most analyses should filter
  ``coverage = 'full'``.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from complexity_lab.config import settings
from complexity_lab.data.reference import read_reference_csv

DEFAULT_SOURCE = Path(
    r"D:\D-Dump\Books & Pdfs\AI\Chaos and Complexity theory books\Wholesale Data"
    r"\2017 to Till Apr-26 MS Data.xlsb"
)
CACHE_PARQUET = "wholesale_clean.parquet"

# Source maker label (upper-cased) -> (clean maker, channel)
MAKER_MAP: dict[str, tuple[str, str | None]] = {
    "ARENA": ("Maruti Suzuki", "Arena"),
    "NEXA": ("Maruti Suzuki", "Nexa"),
    "MARUTI": ("Maruti Suzuki", None),
    "TATA": ("Tata Motors", None),
    "HYUNDAI": ("Hyundai", None),
    "MAHINDRA": ("Mahindra", None),
    "KIA": ("Kia", None),
    "TOYOTA": ("Toyota", None),
    "HONDA": ("Honda Cars", None),
    "MG": ("MG Motor", None),
    "RENAULT": ("Renault", None),
    "VW": ("VW", None),
    "SKODA": ("Skoda", None),
    "NISSAN": ("Nissan", None),
    "DATSUN": ("Nissan", None),
    "CITROEN": ("Citroen", None),
    "PCA": ("Citroen", None),
    "FIAT": ("Fiat", None),
    "FORD": ("Ford", None),
    "FORCE": ("Force", None),
    "ISUZU": ("Isuzu", None),
    "GM": ("Chevy", None),
    "HM": ("Others", None),
    "MITSUBISHI": ("Others", None),
    "OTHER": ("Others", None),
}

# Clean maker -> VAHAN bundle canonical maker (for joining with registrations)
VAHAN_MAKER_MAP: dict[str, str] = {
    "Maruti Suzuki": "Maruti Suzuki",
    "Tata Motors": "Tata Motors",
    "Hyundai": "Hyundai",
    "Mahindra": "Mahindra",
    "Kia": "Kia",
    "Toyota": "Toyota",
    "Honda Cars": "Honda Cars",
    "MG Motor": "MG Motor",
    "Renault": "Renault",
    "VW": "VW",
    "Skoda": "Volkswagen Group",
    "Nissan": "Nissan",
    "Citroen": "Stellantis",
    "Fiat": "Stellantis",
    "Ford": "Ford",
    "Force": "Force",
    "Isuzu": "Isuzu",
    "Chevy": "Chevy",
    "Others": "Others",
}

_EXCEL_EPOCH = date(1899, 12, 30)

# Before this date the source is a ~50-city sample (~7% of industry volume).
FULL_COVERAGE_FROM = pd.Timestamp("2022-04-01")


def excel_serial_to_date(serial: int) -> date:
    """Excel 1900-system serial number -> date."""
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def normalize_maker(raw: str) -> tuple[str, str | None, str]:
    """Source label -> (clean maker, channel, vahan maker)."""
    key = str(raw).strip().upper()
    clean, channel = MAKER_MAP.get(key, ("Others", None))
    return clean, channel, VAHAN_MAKER_MAP.get(clean, "Others")


def load_source(source: Path) -> pd.DataFrame:
    """Read the raw workbook (or a parquet snapshot of it)."""
    if source.suffix.lower() == ".parquet":
        return pd.read_parquet(source)
    return pd.read_excel(source, engine="pyxlsb", header=0)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(
        columns={
            "Financial Year": "fy",
            "Month": "month_serial",
            "CBH": "zone",
            "New RO": "ro",
            "City": "city",
            "city group": "city_group",
            "mdl": "model",
            "maker": "maker_raw",
            "SumOfQty": "qty",
            "Seg-3": "segment3",
            "Seg-5": "segment5",
        }
    )
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    df = df.dropna(subset=["qty", "month_serial"])
    df["qty"] = df["qty"].astype("int64")

    dates = pd.to_datetime(
        df["month_serial"].astype(int).map(excel_serial_to_date), errors="coerce"
    )
    df["date"] = dates
    df["year"] = dates.dt.year
    df["month"] = dates.dt.month

    norm = df["maker_raw"].map(normalize_maker)
    df["maker"] = norm.map(lambda t: t[0])
    df["channel"] = norm.map(lambda t: t[1])
    df["maker_vahan"] = norm.map(lambda t: t[2])

    df["city"] = df["city"].astype(str).str.strip().str.upper()
    df["model"] = df["model"].astype(str).str.strip().str.upper()
    df["segment5"] = df["segment5"].astype(str).str.strip().str.title()
    # Coverage break: ~50-city sample before FY2022-23, full industry after.
    df["coverage"] = (df["date"] >= FULL_COVERAGE_FROM).map({True: "full", False: "sample"})

    city_map = read_reference_csv(settings.reference_dir / "city_state.csv")
    df = df.merge(city_map.rename(columns={"city": "city"}), on="city", how="left")

    # Fuel proxy: wholesale has no fuel column — join the nameplate->fuel map.
    # ev_only=1 rows are exact; primary_fuel is an approximate allocation.
    fuel_map = read_reference_csv(settings.reference_dir / "model_fuel_map.csv")
    df = df.merge(
        fuel_map[["model", "fuel_variants", "primary_fuel", "ev_only"]], on="model", how="left"
    )
    df["ev_only"] = df["ev_only"].fillna(0).astype("int64")

    cols = [
        "fy", "year", "month", "date", "zone", "ro", "city", "state_code",
        "maker", "maker_vahan", "channel", "model", "segment3", "segment5",
        "fuel_variants", "primary_fuel", "ev_only",
        "coverage", "qty",
    ]
    return df[cols]


_SQL_VIEWS = """
CREATE OR REPLACE VIEW ws_maker_month AS
SELECT maker_vahan AS maker, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale GROUP BY maker_vahan, year, month;

CREATE OR REPLACE VIEW ws_model_month AS
SELECT model, maker, segment5, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale GROUP BY model, maker, segment5, year, month;

CREATE OR REPLACE VIEW ws_state_month AS
SELECT state_code, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale WHERE state_code IS NOT NULL GROUP BY state_code, year, month;

CREATE OR REPLACE VIEW ws_segment_month AS
SELECT segment5, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale GROUP BY segment5, year, month;

-- EV dispatches (exact: EV-only nameplates). Multi-fuel nameplates with an EV
-- variant (Nexon, Punch...) are NOT here — this view undercounts total EV
-- wholesale but never misattributes ICE volume as EV.
CREATE OR REPLACE VIEW ws_ev_month AS
SELECT state_code, maker, model, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale WHERE ev_only = 1
GROUP BY state_code, maker, model, year, month;

-- Approximate fuel mix of dispatches via each nameplate's primary fuel.
CREATE OR REPLACE VIEW ws_fuel_month AS
SELECT primary_fuel AS fuel, year, month, MIN(date) AS date, SUM(qty) AS wholesale
FROM wholesale WHERE primary_fuel IS NOT NULL
GROUP BY primary_fuel, year, month;

-- National retail (registrations) vs wholesale, by month — nowcasting workhorse.
-- Restricted to the full-coverage era (2022-04 onward); the earlier 50-city
-- sample is not comparable to national registrations.
CREATE OR REPLACE VIEW retail_wholesale_month AS
WITH retail AS (
    SELECT year, month, SUM("count") AS retail
    FROM registrations WHERE state_code = 'ALL' GROUP BY year, month
),
ws AS (
    SELECT year, month, SUM(qty) AS wholesale
    FROM wholesale WHERE coverage = 'full' GROUP BY year, month
)
SELECT r.year, r.month, MAKE_DATE(r.year, r.month, 1) AS date, r.retail, w.wholesale,
       w.wholesale::DOUBLE / NULLIF(r.retail, 0) AS ws_retail_ratio
FROM retail r JOIN ws w USING (year, month)
ORDER BY r.year, r.month;
"""


def ingest_wholesale(
    con: duckdb.DuckDBPyConnection, source: Path | None = None, use_cache: bool = True
) -> dict:
    """Clean + load the wholesale table and its views. Returns a summary."""
    cache = settings.raw_dir / CACHE_PARQUET
    if use_cache and cache.exists() and source is None:
        df = pd.read_parquet(cache)
    else:
        src = source or DEFAULT_SOURCE
        if not Path(src).exists():
            raise FileNotFoundError(
                f"Wholesale source not found: {src} (pass --source or set LAB_WHOLESALE_DIR)"
            )
        df = clean(load_source(Path(src)))
        df.to_parquet(cache, index=False)

    con.register("ws_df", df)
    con.execute("CREATE OR REPLACE TABLE wholesale AS SELECT * FROM ws_df")
    con.execute(_SQL_VIEWS)

    unmapped = con.execute(
        "SELECT SUM(qty) FILTER (WHERE state_code IS NULL)::DOUBLE / SUM(qty) FROM wholesale"
    ).fetchone()[0]
    return {
        "rows": len(df),
        "total_units": int(df["qty"].sum()),
        "models": int(df["model"].nunique()),
        "makers": int(df["maker"].nunique()),
        "date_range": f"{df['date'].min():%Y-%m} .. {df['date'].max():%Y-%m}",
        "unmapped_state_volume_pct": round(100 * (unmapped or 0), 1),
    }

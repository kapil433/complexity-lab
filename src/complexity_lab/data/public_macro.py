"""National macro series from the World Bank API.

These series are national and annual. They are not state covariates and they
do not replace RBI state GSDP, the lab's estimated state population, or the
PPAC-based fuel-price file. A payload that fails the plausibility gate is not
written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd

from complexity_lab.config import settings

INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "real_gdp_growth_pct",
    "NY.GDP.PCAP.KD.ZG": "real_gdp_per_capita_growth_pct",
    "SP.POP.TOTL": "population_persons",
    "FP.CPI.TOTL.ZG": "cpi_inflation_pct",
}

SOURCE_URL = "https://api.worldbank.org/v2/country/IND/indicator/{code}?format=json&per_page=200"


@dataclass(frozen=True)
class MacroRefresh:
    status: str
    detail: str
    path: str | None = None
    rows: int = 0


def cache_path() -> Path:
    return settings.root / "data" / "external" / "worldbank_india_annual.csv"


def parse_world_bank_page(payload: object, retrieved_at: str) -> pd.DataFrame:
    """Turn one World Bank JSON page into rows. Null values are dropped, not filled."""
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise ValueError("World Bank response did not contain a data page")
    rows = []
    for item in payload[1]:
        if not isinstance(item, dict) or item.get("value") is None:
            continue
        code = item["indicator"]["id"]
        if code not in INDICATORS:
            raise ValueError(f"Unexpected World Bank indicator in payload: {code}")
        rows.append(
            {
                "country_iso3": item.get("countryiso3code"),
                "indicator_code": code,
                "indicator_name": item["indicator"]["value"],
                "series_name": INDICATORS[code],
                "year": int(item["date"]),
                "value": float(item["value"]),
                "source_url": SOURCE_URL.format(code=code),
                "retrieved_at_utc": retrieved_at,
            }
        )
    if not rows:
        raise ValueError("World Bank page contained no numeric observations")
    return pd.DataFrame(rows)


def assert_plausible(frame: pd.DataFrame) -> None:
    """Refuse to store a payload whose India values are physically implausible.

    The gates are wide on purpose. They catch a corrupted download. They do not
    replace the published number with a preferred one.
    """
    problems = []
    population = frame.loc[
        (frame["indicator_code"] == "SP.POP.TOTL") & frame["year"].between(2011, 2025),
        "value",
    ]
    if population.empty or not population.between(1.0e9, 1.7e9).all():
        problems.append("India population is missing or outside 1.0–1.7 billion for 2011–2025")
    growth = frame.loc[
        (frame["indicator_code"] == "NY.GDP.MKTP.KD.ZG") & frame["year"].between(2012, 2025),
        "value",
    ]
    if growth.empty or not growth.between(-20, 25).all():
        problems.append("India real GDP growth is missing or outside -20% to 25% for 2012–2025")
    if problems:
        raise ValueError("; ".join(problems))


def fetch_world_bank(timeout: float = 40) -> pd.DataFrame:
    retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    frames = []
    for code in INDICATORS:
        url = SOURCE_URL.format(code=code)
        try:
            with urlopen(url, timeout=timeout) as response:
                payload = json.load(response)
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"World Bank request failed for {code}: {exc}") from exc
        frames.append(parse_world_bank_page(payload, retrieved_at))
    frame = pd.concat(frames, ignore_index=True)
    if set(frame["country_iso3"].dropna()) != {"IND"}:
        raise ValueError("World Bank payload was not restricted to India")
    assert_plausible(frame)
    return frame.sort_values(["indicator_code", "year"]).reset_index(drop=True)


def refresh_world_bank(timeout: float = 40) -> MacroRefresh:
    """Fetch, validate, and replace the local cache. Failure leaves the old file."""
    path = cache_path()
    try:
        frame = fetch_world_bank(timeout=timeout)
    except (RuntimeError, ValueError) as exc:
        return MacroRefresh("not_retrieved", str(exc), str(path) if path.exists() else None)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)
    return MacroRefresh("retrieved", "World Bank India annual series passed the plausibility gate.", str(path), len(frame))


def load_world_bank() -> pd.DataFrame | None:
    path = cache_path()
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    required = {"indicator_code", "series_name", "year", "value", "source_url", "retrieved_at_utc"}
    if not required <= set(frame.columns):
        raise ValueError(f"World Bank cache is missing columns: {sorted(required - set(frame.columns))}")
    return frame


def gdp_growth_for_year(year: int) -> float | None:
    frame = load_world_bank()
    if frame is None:
        return None
    match = frame[
        (frame["series_name"] == "real_gdp_growth_pct") & (frame["year"] == int(year))
    ]
    if match.empty:
        return None
    return float(match["value"].iloc[0])


SOURCE_CATALOG: tuple[dict[str, str], ...] = (
    {
        "series": "Vahan registrations",
        "grain": "state × month × OEM × fuel",
        "status": "in the lab",
        "use": "Observed market outcomes. All India is its own series.",
    },
    {
        "series": "Autiqa Supabase API",
        "grain": "not loaded until a pull validates",
        "status": "optional, credentials required",
        "use": "Future extract of the same registration contract. A failed or missing pull adds no rows.",
    },
    {
        "series": "RBI Handbook Table 20, real per-capita NSDP",
        "grain": "state × financial year",
        "status": "in the lab, official",
        "use": "Real income level. Joined to the calendar year in which the financial year starts.",
    },
    {
        "series": "RBI Handbook Table 22, real GSDP and growth",
        "grain": "state × financial year",
        "status": "in the lab, official / derived growth",
        "use": "State output and its growth. Not the same calendar as World Bank national GDP.",
    },
    {
        "series": "State population denominator",
        "grain": "state × year, 2012–2026",
        "status": "in the lab, estimate",
        "use": "Per-capita registrations. Interpolated between anchors. Urban share is Census 2011, held fixed.",
    },
    {
        "series": "Retail petrol, diesel, and CNG prices",
        "grain": "state × year",
        "status": "in the lab, approximate",
        "use": "Delhi compiled series plus era-anchored capital differentials. Not a daily pump panel.",
    },
    {
        "series": "Scheduled-bank personal loans",
        "grain": "state × year",
        "status": "in the lab, constrained estimate",
        "use": "Broad household credit depth. Not vehicle-finance penetration.",
    },
    {
        "series": "CNG stations and public EV chargers",
        "grain": "state snapshot",
        "status": "in the lab, not a time series",
        "use": "Cross-section context only. No historical state panel is stored.",
    },
    {
        "series": "World Bank India real GDP growth, GDP per capita growth, population, CPI inflation",
        "grain": "India × calendar year",
        "status": "fetched when the API responds",
        "use": "National context beside the All India registration series. Not a state driver and not a substitute for RBI GSDP.",
    },
    {
        "series": "data.gov.in daily city fuel prices",
        "grain": "would be city × day",
        "status": "not added",
        "use": "No verified keyless extract was retrieved. The lab keeps the audited annual fuel file instead of inventing a daily panel.",
    },
    {
        "series": "State vehicle-finance penetration and OEM dealer history",
        "grain": "not available",
        "status": "unavailable",
        "use": "Known gaps. Personal loans and dealer anecdotes are not used to fill them.",
    },
)

"""Optional Autiqa Supabase extract.

The analytical database remains the verified local Vahan bundle. This module
probes the API when credentials exist and refuses a pull that does not match
the registration contract. It never manufactures rows to fill a gap.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

REQUIRED_COLUMNS = (
    "state_code",
    "year",
    "month",
    "maker",
    "fuel",
    "count",
)
KNOWN_FUELS = frozenset({"Petrol", "Diesel", "CNG", "EV", "Strong Hybrid"})


@dataclass(frozen=True)
class AutiqaStatus:
    status: str
    detail: str
    url_host: str | None = None
    table: str | None = None


class AutiqaContractError(ValueError):
    """The remote payload is present but not safe to treat as registrations."""


def _credentials() -> tuple[str, str, str] | None:
    url = os.environ.get("LAB_AUTIQA_SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("LAB_AUTIQA_SUPABASE_KEY", "").strip()
    table = os.environ.get("LAB_AUTIQA_REGISTRATIONS_TABLE", "registrations").strip()
    if not url or not key:
        return None
    return url, key, table or "registrations"


def autiqa_status(timeout: float = 20) -> AutiqaStatus:
    """Report whether the API is configured and reachable. Does not invent rows."""
    found = _credentials()
    if found is None:
        return AutiqaStatus(
            "not_configured",
            "LAB_AUTIQA_SUPABASE_URL and LAB_AUTIQA_SUPABASE_KEY are not set. "
            "The lab is reading the verified local Vahan bundle. No Autiqa rows were created.",
        )
    url, key, table = found
    host = url.split("//", 1)[-1].split("/", 1)[0]
    request = Request(
        f"{url}/rest/v1/",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/openapi+json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(200_000)
    except HTTPError as exc:
        return AutiqaStatus(
            "rejected",
            f"Supabase returned HTTP {exc.code}. The local bundle was not modified.",
            host,
            table,
        )
    except (URLError, TimeoutError) as exc:
        return AutiqaStatus(
            "unreachable",
            f"The Autiqa endpoint could not be reached ({exc}). The local bundle was not modified.",
            host,
            table,
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return AutiqaStatus(
            "unreadable",
            "The endpoint responded, but the OpenAPI document was not valid JSON. No rows were loaded.",
            host,
            table,
        )
    paths = payload.get("paths", {}) if isinstance(payload, dict) else {}
    if paths and f"/{table}" not in paths:
        return AutiqaStatus(
            "table_absent",
            f"The OpenAPI document does not list '/{table}'. "
            "Set LAB_AUTIQA_REGISTRATIONS_TABLE to the published table. No rows were loaded.",
            host,
            table,
        )
    return AutiqaStatus(
        "reachable",
        "The API answered. A pull still has to pass the registration contract before it can be used. "
        "This probe did not copy rows into the lab database.",
        host,
        table,
    )


def validate_autiqa_registrations(
    frame: pd.DataFrame,
    known_state_codes: set[str],
) -> list[str]:
    """Return contract problems. An empty list means the frame may be analysed.

    Unknown fuels and unknown state codes are reported. They are not relabelled.
    """
    problems: list[str] = []
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        return [f"Missing columns: {', '.join(missing)}"]
    if frame.empty:
        return ["The extract has no rows."]

    work = frame.loc[:, REQUIRED_COLUMNS].copy()
    if work[list(REQUIRED_COLUMNS)].isna().any().any():
        problems.append("Nulls in state_code, year, month, maker, fuel, or count.")

    counts = pd.to_numeric(work["count"], errors="coerce")
    if counts.isna().any():
        problems.append("Count has non-numeric values.")
    elif (counts < 0).any():
        problems.append(f"Negative registration counts: {int((counts < 0).sum())} rows.")
    elif not (counts.dropna() == counts.dropna().round()).all():
        problems.append("Counts are not whole registrations.")

    months = pd.to_numeric(work["month"], errors="coerce")
    if months.isna().any() or not months.dropna().between(1, 12).all():
        problems.append("Month is outside 1–12.")
    years = pd.to_numeric(work["year"], errors="coerce")
    if years.isna().any() or not years.dropna().between(1990, 2100).all():
        problems.append("Year is outside 1990–2100.")

    fuels = sorted(set(work["fuel"].dropna().astype(str)) - KNOWN_FUELS)
    if fuels:
        problems.append(
            "Unknown fuel labels (not remapped): " + ", ".join(fuels) + "."
        )

    codes = set(work["state_code"].dropna().astype(str))
    unknown_codes = sorted(codes - known_state_codes)
    if unknown_codes:
        problems.append(
            "State codes absent from dim_state (not guessed): " + ", ".join(unknown_codes) + "."
        )

    duplicate_key = ["state_code", "year", "month", "maker", "fuel"]
    if work.duplicated(duplicate_key).any():
        problems.append("Duplicate state × year × month × maker × fuel keys.")
    return problems


def pull_registrations(known_state_codes: set[str], page_size: int = 1000, max_rows: int = 400_000) -> pd.DataFrame:
    """Page the configured table and return it only when the contract holds.

    A truncated page stops with an error. A short extract is not treated as the
    full market. Nothing is written to the lab database.
    """
    found = _credentials()
    if found is None:
        raise AutiqaContractError(
            "Autiqa credentials are not configured. Refusing to build a substitute extract."
        )
    url, key, table = found
    frames: list[pd.DataFrame] = []
    offset = 0
    while offset < max_rows:
        request = Request(
            f"{url}/rest/v1/{table}?select={','.join(REQUIRED_COLUMNS)}",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + page_size - 1}",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                page = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AutiqaContractError(f"Pull failed before validation: {exc}") from exc
        if not isinstance(page, list):
            raise AutiqaContractError("Supabase did not return a row list.")
        if not page:
            break
        frames.append(pd.DataFrame(page))
        offset += len(page)
        if len(page) < page_size:
            break
    else:
        raise AutiqaContractError(
            f"Pull reached {max_rows} rows without a short final page. "
            "Refusing to treat a truncated extract as the registration population."
        )
    if not frames:
        raise AutiqaContractError("The remote table returned no rows.")
    frame = pd.concat(frames, ignore_index=True)
    problems = validate_autiqa_registrations(frame, known_state_codes)
    if problems:
        raise AutiqaContractError(" ".join(problems))
    return frame

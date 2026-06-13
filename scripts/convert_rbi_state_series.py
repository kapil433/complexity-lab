"""Convert selected RBI Handbook wide state tables to long reference CSVs.

Usage:
  uv run --with openpyxl python scripts/convert_rbi_state_series.py roads <xlsx>
  uv run --with openpyxl python scripts/convert_rbi_state_series.py personal-loans <xlsx>
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

NAME_TO_CODE = {
    "andaman & nicobar islands": "AN",
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chandigarh": "CH",
    "chhattisgarh": "CG",
    "dadra & nagar haveli": "DN",
    "daman & diu": "DN",
    "delhi": "DL",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jammu & kashmir": "JK",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "ladakh": "LA",
    "lakshadweep": "LD",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OD",
    "puducherry": "PY",
    "punjab": "PB",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TS",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
    "all india": "ALL",
}

CONFIG = {
    "roads": {
        "column": "road_length_km",
        "table": 146,
        "title": "State-wise length of roads",
        "unit": "km",
        "default_file": "state_road_length.csv",
    },
    "personal-loans": {
        "column": "personal_loans_outstanding_crore",
        "table": 159,
        "title": "State-wise personal loans by scheduled commercial banks",
        "unit": "INR crore outstanding",
        "default_file": "state_personal_loans_rbi.csv",
    },
}


def clean_label(value: object) -> str:
    label = str(value).strip().lower()
    return re.sub(r"[@*#\d.\s]+$", "", label).strip()


def parse_year(value: object) -> int | None:
    year = pd.to_numeric(value, errors="coerce")
    if pd.isna(year) or int(year) != year:
        return None
    year = int(year)
    return year if 1900 <= year <= 2100 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("series", choices=CONFIG)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def geography_note(state_code: str, year: int) -> str:
    if state_code == "AP" and year <= 2014:
        return "Source Andhra Pradesh includes Telangana through the March 2014 observation."
    if state_code == "JK" and year <= 2019:
        return "Source Jammu & Kashmir includes the territory later separated as Ladakh."
    if state_code == "DN":
        return "Dadra & Nagar Haveli and Daman & Diu source rows aggregated to the merged UT."
    return ""


def parse_workbook(path: Path, series: str) -> pd.DataFrame:
    config = CONFIG[series]
    rows: list[dict] = []
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        raw = xl.parse(sheet, header=None)
        label_col = next(
            (
                col
                for col in range(min(4, raw.shape[1]))
                if {
                    clean_label(value)
                    for value in raw.iloc[:, col].dropna().tolist()
                }
                & {"andhra pradesh", "maharashtra", "gujarat"}
            ),
            None,
        )
        if label_col is None:
            continue
        header_row = next(
            (
                i
                for i in range(min(12, len(raw)))
                if sum(parse_year(v) is not None for v in raw.iloc[i, label_col + 1 :]) >= 3
            ),
            None,
        )
        if header_row is None:
            continue
        header = raw.iloc[header_row].tolist()
        for i in range(header_row + 1, len(raw)):
            code = NAME_TO_CODE.get(clean_label(raw.iloc[i, label_col]))
            if code is None:
                continue
            for j, year_raw in enumerate(header[label_col + 1 :], start=label_col + 1):
                year = parse_year(year_raw)
                if year is None:
                    continue
                value = pd.to_numeric(raw.iloc[i, j], errors="coerce")
                if pd.isna(value):
                    continue
                rows.append(
                    {
                        "state_code": code,
                        "year": year,
                        config["column"]: int(round(value)),
                        "as_of": f"{year}-03-31",
                        "source": (
                            "RBI Handbook of Statistics on Indian States 2024-25, "
                            f"Table {config['table']}"
                        ),
                        "quality": "official_derived" if code == "DN" else "official",
                        "geography_note": geography_note(code, year),
                    }
                )

    df = pd.DataFrame(rows)
    value_column = config["column"]
    aggregations = {
        value_column: "sum",
        "as_of": "first",
        "source": "first",
        "quality": lambda values: (
            "official_derived" if "official_derived" in set(values) else "official"
        ),
        "geography_note": lambda values: next((v for v in values if v), ""),
    }
    return (
        df.groupby(["state_code", "year"], as_index=False)
        .agg(aggregations)
        .sort_values(["state_code", "year"])
    )


def main() -> None:
    args = parse_args()
    config = CONFIG[args.series]
    root = Path(__file__).resolve().parents[1]
    default_dir = (
        root / "data" / "raw" / "reference_inputs"
        if args.series == "personal-loans"
        else root / "data" / "reference"
    )
    output = args.output or default_dir / config["default_file"]
    df = parse_workbook(args.xlsx, args.series)
    comment = (
        f"# {config['title']} ({config['unit']}).\n"
        f"# Source: RBI Handbook of Statistics on Indian States 2024-25, Table {config['table']}.\n"
        "# Values are as at end-March. Read geography_note before longitudinal comparison.\n"
    )
    output.write_text(
        comment + df.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(df)} rows, {df['state_code'].nunique()} geographies, "
        f"{df['year'].min()}..{df['year'].max()} -> {output}"
    )


if __name__ == "__main__":
    main()

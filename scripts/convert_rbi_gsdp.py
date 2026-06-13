"""Convert RBI Handbook Table 22 to constant-price GSDP and real growth.

Usage:
  uv run --with openpyxl python scripts/convert_rbi_gsdp.py <xlsx_path>
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
    "delhi": "DL",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jammu & kashmir": "JK",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
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
}


def clean_label(value: object) -> str:
    return re.sub(r"[*#\d.\s]+$", "", str(value).strip().lower()).strip()


def clean_fy(value: object) -> str | None:
    text = str(value).strip().replace("–", "-").replace("â€“", "-")
    match = re.match(r"^(\d{4})-(\d{2})", text)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def geography_note(state_code: str, fy: str) -> str:
    if state_code in {"AP", "TS"}:
        return "RBI/NSO provides a back-cast series on current AP and Telangana geographies."
    if state_code == "JK" and int(fy[:4]) <= 2018:
        return "Source Jammu & Kashmir includes Ladakh through FY2018-19."
    return ""


def parse_workbook(path: Path) -> pd.DataFrame:
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
                if sum(
                    clean_fy(value) is not None
                    for value in raw.iloc[i, label_col + 1 :]
                )
                >= 3
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
            for j, fy_raw in enumerate(header[label_col + 1 :], start=label_col + 1):
                fy = clean_fy(fy_raw)
                if fy is None:
                    continue
                value = pd.to_numeric(raw.iloc[i, j], errors="coerce")
                if pd.isna(value):
                    continue
                rows.append(
                    {
                        "state_code": code,
                        "fy": fy,
                        "gsdp_constant_2011_12_lakh": int(round(value)),
                        "source": (
                            "RBI Handbook of Statistics on Indian States 2024-25, "
                            "Table 22; underlying NSO/MOSPI"
                        ),
                        "level_quality": "official",
                        "growth_quality": "derived",
                        "quality": "official_derived",
                        "geography_note": geography_note(code, fy),
                    }
                )

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(["state_code", "fy"], keep="last")
        .sort_values(["state_code", "fy"])
    )
    df["gsdp_real_growth_pct"] = (
        df.groupby("state_code")["gsdp_constant_2011_12_lakh"].pct_change() * 100
    ).round(3)
    return df


def main() -> None:
    args = parse_args()
    output = args.output or (
        Path(__file__).resolve().parents[1] / "data" / "reference" / "state_gsdp.csv"
    )
    df = parse_workbook(args.xlsx)
    comment = (
        "# State GSDP at constant 2011-12 prices (INR lakh) and derived real growth.\n"
        "# Source: RBI Handbook of Statistics on Indian States 2024-25, Table 22.\n"
        "# FY = April-March. Growth is arithmetic percent change from the prior available FY.\n"
    )
    output.write_text(
        comment + df.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(df)} rows, {df['state_code'].nunique()} states, "
        f"FY {df['fy'].min()}..{df['fy'].max()} -> {output}"
    )


if __name__ == "__main__":
    main()

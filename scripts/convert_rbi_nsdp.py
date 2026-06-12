"""Convert RBI per-capita NSDP tables to a reference CSV.

Usage:
  uv run --with openpyxl python scripts/convert_rbi_nsdp.py <xlsx_path>
  uv run --with openpyxl python scripts/convert_rbi_nsdp.py <xlsx_path> --kind constant

Table 19 contains current prices; Table 20 contains constant 2011-12 prices.
"""

import argparse
from pathlib import Path

import pandas as pd

NAME_TO_CODE = {
    "andhra pradesh": "AP", "arunachal pradesh": "AR", "assam": "AS", "bihar": "BR",
    "chhattisgarh": "CG", "goa": "GA", "gujarat": "GJ", "haryana": "HR",
    "himachal pradesh": "HP", "jharkhand": "JH", "karnataka": "KA", "kerala": "KL",
    "madhya pradesh": "MP", "maharashtra": "MH", "manipur": "MN", "meghalaya": "ML",
    "mizoram": "MZ", "nagaland": "NL", "odisha": "OD", "punjab": "PB",
    "rajasthan": "RJ", "sikkim": "SK", "tamil nadu": "TN", "telangana": "TS",
    "tripura": "TR", "uttar pradesh": "UP", "uttarakhand": "UK", "west bengal": "WB",
    "jammu & kashmir": "JK", "jammu and kashmir": "JK",
    "andaman & nicobar islands": "AN", "andaman and nicobar islands": "AN",
    "chandigarh": "CH", "delhi": "DL", "puducherry": "PY", "all india": "ALL",
    "all-india": "ALL", "india": "ALL",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--kind", choices=("current", "constant"), default="current")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def parse_sheet(raw: pd.DataFrame, value_column: str) -> list[dict]:
    header_row = None
    for i in range(min(12, len(raw))):
        cells = [str(c) for c in raw.iloc[i].tolist()]
        if sum("-" in c and any(ch.isdigit() for ch in c) for c in cells) >= 3:
            header_row = i
            break
    if header_row is None:
        return []
    header = [str(c) for c in raw.iloc[header_row].tolist()]
    # The label column is whichever column actually contains state names.
    label_col = 0
    for col in range(min(3, raw.shape[1])):
        col_vals = {str(v).strip().lower() for v in raw.iloc[:, col].tolist()}
        if col_vals & {"andhra pradesh", "maharashtra", "gujarat"}:
            label_col = col
            break
    rows = []
    for i in range(header_row + 1, len(raw)):
        label = str(raw.iloc[i, label_col]).strip().lower()
        label = label.rstrip("*#1234567890 ").strip()
        code = NAME_TO_CODE.get(label)
        if code is None:
            continue
        for j in range(1, len(header)):
            fy_raw = header[j].strip()
            if "-" not in fy_raw:
                continue
            fy = fy_raw.split("(")[0].strip().replace("–", "-")
            parts = fy.split("-")
            if len(parts[0]) != 4 or not parts[0].isdigit():
                continue
            val = pd.to_numeric(raw.iloc[i, j], errors="coerce")
            if pd.isna(val):
                continue
            rows.append(
                {
                    "state_code": code,
                    "fy": f"{parts[0]}-{parts[1][:2]}",
                    value_column: int(round(val)),
                }
            )
    return rows


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.kind == "constant":
        value_column = "pc_nsdp_constant_2011_12_inr"
        table = 20
        price_basis = "constant 2011-12 prices"
        default_output = root / "data" / "reference" / "state_income_constant.csv"
    else:
        value_column = "pc_nsdp_current_inr"
        table = 19
        price_basis = "current prices"
        default_output = root / "data" / "reference" / "state_income.csv"
    output = args.output or default_output

    xl = pd.ExcelFile(args.xlsx)
    all_rows: list[dict] = []
    for sheet in xl.sheet_names:
        rows = parse_sheet(xl.parse(sheet, header=None), value_column)
        print(f"{sheet}: {len(rows)} values")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["state_code", "fy"], keep="last")
    df["source"] = f"RBI Handbook of Statistics on Indian States 2024-25, Table {table}"
    df["quality"] = "official"
    df = df.sort_values(["state_code", "fy"])

    header_comment = (
        f"# Per-capita Net State Domestic Product at {price_basis} (INR).\n"
        f"# Source: RBI Handbook of Statistics on Indian States 2024-25, Table {table}\n"
        "# (published 11-Dec-2025; underlying data from MOSPI/NSO). FY = April-March.\n"
    )
    output.write_text(
        header_comment + df.to_csv(index=False, lineterminator="\n"),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(df)} rows, {df['state_code'].nunique()} states, "
        f"FY {df['fy'].min()}..{df['fy'].max()} -> {output}"
    )


if __name__ == "__main__":
    main()

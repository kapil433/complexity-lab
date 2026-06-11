"""One-off: convert RBI Handbook Table 19 (per-capita NSDP, current prices) to reference CSV.

Usage: uv run --with openpyxl python scripts/convert_rbi_nsdp.py <xlsx_path>
The table is split across two sheets, T_19(i) and T_19(ii).
"""

import sys
from pathlib import Path

import pandas as pd

XLSX = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "state_income.csv"

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


def parse_sheet(raw: pd.DataFrame) -> list[dict]:
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
                    "pc_nsdp_current_inr": int(round(val)),
                }
            )
    return rows


xl = pd.ExcelFile(XLSX)
all_rows: list[dict] = []
for sheet in xl.sheet_names:
    rows = parse_sheet(xl.parse(sheet, header=None))
    print(f"{sheet}: {len(rows)} values")
    all_rows.extend(rows)

df = pd.DataFrame(all_rows).drop_duplicates(subset=["state_code", "fy"], keep="last")
df["source"] = "RBI Handbook of Statistics on Indian States 2024-25, Table 19"
df["quality"] = "official"
df = df.sort_values(["state_code", "fy"])

header_comment = (
    "# Per-capita Net State Domestic Product at current prices (INR).\n"
    "# Source: RBI Handbook of Statistics on Indian States 2024-25, Table 19\n"
    "# (published 11-Dec-2025; underlying data from MOSPI/NSO). FY = April-March.\n"
)
OUT.write_text(header_comment + df.to_csv(index=False), encoding="utf-8")
print(
    f"Wrote {len(df)} rows, {df['state_code'].nunique()} states, "
    f"FY {df['fy'].min()}..{df['fy'].max()} -> {OUT}"
)

"""Inspect the wholesale XLSB bundle: sheets, shapes, first rows."""

import sys

import pandas as pd

PATH = sys.argv[1]

xl = pd.ExcelFile(PATH, engine="pyxlsb")
print("Sheets:", xl.sheet_names)
for sheet in xl.sheet_names:
    df = xl.parse(sheet, header=None, nrows=15)
    print(f"\n=== {sheet} (first 15 rows, {df.shape[1]} cols) ===")
    with pd.option_context("display.max_columns", 14, "display.width", 250):
        print(df.iloc[:, : min(14, df.shape[1])].to_string())

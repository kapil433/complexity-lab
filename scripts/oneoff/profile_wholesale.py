"""Profile the wholesale XLSB: row count, distincts, volume coverage."""

import sys

import pandas as pd

PATH = sys.argv[1]

df = pd.read_excel(PATH, engine="pyxlsb", header=0)
df.columns = [str(c).strip() for c in df.columns]
print("Shape:", df.shape)
print("Columns:", list(df.columns))
print("\nMonth serial range:", df["Month"].min(), "->", df["Month"].max())
print("FY values:", sorted(df["Financial Year"].dropna().unique()))
print("\nDistincts:")
for c in ["CBH", "New RO", "City", "city group", "mdl", "maker", "Seg-3", "Seg-5"]:
    print(f"  {c}: {df[c].nunique()}")
raw_qty = df["SumOfQty"]
df["SumOfQty"] = pd.to_numeric(raw_qty, errors="coerce")
bad = df[df["SumOfQty"].isna() & raw_qty.notna()]
print("\nNon-numeric qty rows:", len(bad))
if len(bad):
    print(bad.head(5).to_string())
print("Total qty:", int(df["SumOfQty"].sum()))
print("\nMakers by volume:")
print(df.groupby("maker")["SumOfQty"].sum().sort_values(ascending=False).to_string())
print("\nTop 25 cities by volume:")
print(df.groupby("City")["SumOfQty"].sum().sort_values(ascending=False).head(25).to_string())
print("\nCBH values:", df["CBH"].unique())
print("RO values:", sorted(df["New RO"].dropna().unique())[:40])
print("\nSeg-5 values:", sorted(df["Seg-5"].dropna().astype(str).unique()))
# stash a parquet for fast iteration
df.to_parquet("data/raw/wholesale_raw.parquet", index=False)
print("\nSaved data/raw/wholesale_raw.parquet")

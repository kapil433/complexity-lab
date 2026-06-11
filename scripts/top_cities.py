"""Dump top cities by wholesale volume (for building the city->state mapping)."""

import pandas as pd

df = pd.read_parquet("data/raw/wholesale_raw.parquet")
df["SumOfQty"] = pd.to_numeric(df["SumOfQty"], errors="coerce")
vol = df.groupby("City")["SumOfQty"].sum().sort_values(ascending=False)
total = vol.sum()
print(f"total={total:,.0f}  cities={len(vol)}")
print(f"top 150 cover {vol.head(150).sum() / total:.1%}")
print(f"top 250 cover {vol.head(250).sum() / total:.1%}")
for city, qty in vol.head(250).items():
    print(f"{city}\t{qty:,.0f}")

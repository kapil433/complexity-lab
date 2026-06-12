"""Spot-check wholesale vs retail coverage and lead/lag."""

import duckdb

con = duckdb.connect("data/lab.duckdb", read_only=True)
df = con.execute("SELECT * FROM retail_wholesale_month ORDER BY date").df()
print("Months joined:", len(df))
print("\nWS/retail ratio by year:")
print(df.groupby("year")[["retail", "wholesale"]].sum().assign(
    ratio=lambda d: (d.wholesale / d.retail).round(3)).to_string())

# cross-correlation: does wholesale lead retail?
g = df.set_index("date")[["retail", "wholesale"]].pct_change().dropna()
print("\nCorr of monthly growth, wholesale shifted by k months (k>0 = wholesale leads):")
for k in range(-3, 4):
    c = g["retail"].corr(g["wholesale"].shift(k))
    print(f"  k={k:+d}: {c:.3f}")

print("\nTop 10 models by 2025 wholesale:")
print(con.execute(
    "SELECT model, maker, SUM(wholesale) AS units FROM ws_model_month "
    "WHERE year = 2025 GROUP BY model, maker ORDER BY units DESC LIMIT 10").df().to_string(index=False))
con.close()

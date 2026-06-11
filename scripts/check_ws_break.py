"""Locate the wholesale coverage break: cities/makers/volume by month around 2021-22."""

import duckdb

con = duckdb.connect("data/lab.duckdb", read_only=True)
print(con.execute("""
    SELECT year, COUNT(DISTINCT city) cities, COUNT(DISTINCT maker) makers,
           COUNT(DISTINCT model) models, SUM(qty) units
    FROM wholesale GROUP BY year ORDER BY year
""").df().to_string(index=False))

print("\nMonthly units around the break:")
print(con.execute("""
    SELECT date, SUM(qty) units, COUNT(DISTINCT maker) makers
    FROM wholesale WHERE date BETWEEN '2021-06-01' AND '2022-09-01'
    GROUP BY date ORDER BY date
""").df().to_string(index=False))

print("\nMakers present pre-2022 (by units):")
print(con.execute("""
    SELECT maker, SUM(qty) units FROM wholesale WHERE year < 2022
    GROUP BY maker ORDER BY units DESC
""").df().to_string(index=False))
con.close()

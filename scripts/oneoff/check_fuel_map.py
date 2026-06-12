import duckdb

con = duckdb.connect("data/lab.duckdb", read_only=True)
pct = con.execute(
    "SELECT ROUND(100.0 * SUM(qty) FILTER (WHERE primary_fuel IS NULL) / SUM(qty), 2) FROM wholesale"
).fetchone()[0]
print("unmapped fuel volume pct:", pct)
print(con.execute(
    "SELECT year, SUM(wholesale) AS ev_units FROM ws_ev_month WHERE year >= 2022 "
    "GROUP BY year ORDER BY year").df().to_string(index=False))
print(con.execute(
    "SELECT fuel, SUM(wholesale) AS units FROM ws_fuel_month WHERE year = 2025 "
    "GROUP BY fuel ORDER BY units DESC").df().to_string(index=False))

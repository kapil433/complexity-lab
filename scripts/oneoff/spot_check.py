"""Spot-check the ingested database against the bundle README stats."""

import duckdb

con = duckdb.connect("data/lab.duckdb", read_only=True)
print("AP around the 2014 bifurcation:")
print(
    con.execute(
        'SELECT year, SUM("count") AS regs FROM registrations '
        "WHERE state_code='AP' AND year BETWEEN 2012 AND 2017 GROUP BY year ORDER BY year"
    ).df().to_string(index=False)
)
print("\nAll India by year (millions):")
print(
    con.execute(
        'SELECT year, ROUND(SUM("count")/1e6, 3) AS regs_m FROM registrations '
        "WHERE state_code='ALL' GROUP BY year ORDER BY year"
    ).df().to_string(index=False)
)
print("\nFuels:", [r[0] for r in con.execute("SELECT DISTINCT fuel FROM registrations").fetchall()])
print("Makers:", con.execute("SELECT COUNT(DISTINCT maker) FROM registrations").fetchone()[0])
con.close()

"""Validate panel numbers: internal consistency + external sanity anchors."""

import duckdb

con = duckdb.connect("data/lab.duckdb", read_only=True)
fails: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok:
        fails.append(name)


# 1. fuel shares sum to 1 where total > 0
d = con.execute("""
    SELECT MAX(ABS(ev_share + cng_share + petrol_share + diesel_share + hybrid_share - 1)) m
    FROM panel_state_year WHERE total_regs > 0
""").fetchone()[0]
check("fuel shares sum to 1 (year panel)", d < 1e-9, f"max dev {d:.2e}")

# 2. maker shares sum to 1 per state-year
d = con.execute("""
    SELECT MAX(ABS(s - 1)) FROM (
      SELECT state_code, year, SUM(share) s FROM maker_state_share GROUP BY 1, 2)
""").fetchone()[0]
check("maker shares sum to 1", d < 1e-9, f"max dev {d:.2e}")

# 3. HHI bounds and consistency with shares
d = con.execute("""
    SELECT COUNT(*) FROM panel_state_year
    WHERE hhi_oem < 0 OR hhi_oem > 10000 OR (n_oems = 1 AND ABS(hhi_oem - 10000) > 1)
""").fetchone()[0]
check("HHI in (0, 10000], =10000 iff single OEM", d == 0, f"{d} violations")

# 4. panel totals == raw registrations
d = con.execute("""
    WITH p AS (SELECT state_code, year, total_regs FROM panel_state_year),
         r AS (SELECT state_code, year, SUM("count") c FROM registrations GROUP BY 1, 2)
    SELECT COUNT(*) FROM p JOIN r USING (state_code, year) WHERE p.total_regs <> r.c
""").fetchone()[0]
check("panel totals match raw registrations", d == 0, f"{d} mismatches")

# 5. yoy growth recomputation
d = con.execute("""
    WITH t AS (
      SELECT state_code, year, total_regs,
             total_regs::DOUBLE / NULLIF(LAG(total_regs) OVER (PARTITION BY state_code ORDER BY year), 0) - 1 g
      FROM panel_state_year)
    SELECT MAX(ABS(p.yoy_growth - t.g)) FROM panel_state_year p
    JOIN t USING (state_code, year) WHERE p.yoy_growth IS NOT NULL
""").fetchone()[0]
check("yoy_growth recomputes", d < 1e-12, f"max dev {d:.2e}")

# 6. pp-change columns recompute
d = con.execute("""
    WITH t AS (
      SELECT state_code, year,
             (ev_share - LAG(ev_share) OVER (PARTITION BY state_code ORDER BY year)) * 100 c
      FROM panel_state_year)
    SELECT MAX(ABS(p.ev_share_chg_pp - t.c)) FROM panel_state_year p
    JOIN t USING (state_code, year) WHERE p.ev_share_chg_pp IS NOT NULL
""").fetchone()[0]
check("ev_share_chg_pp recomputes", d < 1e-12, f"max dev {d:.2e}")

# 7. external anchors (calendar 2024, full year)
row = con.execute("""
    SELECT total_regs, ev_share, cng_share, diesel_share FROM panel_state_year
    WHERE state_code = 'ALL' AND year = 2024
""").fetchone()
total24, ev24, cng24, dsl24 = row
check("2024 All-India total ~ 3.9-4.2M (FADA ~4.07M)", 3.8e6 < total24 < 4.3e6, f"{total24:,.0f}")
check("2024 EV share ~ 2.3-2.7% (public ~2.5%)", 0.022 < ev24 < 0.028, f"{ev24:.2%}")
check("2024 CNG share ~ 15-20%", 0.15 < cng24 < 0.20, f"{cng24:.2%}")
check("2024 diesel share ~ 15-23%", 0.14 < dsl24 < 0.24, f"{dsl24:.2%}")

# 8. Maruti national share ~ 40%
ms = con.execute("""
    SELECT share FROM maker_state_share WHERE state_code='ALL' AND year=2024 AND maker='Maruti Suzuki'
""").fetchone()[0]
check("Maruti 2024 share ~ 38-42%", 0.36 < ms < 0.44, f"{ms:.1%}")

# 9. fuel price join sanity (MH petrol 2024 ~ 103-108 INR)
fp = con.execute("""
    SELECT petrol_price_inr FROM panel_state_year WHERE state_code='MH' AND year=2024
""").fetchone()[0]
check("MH petrol price 2024 ~ 100-112", fp is not None and 100 < fp < 112, f"{fp}")

# 10. per-capita sanity: DL among top-5 states by regs per 1000 (2024)
pc = con.execute("""
    SELECT state_code FROM panel_state_year WHERE year=2024 AND state_code <> 'ALL'
    AND regs_per_1000_capita IS NOT NULL ORDER BY regs_per_1000_capita DESC LIMIT 5
""").df()["state_code"].tolist()
check("Delhi in top-5 per-capita registrations", "DL" in pc, f"top5={pc}")

# 11. wholesale (if present): Maruti wholesale share ~ retail share
tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
if "wholesale" in tables:
    wms = con.execute("""
        SELECT SUM(qty) FILTER (WHERE maker_vahan='Maruti Suzuki')::DOUBLE / SUM(qty)
        FROM wholesale WHERE year=2024
    """).fetchone()[0]
    check("Maruti wholesale share 2024 ~ retail ±5pp", abs(wms - ms) < 0.05, f"ws {wms:.1%} vs retail {ms:.1%}")

# 12. monthly panel: no negative counts anywhere
d = con.execute("SELECT COUNT(*) FROM registrations WHERE \"count\" < 0").fetchone()[0]
check("no negative registration counts", d == 0, f"{d}")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
raise SystemExit(1 if fails else 0)

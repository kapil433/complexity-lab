# Reference Source Roadmap

Last researched: **2026-06-13**

This is the acquisition queue for stronger external data. A source is not promoted
to `data/reference/` merely because it is official. It must also have a stable
download, documented grain, compatible geography, usable time coverage, and a
reproducible conversion.

## Acquired And Verified

| Priority | Candidate | Official source | Verified grain and coverage | Intended use | Promotion status |
|---|---|---|---|---|---|
| P0 | Constant-price per-capita NSDP | [RBI Handbook Table 20](https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/20T_111220252B6EE27737FD4931A99C5A448B7CEC68.XLSX) | State/UT x FY, FY2011-12 to FY2024-25, constant 2011-12 prices; latest years are missing for some states | Real-income levels and growth | Promoted to `state_income_constant.csv` and the annual panel |
| P0 | Constant-price GSDP | [RBI Handbook Table 22](https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/22T_11122025E6BC0CB35180406EAB6E0D49DE51C8E8.XLSX) | State/UT x FY, FY2011-12 to FY2024-25, constant 2011-12 prices | Real state-output levels and derived growth | Promoted to `state_gsdp.csv` and the annual panel |
| P1 | State road length | [RBI Handbook Table 146](https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/146T_11122025B89449F4159B420E8305A9509F27FE82.XLSX) | State/UT x end-March year, 2005-2020, kilometres | Slow infrastructure/accessibility context | Promoted as a constrained reference table; not silently joined to the panel |
| P1 | Scheduled-bank personal loans | [RBI Handbook Table 159](https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/159T_1112202552A28DBA4EF94487B4240BF86BC15692.XLSX) | State/UT x end-March year, 2004-2025, outstanding INR crore | Broad household credit-depth context | Promoted as a constrained reference table; never label as auto finance |

All three tables are from the [RBI Handbook of Statistics on Indian States
2024-25](https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20States),
published on 11 December 2025.

### Mandatory interpretation rules

- Table 20 is preferable to current-price Table 19 for real-income change. The
  fiscal-year/calendar-year join remains approximate.
- Table 146 is sourced by RBI from the Ministry of Road Transport and Highways.
  Large jumps can reflect definition, reporting, or boundary changes, not road
  construction alone. Andhra Pradesh includes Telangana through 2013.
- Table 159 covers personal loans outstanding at scheduled commercial banks. It
  does **not** measure vehicle-loan penetration, approval rates, NBFC lending,
  interest rates, or OEM captive finance.
- Dadra & Nagar Haveli and Daman & Diu source rows require aggregation to the
  current merged-UT code. Pre-reorganisation Jammu & Kashmir includes Ladakh.

Reproducible converters:

```powershell
uv run --with openpyxl python scripts/convert_rbi_nsdp.py `
  data/raw/rbi/table20_pc_nsdp_constant_2024-25.xlsx --kind constant

uv run --with openpyxl python scripts/convert_rbi_gsdp.py

uv run --with openpyxl python scripts/convert_rbi_state_series.py roads `
  data/raw/rbi/table146_state_road_length_2024-25.xlsx

uv run --with openpyxl python scripts/convert_rbi_state_series.py personal-loans `
  data/raw/rbi/table159_state_personal_loans_2024-25.xlsx
```

Promotion checks cover generated-file row counts, unique state-period keys,
state-code validation, catalog entries, panel/UI provenance, and the full
ingest/test run.

## Official Sources Still Needing A Reproducible Extract

| Need | Best authority | Current finding | Lab decision |
|---|---|---|---|
| Annual state population | Ministry of Health and Family Welfare population projections, then Census of India | A stable official state-year extract was not verified. The lab now generates 2012-2026 estimates between 2011/2024 anchors and holds 2011 urban shares fixed | Permit estimated denominators with visible method/quality; do not call them observations |
| Historical public EV chargers | Bureau of Energy Efficiency / Ministry of Power, including EV Yatra | Official dashboards and government answers provide snapshots, but no stable state-year download has been archived locally | Keep the 2025 cross-section constrained; acquire dated snapshots before panel use |
| Historical CNG stations | PNGRB | Current state/GA snapshots are authoritative; a consistent historical state-year series was not found | Keep 2024 cross-section constrained |
| Historical retail fuel prices | PPAC and oil marketing companies | Official snapshots exist, but a complete state/city daily archive is not exposed as a simple download | Retain modeled series as approximate/proxy and expose basis |
| State road-tax history | State transport departments | Notifications are fragmented by state, vehicle type, price slab, cess, and effective date | Keep the simplified 2024 cross-section constrained |

## Not Available At The Required Grain

| Need | Why it remains unavailable | What would qualify |
|---|---|---|
| State auto-finance penetration | No defensible public state x year passenger-vehicle finance series covering banks, NBFCs, and captive financiers was found. RBI personal loans are a broad credit proxy only | Regulatory or industry microdata with vehicle-loan purpose, state, period, lender coverage, and denominator |
| State/OEM dealer counts over time | FADA commentary and OEM locators do not form a historical, deduplicated dealer panel | Dated OEM dealer-locator snapshots with outlet identity, city/state, brand, opening/closure dates |
| Wholesale fuel split | The proprietary wholesale source has no fuel/powertrain quantity field | A source-supplied model x fuel x geography x month quantity table |

Personal loans may support an explicitly named **credit depth** experiment. They
must not be used to fill or rename the vehicle-finance gap in
`known_data_gaps.csv`.

## Revised Acquisition Order

1. Replace the estimated annual population denominator with an archived official
   state-year population projection series.
2. Build dated BEE/Ministry of Power and PNGRB snapshot collectors before claiming
   charger or CNG-station dynamics.
3. Add optional road-infrastructure and credit-depth experiments only after
   normalization choices and geographic boundary handling are explicit.
4. Treat auto finance and dealer history as new data-acquisition projects, not
   fields that can be inferred from broad proxies.

# Data dictionary

## DuckDB tables (`data/lab.duckdb`, rebuilt via `uv run lab ingest && uv run lab panel`)

| Table | Grain | Notes |
|---|---|---|
| `registrations` | state × year × month × maker × fuel | Decoded from `vahan_master.json.gz`. 'All India' (`ALL`) is **pre-aggregated** — never sum states to reproduce it. |
| `events` | event | Policy/data-break timeline embedded in the bundle (47 events, tiered). |
| `meta` | key/value | Bundle metadata incl. partial-year flags. |
| `dim_state` | state | From `reference/states.csv`; includes GeoJSON name mapping. |
| `ref_*` | varies | One table per reference CSV (below). |
| `reference_availability` | reference dataset | Governing status, scope, time coverage, approved use, unavailable fields and observed file facts from `reference_catalog.csv`. |
| `panel_state_month` | state × month | Fuel pivots, EV/CNG shares, OEM HHI/entropy. |
| `panel_state_year` | state × year | Same + YoY growth + covariates joined. |
| `oem_state_edges` | state × maker × year | Network edge list (view). |
| `wholesale` | city × model × month | **Local only** (proprietary; never committed). FY2017-18→present. Built by `lab wholesale`. |
| `ws_model_month`, `ws_maker_month`, `ws_state_month`, `ws_segment_month` | views | Wholesale aggregates; state view excludes unmapped cities (~3.7% of volume overall after the current mapping). |
| `ws_ev_month` | view | Dispatches of **EV-only nameplates**. This is a model subset, not a wholesale EV/fuel cut; mixed-fuel nameplates cannot be split. |
| `ws_fuel_month` | view | **Legacy nameplate proxy, not a wholesale fuel cut.** It assigns every model to one externally inferred `primary_fuel`; do not report it as observed fuel mix/share/volume. |
| `retail_wholesale_month` | month | National retail vs wholesale join, full-coverage era only — the nowcasting workhorse. |

## Known caveats (read before inferring)

1. **No separate Telangana.** The bundle's 35 regions exclude Telangana; the AP
   series is continuous through the 2014 bifurcation (see `events` id A01).
   When joining covariates to AP, consider that AP registrations may span
   undivided AP — income/urbanization for residual AP are not strictly aligned.
2. **Partial years.** 2026 (and the latest 1–2 months generally) are partial —
   `meta` flags them; experiments use `max(year) - 1` as the latest full year.
3. **All India ≠ Σ states** by design (different RTO coverage).
4. **Covariate quality flags.** Every reference CSV carries `source` and
   `quality` columns: `official` > `official_derived` > `reported` >
   `approximate` > `proxy` > `estimate` > `placeholder`. Filter on them.
5. **Wholesale coverage break (2022-04).** Before FY2022-23 the wholesale
   source is a ~50-city sample (~7% of industry volume); after, full industry.
   Rows carry a `coverage` flag (`sample`/`full`) — most analyses should filter
   `coverage = 'full'`. Maruti's ARENA/NEXA channels are merged into
   `maker = 'Maruti Suzuki'` (channel kept in `channel`); `maker_vahan` maps to
   the registration bundle's OEM names (e.g. Skoda→Volkswagen Group,
   Citroen/Fiat→Stellantis) for cross-source joins.
6. **Wholesale data is proprietary** — the raw XLSB and all derived caches are
   gitignored (`data/raw/wholesale*`); only the city→state mapping is committed.
7. **Wholesale has no fuel cut.** The source has no fuel/powertrain column and
   supplies no fuel-wise quantity split. `model_fuel_map.csv`, `ws_ev_month`, and
   `ws_fuel_month` add model-level metadata only. They cannot split mixed models
   such as Nexon into Petrol/Diesel/EV dispatches. Do not call these outputs
   wholesale fuel mix, fuel share, or fuel volume.
8. **Strong Hybrid is censored before 2024 in Vahan.** `hybrid_regs` is exactly
   zero until 2023 and jumps in 2024 — a fuel-classification reporting break,
   not a sales fact (hybrids sold from ~2017 are classified as Petrol pre-2024).
   Wholesale can show dispatches of hybrid-only or hybrid-associated nameplates,
   but cannot provide a fuel cut for mixed nameplates. Never fit adoption curves
   to the Vahan hybrid series across the 2024 boundary.

## Reference CSVs (`data/reference/`)

The streamlined availability contract is
[`reference_catalog.csv`](../data/reference/reference_catalog.csv); the readable
usage guide is [`docs/reference-data.md`](reference-data.md). Use
`uv run lab references` to print the current status table.

| File | Coverage | Quality | Source |
|---|---|---|---|
| `reference_catalog.csv` | all reference files | governing metadata | Local audited contract: usable / constrained / unavailable |
| `states.csv` | 36 + ALL | — | Canonical dim (codes, zones, GeoJSON names) |
| `state_income.csv` | 33 states, FY2011-12→2024-25 | official | RBI Handbook of Statistics on Indian States 2024-25, Table 19 |
| `state_income_constant.csv` | 33 states, FY2011-12 to 2024-25 | official | RBI Handbook 2024-25, Table 20 |
| `state_gsdp.csv` | 33 states, FY2011-12 to 2024-25 | official/derived | RBI Handbook 2024-25, Table 22; growth derived from constant-price levels |
| `state_road_length.csv` | ALL + 35 states/UTs, 2005-2020 | official/official_derived | RBI Table 146; underlying source MoRTH |
| `state_personal_loans.csv` | ALL + 36 states/UTs, 2004-2025 | official/official_derived | RBI Table 159; broad personal loans, not auto finance |
| `state_credit_depth.csv` | ALL + 36 states/UTs, 2012-2025 | estimate | RBI personal-loan stock per estimated population; not vehicle finance |
| `state_population_annual.csv` | ALL + 36 states/UTs, 2012-2026 | estimate | Interpolation/extrapolation from 2011/2024 anchors; 2011 urban shares fixed |
| `urbanization.csv` | all states | official/derived | Census of India 2011 |
| `cng_stations.csv` | all states, 2024 (+ national 2025) | official_derived | PNGRB RTI R-1855 (31.05.2024), GA→state allocation |
| `ev_charging.csv` | incomplete state allocation 2025, selected states 2024 | reported/approximate | Ministry of Power via ORF/PIB; stored 2025 states cover 77.65% of national total |
| `fuel_prices.csv` | Delhi 2012–2026; 33 states 2017–2026 (GA/NE/AN/DN 2022–26 only); CNG 7 states (annual avg), ALL=Delhi proxy | approximate | Delhi: PPAC/IOCL/IGL compiled. States: Delhi series + capital-city differentials from era-anchored RSP snapshots 2019/2021/2025 (PPAC/OMC-sourced); see `scripts/compile_state_fuel_prices.py`. Caveat: HR/PB use shared capital Chandigarh (Punjab in-state pumps ~₹3/l higher) |
| `road_tax.csv` | 25 states, as-of 2024 | approximate | State transport dept notifications, single-band simplification |
| `vehicle_lifetime_tax.csv` | 25 states x 5 fuel labels, as-of 2024 | approximate | Normalized INR 10 lakh benchmark; non-EV fuels repeat ICE rate where not distinguished |
| `policy_events.csv` | 27 events 2013–2025 | official | MoHI/MoRTH/GST Council/state EV policies |
| `policy_events_canonical.csv` | 74 bundle + curated records, 2008-2025 | reported/official | Unified origins, tiers, scopes, and overlap flags |
| `dealer_counts.csv` | zero-row acquisition schema | **unavailable for modelling** | No defensible state x OEM x year panel acquired |
| `financing.csv` | five national anchors | **unavailable for state/OEM modelling** | CRISIL/JATO/industry |
| `state_adjacency.csv` | 68 land borders | — | Hand-compiled pair list (islands have none; DL enclosed by HR/UP) |
| `model_fuel_map.csv` | 120 nameplates ≈99.8% of wholesale volume | approximate | OEM lineups; `ev_only` flag is the exact subset |

## Logged data TODOs

- **Promoted RBI upgrades:** constant-price per-capita NSDP (Table 20), constant-price
  GSDP (Table 22), state road length (Table 146), and scheduled-bank personal loans
  (Table 159). The latter is
  broad credit depth, not vehicle-finance penetration; see
  [`reference-source-roadmap.md`](reference-source-roadmap.md).

- **Gujarat CNG price series** (largest CNG market; no archived city anchors found —
  petrol/diesel covered, CNG falls back to the Delhi proxy).
- **Pre-2017 state fuel price levels** (daily-pricing era only; earlier years fall
  back to the ALL proxy by design).
- **CNG station history** (pre-2024 state series; only national anchors exist here).
- **EV charger time series** (currently a 2025 cross-section + 2024 partial).
- **State-wise dealer counts** (FADA or OEM dealer-locator scrape).
- **AP+Telangana covariate reconciliation** (population-weighted combination).
- **Wholesale city→state mapping tail** (~3.7% of volume unmapped overall; continue
  extending `city_state.csv`, while leaving `OTHERS`/`NCR` unmapped).

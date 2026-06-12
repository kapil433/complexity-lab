# Data dictionary

## DuckDB tables (`data/lab.duckdb`, rebuilt via `uv run lab ingest && uv run lab panel`)

| Table | Grain | Notes |
|---|---|---|
| `registrations` | state × year × month × maker × fuel | Decoded from `vahan_master.json.gz`. 'All India' (`ALL`) is **pre-aggregated** — never sum states to reproduce it. |
| `events` | event | Policy/data-break timeline embedded in the bundle (47 events, tiered). |
| `meta` | key/value | Bundle metadata incl. partial-year flags. |
| `dim_state` | state | From `reference/states.csv`; includes GeoJSON name mapping. |
| `ref_*` | varies | One table per reference CSV (below). |
| `panel_state_month` | state × month | Fuel pivots, EV/CNG shares, OEM HHI/entropy. |
| `panel_state_year` | state × year | Same + YoY growth + covariates joined. |
| `oem_state_edges` | state × maker × year | Network edge list (view). |
| `wholesale` | city × model × month | **Local only** (proprietary; never committed). FY2017-18→present. Built by `lab wholesale`. |
| `ws_model_month`, `ws_maker_month`, `ws_state_month`, `ws_segment_month` | views | Wholesale aggregates; state view excludes unmapped cities (~6% of volume). |
| `ws_ev_month` | view | EV dispatches from **EV-only nameplates** (exact but undercounts: multi-fuel nameplates' EV variants excluded). |
| `ws_fuel_month` | view | Approximate fuel mix of dispatches via each nameplate's `primary_fuel` (see `model_fuel_map.csv`). |
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

## Reference CSVs (`data/reference/`)

| File | Coverage | Quality | Source |
|---|---|---|---|
| `states.csv` | 36 + ALL | — | Canonical dim (codes, zones, GeoJSON names) |
| `state_income.csv` | 33 states, FY2011-12→2024-25 | official | RBI Handbook of Statistics on Indian States 2024-25, Table 19 |
| `urbanization.csv` | all states | official/derived | Census of India 2011 |
| `cng_stations.csv` | all states, 2024 (+ national 2025) | official_derived | PNGRB RTI R-1855 (31.05.2024), GA→state allocation |
| `ev_charging.csv` | all states 2025, partial 2024 | reported/approximate | Ministry of Power via ORF/PIB |
| `fuel_prices.csv` | Delhi 2012–2026; 33 states 2017–2026 (GA/NE/AN/DN 2022–26 only); CNG 7 states (annual avg), ALL=Delhi proxy | approximate | Delhi: PPAC/IOCL/IGL compiled. States: Delhi series + capital-city differentials from era-anchored RSP snapshots 2019/2021/2025 (PPAC/OMC-sourced); see `scripts/compile_state_fuel_prices.py`. Caveat: HR/PB use shared capital Chandigarh (Punjab in-state pumps ~₹3/l higher) |
| `road_tax.csv` | 25 states, as-of 2024 | approximate | State transport dept notifications, single-band simplification |
| `policy_events.csv` | 27 events 2013–2025 | official | MoHI/MoRTH/GST Council/state EV policies |
| `dealer_counts.csv` | national only | placeholder | FADA commentary |
| `financing.csv` | national, sparse | estimate | CRISIL/JATO/industry |
| `state_adjacency.csv` | 68 land borders | — | Hand-compiled pair list (islands have none; DL enclosed by HR/UP) |
| `model_fuel_map.csv` | 120 nameplates ≈99.8% of wholesale volume | approximate | OEM lineups; `ev_only` flag is the exact subset |

## Logged data TODOs

- **Gujarat CNG price series** (largest CNG market; no archived city anchors found —
  petrol/diesel covered, CNG falls back to the Delhi proxy).
- **Pre-2017 state fuel price levels** (daily-pricing era only; earlier years fall
  back to the ALL proxy by design).
- **CNG station history** (pre-2024 state series; only national anchors exist here).
- **EV charger time series** (currently a 2025 cross-section + 2024 partial).
- **State-wise dealer counts** (FADA or OEM dealer-locator scrape).
- **AP+Telangana covariate reconciliation** (population-weighted combination).
- **Wholesale city→state mapping tail** (~6% of volume unmapped; extend
  `city_state.csv` beyond the top 250 cities).

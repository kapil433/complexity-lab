# Reference Data Guide

The governing machine-readable catalog is
[`data/reference/reference_catalog.csv`](../data/reference/reference_catalog.csv).
Run this at any time to see the current availability report:

```powershell
uv run lab references
```

## Status Meaning

| Status | Meaning | App behavior |
|---|---|---|
| `usable` | Suitable for its stated grain and period. Normal provenance labels still apply. | Show |
| `constrained` | Useful only with an explicit period, geography, quality, or interpretation warning. | Warn |
| `unavailable` | The required analytical dataset does not exist locally at a defensible grain. | Hide from modelling |

## Current Decision Table

| Dataset | Status | Use it for | Do not use it for |
|---|---|---|---|
| State income | Usable | FY annual income levels and panel analysis for covered states | Real-income growth without constant-price adjustment; DN/LA/LD |
| Constant-price state income | Usable | Real-income levels and growth | FY/calendar alignment; DN/LA/LD/ALL |
| Constant-price GSDP | Usable | Real state-output levels and derived annual growth | FY/calendar alignment; missing latest years; DN/LA/LD/ALL |
| State road length | Constrained | Pre-2021 infrastructure context | Post-2020 conditions or literal construction growth across reporting breaks |
| Personal loans | Constrained | Broad scheduled-bank household credit depth | Auto-finance penetration, NBFC or captive-finance coverage |
| Per-capita credit depth | Constrained | Broad personal-loan stock per estimated resident | Vehicle-finance penetration or approval rates |
| Urbanization | Constrained | Census-2011 structural cross-state context | Annual urbanization change |
| Population anchors | Constrained | Census/projection anchor checks | Annual observed population |
| Annual population estimate | Constrained | 2012-2026 rate denominators and fixed-share urban/rural context | Observed annual population or annual urbanization |
| CNG stations | Constrained | Reconciled snapshot on 31 May 2024 | Pre-2024 history or a 2025 state split |
| EV charging | Constrained | Selected-state snapshot comparisons with coverage shown | A complete 2025 allocation or historical panel regressions |
| Fuel prices | Constrained | Broad annual trends and shocks with basis/quality shown | Pump-level accounting or silent Delhi-proxy use |
| Road tax | Constrained | Approximate 2024 ordinal policy comparison | Invoice calculation or historical tax panels |
| Fuel-shaped lifetime tax | Constrained | Current INR 10 lakh benchmark across five labels | Independent fuel schedules where the source only gives ICE/EV |
| Policy events | Constrained | Context and pre-specified event studies | Exhaustive policy coverage or causality by annotation |
| Canonical policy events | Constrained | One timeline with origin and overlap flags | Deduplicated causal treatments |
| Financing | Unavailable | National narrative context only | State/OEM/model regressions |
| Dealer counts | Unavailable | Empty acquisition schema only | Dealer-network or state-access inference |
| Model fuel metadata | Constrained | EV-only versus mixed-fuel nameplate classification | Any wholesale fuel cut, share, or volume |

The stronger-source acquisition queue, exact official downloads, and promotion
criteria are in
[`docs/reference-source-roadmap.md`](reference-source-roadmap.md).

## Panel Provenance

After `uv run lab ingest && uv run lab panel`, `panel_state_year` carries:

- Annual estimated population, urban/rural counts, method, source, and quality.
- Current and constant-price income FY, source, and quality.
- Constant-price GSDP, derived real growth, source, and quality.
- Personal-loan stock and per-capita broad credit depth.
- Urbanization census year, source, and quality.
- CNG-station and EV-charger snapshot date, source, quality, coverage scope, and
  state-allocation coverage.
- Petrol, diesel, and CNG price source, quality, and basis.

Fuel-price basis is either:

- `state`: a state/capital series exists.
- `ALL/Delhi fallback`: the state value was unavailable and the national Delhi
  proxy was used.

`regs_per_1000_population` and the compatibility alias `regs_per_1000_capita` use
the annual estimated population. `regs_per_1000_population_2024` remains the
fixed-2024 sensitivity field.

## Adding or Replacing Data

1. Add or replace the CSV under `data/reference/`.
2. Update `reference_catalog.csv` with status, coverage, approved use, and what is
   unavailable.
3. Include row-level `source` and `quality` columns where applicable.
4. Run:

```powershell
uv run lab references
uv run lab ingest
uv run lab panel
uv run pytest
```

The ingest fails when a CSV is missing from the catalog, the catalog names a missing
file, statuses are invalid, or state codes are unknown.

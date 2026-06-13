# Reference Data Guide

The governing catalog is
[`data/reference/reference_catalog.csv`](../data/reference/reference_catalog.csv).
Only experiment-ready analytical datasets belong in `data/reference/`.
Generator-only inputs are preserved under `data/raw/reference_inputs/`.

```powershell
uv run lab references
```

## Canonical Interfaces

Experiments must use:

| Interface | Grain | Intended use |
|---|---|---|
| `experiment_state_year` | state x year | Vahan outcomes plus annual estimated population, real income, real GSDP, broad credit depth, and fuel prices |
| `experiment_state_context` | state | Latest real macro context, dated 2024 CNG snapshot, incomplete 2025 EV-charger snapshot, and current tax benchmark |
| `ref_policy_events_canonical` | event | Policy/event overlays with origin and overlap flags |

The experiment runner records declared dependencies and the reference-catalog
SHA-256 in every `manifest.json`. Contract tests reject nominal income and deleted
reference tables in registered or published experiment code.

## Decision Table

| Dataset | Status | Approved use | Not approved |
|---|---|---|---|
| Constant-price state income | Usable | Real income levels and cross-state context | FY/calendar precision; missing DN/LA/LD/ALL |
| Constant-price GSDP | Usable | Real output levels and derived growth | Missing latest years; exact calendar-year causality |
| Annual population estimate | Constrained | 2012-2026 denominators | Observed population or changing urbanization |
| Broad credit depth | Constrained | Scheduled-bank personal-loan context | Vehicle-finance penetration, NBFC, or captive finance |
| CNG stations | Constrained | Reconciled 31 May 2024 state snapshot | Historical state panel or 2025 state split |
| EV charging | Constrained | Dated cross-state context with 77.65% reconciliation shown | Complete 2025 census or historical treatment |
| Fuel prices | Constrained | Broad annual trend/shock context | Pump-level accounting or silent Delhi-proxy use |
| Vehicle lifetime tax | Constrained | Current INR 10 lakh ordinal comparison | Invoice calculation or historical tax panel |
| Canonical policy events | Constrained | Context and pre-specified event studies | Automatic causal treatment assignment |
| State road length | Constrained | Pre-2021 infrastructure context | Current infrastructure or literal construction growth |
| Model fuel metadata | Constrained | EV-only/mixed-nameplate classification | Wholesale fuel cut, share, or volume |
| Vehicle finance and dealer network | Unavailable | Display through `known_data_gaps.csv` | Any modelling effect |

Wholesale has **no fuel cut**. Model metadata cannot split mixed-fuel nameplate
dispatches.

## Refresh Rules

1. Preserve official/raw source material under `data/raw/`.
2. Generate one canonical analytical CSV per concept under `data/reference/`.
3. Delete superseded analytical duplicates and observation-shaped placeholders.
4. Update `reference_catalog.csv`, `DATA_TRUTH.md`, and contract tests.
5. Run:

```powershell
uv run lab references
uv run lab ingest
uv run lab panel
uv run pytest
uv run ruff check .
```

The loader fails when analytical files and the catalog differ or state codes are
unknown.

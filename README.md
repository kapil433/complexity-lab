# Complexity Lab

A personal research lab for studying **India's passenger-vehicle market as a complex system**,
built on VAHAN registration data (2012–2026, state × month × OEM × fuel) enriched with
state-level covariates — per-capita income, urbanization, CNG/EV infrastructure, state fuel
prices, road tax, policy events, population — and a proprietary wholesale dispatch dataset
(city × model × month, local only).

**Live lab notebook**: [kapil433.github.io/complexity-lab](https://kapil433.github.io/complexity-lab/) —
13 experiments with full methodological cards, light/dark theme.

| Layer | Where | What it answers |
|---|---|---|
| Descriptive | `analysis/descriptive`, Macro Dashboard | Size, growth, shares, concentration, seasonality |
| Distributions | `analysis/distributions` | Power laws, rank–size, Gini |
| Econometrics | `analysis/econometrics` | Panel FE regression, Granger, changepoints, DiD with placebos |
| Forecasting | `analysis/forecast`, `analysis/nowcast` | Backtested SARIMA/Holt-Winters/naive; wholesale→retail nowcast |
| Networks | `networks/` | Bipartite OEM–state graphs, contagion, network inference + nulls |
| Complexity | `complexity/` | HMM fuel regimes, early-warning signals, tipping points, survival |
| Simulation | `simulation/` | Bass diffusion & counterfactuals, ABM, demand/supply shock model |

## Quickstart

```powershell
uv sync --all-extras           # environment
uv run lab ingest              # raw bundle + reference CSVs -> data/lab.duckdb
uv run lab panel               # state x month / state x year analysis panels
uv run lab wholesale           # local-only proprietary dispatches (optional)
uv run lab list                # registered experiments
uv run lab run descriptive-baseline
uv run lab app                 # interactive lab -> http://localhost:8501
```

## The interactive lab (9 pages)

Macro Dashboard · Explorer · Networks · Diffusion Lab (user-controlled fit windows +
sensitivity scans) · Hypothesis Tester (period slider, wholesale covariates) ·
Wholesale (nowcast, models, segments, EV proxy) · Phase Transitions (percolation,
tipping, Markov + HMM regimes) · Forecast Studio (champion-by-backtest) · Shock Lab
(stock-and-flow channel simulation). Light/dark via app menu → Settings.

Every page opens with an explainer card (question, method, plain-English concepts,
math with toy examples, interpretation guide, limits) — same content as the site's
[experiment guide](https://kapil433.github.io/complexity-lab/experiments/guide.html).

## Experiments (the published notebook)

001 descriptive baseline · 002 EV diffusion (Bass) · 003 OEM–state network ·
004 wholesale↔retail nowcast · 005 phase transitions · 006 EV tipping points ·
007 EV contagion (Moran's I + threshold cascades) · 008 HMM fuel regimes ·
009 adoption-network horse race (+ out-of-sample + rewiring null) ·
010 SHEV structural isolation (lead paper) · 011 regime-switch survival ·
012 hatchback→SUV transition (τ\* ≈ 30%) · 013 SHEV tax-parity counterfactual.

Add your own: copy `experiments/_template.qmd`, number it, commit — CI renders it
into the site. Conventions in [docs/lab-guide.md](docs/lab-guide.md).

## Engineering

- **Validation in CI**: `scripts/validate_numbers.py` runs on every push — internal
  identities (shares sum to 1, panel == raw totals) plus external anchors (FADA-scale
  totals, public EV share, Maruti share, wholesale↔retail agreement).
- **Reproducibility**: DuckDB is a build artifact; everything rebuilds from the
  committed bundle + reference CSVs. `_freeze/` carries locally-executed notebook
  results so CI can publish wholesale-dependent experiments without the data.
- **Data refresh**: monthly ritual in [docs/refresh-runbook.md](docs/refresh-runbook.md).
- 70+ tests; ruff; experiment registry with timestamped, manifest-ed artifacts.

## Data, licensing, caveats

- Registration data: **Vahan Intelligence** ([vahanintelligence.in](https://www.vahanintelligence.in)),
  based on VAHAN/Parivahan public data (MoRTH, GoI) — research use with attribution.
- Reference CSVs carry per-file provenance (`source`, `quality` columns); read
  [docs/data-dictionary.md](docs/data-dictionary.md) **before inferring** — it documents
  the seven caveats that bite (Telangana, partial years, the wholesale coverage break,
  the 2024 hybrid classification break, …).
- The wholesale dataset is proprietary: raw and derived files are gitignored; only
  aggregate chart outputs appear in published experiments.
- Code: MIT ([LICENSE](LICENSE)).

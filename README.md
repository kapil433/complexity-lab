# Complexity Lab

A personal research lab for studying **India's passenger-vehicle market as a complex system**,
built on VAHAN registration data (2012–2026, state × month × OEM × fuel) enriched with
state-level covariates: per-capita income, urbanization, CNG/EV infrastructure, fuel prices,
road tax, policy events, dealer footprint and financing penetration.

The lab spans the full analytical ladder:

| Layer | Module | What it answers |
|---|---|---|
| Descriptive | `complexity_lab.analysis.descriptive` | Market size, growth, fuel mix, seasonality, concentration (HHI) |
| Distributions | `complexity_lab.analysis.distributions` | Power-law / lognormal fits, rank–size, Gini |
| Econometrics | `complexity_lab.analysis.econometrics` | Panel correlations & regressions, Granger causality, changepoints |
| Networks | `complexity_lab.networks` | Bipartite OEM–state graphs, centrality, communities, temporal evolution |
| Complexity | `complexity_lab.complexity` | Diversity/entropy indices, early-warning signals, regime shifts |
| Simulation | `complexity_lab.simulation` | Bass diffusion fits & scenarios, agent-based adoption models |

## Quickstart

```powershell
uv sync --all-extras          # create env & install
uv run lab ingest             # build data/lab.duckdb from raw + reference data
uv run lab panel              # build the state×month / state×year analysis panels
uv run lab list               # list registered experiments
uv run lab run descriptive-baseline
uv run lab app                # launch the interactive Streamlit lab
```

Experiments live in `experiments/` as Quarto documents and are rendered to a website
(GitHub Pages) on every push — the published lab notebook.

## Layout

```
data/raw/         VAHAN master bundle (committed, compressed) + India states GeoJSON
data/reference/   Enrichment CSVs with provenance (income, infra, fuel prices, tax, events…)
data/lab.duckdb   Built analytical database (gitignored — rebuild with `lab ingest`)
src/complexity_lab/   The package: data, analysis, networks, complexity, simulation, experiments
app/              Streamlit lab (Explorer, Networks, Diffusion Lab, Hypothesis Tester)
experiments/      Quarto experiment notebook — one .qmd per numbered experiment
docs/             Research questions, data dictionary, reading list, lab guide
outputs/          Run artifacts (gitignored)
```

## Adding an experiment

See [docs/lab-guide.md](docs/lab-guide.md). Short version: copy `experiments/_template.qmd`,
number it, state the hypothesis, run analysis against the panel tables, commit — CI renders it
into the site.

## Data attribution

- Registration data: **Vahan Intelligence** ([vahanintelligence.in](https://www.vahanintelligence.in)),
  based on VAHAN/Parivahan public data (MoRTH, Government of India). Free for research with attribution.
- Reference datasets carry per-file provenance headers (`source`, `as_of`, `quality`) —
  see [docs/data-dictionary.md](docs/data-dictionary.md). Several series are flagged
  `estimate`/`partial`; treat them accordingly in inference.

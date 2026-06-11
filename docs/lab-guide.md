# Lab guide — how to run and extend the lab

## Daily loop

```powershell
uv run lab list                       # what experiments exist
uv run lab run <name>                 # scripted run -> outputs/<name>/<timestamp>/
uv run lab app                        # interactive Streamlit lab
quarto preview                        # the published notebook, locally
```

Rebuild the database after changing raw/reference data:

```powershell
uv run lab ingest
uv run lab panel
uv run lab wholesale            # local-only proprietary source (uses parquet cache)
uv run lab wholesale --refresh  # re-read the source XLSB after it's updated
```

## Adding an experiment (the contract)

1. **Notebook**: copy `experiments/_template.qmd` → `experiments/NNN-slug.qmd`.
   State the question, run the analysis against `panel_state_year` /
   `panel_state_month` / `oem_state_edges`, write the finding. Remove
   `draft: true`. Add a row to `experiments/index.qmd`. Commit — CI renders it.
2. **Scripted (optional but encouraged)**: register a function in
   `src/complexity_lab/experiments/builtin.py` (or a new module imported there)
   with `@experiment("NNN-slug", description=...)`. It gets `lab run` support
   and artifact/manifest management for free.
3. **New reusable logic** goes in the package (`analysis/`, `networks/`,
   `complexity/`, `simulation/`) **with a unit test** on a synthetic fixture —
   not inline in the notebook. Notebooks call the package.

## Adding a reference dataset

1. Drop `data/reference/<name>.csv` with `#` provenance header lines and
   `source`/`quality` columns; key states by `state_code` (validated against
   `states.csv` at ingest — unknown codes fail loudly).
2. Re-run `uv run lab ingest`; the table appears as `ref_<name>`.
3. Join it in `src/complexity_lab/data/panel.py` if it belongs on the panel.
4. Document it in `docs/data-dictionary.md` (and its quality caveats).

## Conventions

- `state_code = 'ALL'` rows are pre-aggregated All-India — filter for cross-state work.
- Latest calendar year is partial: use `max(year) - 1`.
- Money in INR; shares as fractions (0–1); HHI on the 0–10000 scale.
- Run `uv run pytest` and `uv run ruff check .` before pushing (CI enforces both).

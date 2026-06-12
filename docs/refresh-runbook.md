# Data refresh runbook

The monthly ritual when new data lands. Total time: ~15 minutes.

## 1. New VAHAN bundle (from vahanintelligence.in)

```powershell
# replace the bundle, keep the same filename
Copy-Item <new>\vahan_master.json.gz data\raw\vahan_master.json.gz
uv run lab ingest
uv run lab panel
uv run python scripts/validate_numbers.py   # MUST pass — checks identities + external anchors
```

If validation fails on an *anchor* (e.g. a new year shifted the 2024 totals),
inspect before changing the check — anchors exist to catch silent data breaks.

## 2. New wholesale workbook (proprietary, local only)

```powershell
# drop the new XLSB into the wholesale folder (LAB_WHOLESALE_DIR or the default
# D:\...\Wholesale Data). The newest .xlsb in that folder is picked automatically.
uv run lab wholesale --refresh        # re-reads the source, rebuilds cache + views
uv run python scripts/validate_numbers.py
```

Check the summary it prints: `date_range` should now include the new months and
`unmapped_state_volume_pct` should stay below 4% (a jump means new city names —
extend `data/reference/city_state.csv`, but do not guess non-geographic buckets).
New model names → extend
`data/reference/model_fuel_map.csv` (check coverage with
`scripts/oneoff/check_fuel_map.py`).

## 3. Re-run experiments & publish

```powershell
uv run lab list                                  # registry
uv run lab run wholesale-retail-nowcast          # or whichever you care about
quarto render                                    # executes notebooks, updates _freeze/
git add -A; git commit -m "Data refresh <month>"; git push
```

**The freeze rule**: `_freeze/` is committed on purpose. CI has no wholesale
data — it publishes whatever execution results you rendered locally. So:

- after a data refresh or after editing any wholesale-dependent notebook
  (004, 010, 012, 013), run `quarto render` locally **before pushing**;
- if you push a notebook edit without re-rendering, CI re-executes that page
  without the data and publishes it with the wholesale sections skipped.

## 4. Annual reference updates

| Series | Source | Helper |
|---|---|---|
| Per-capita NSDP | RBI Handbook (December release), Table 19 XLSX | `uv run --with openpyxl python scripts/convert_rbi_nsdp.py <xlsx>` |
| State fuel prices | PPAC/OMC RSP snapshots | `scripts/compile_state_fuel_prices.py` |
| CNG stations | PNGRB GA-wise table | manual → `data/reference/cng_stations.csv` |
| EV chargers | Ministry of Power / BEE releases | manual → `data/reference/ev_charging.csv` |
| Policy events | budget/GST/state EV announcements | manual → `data/reference/policy_events.csv` |

After any reference edit: `uv run lab ingest && uv run lab panel` (the loader
validates state codes and the panel picks the new joins up automatically),
then the validation script.

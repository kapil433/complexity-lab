# Science Playground

The playground is 50 pre-specified experiments. The contract for each one —
hypothesis, null, method, variables, knobs, and the sentence it must not
support — lives in `src/complexity_lab/playground/catalog.py`. The executor
for that id lives beside it. A test fails if the two lists diverge.

## How a run is allowed to change

Move one knob and run again. The interpretation is a function of the numbers
and that knob. Examples that are tested directly:

- A Zipf tolerance can withdraw the Zipf description without refitting a new slope.
- Year effects on or off change what an income coefficient is allowed to mean.
- A scenario shock of zero leaves the seasonal path untouched. A non-zero shock
  is labelled a simulation, not a forecast.
- A self-transition bar of 0.95 is a strict absorption rule. A bar of 0.50 is not.

## What the variables are

| Variable | Role | Boundary |
|---|---|---|
| Vahan counts and shares | Outcomes | All India is its own series. Telangana is absent. Strong hybrid breaks in 2024. |
| Real per-capita NSDP | Income context | RBI Table 20, financial year, constant 2011-12 prices |
| Real GSDP growth | State output context | RBI Table 22. Not World Bank national GDP |
| Population | Denominator | Estimate. Urban share is Census 2011, held fixed |
| Fuel prices | Approximate annual prices | Basis is state or Delhi fallback, and the basis is disclosed |
| Personal loans per person | Broad credit depth | Not vehicle finance |
| World Bank India GDP, population, CPI | National context only | Fetched, plausibility-gated, never copied into a state hole |

## Sources that were not added

Daily city fuel prices from data.gov.in were not retrieved as a keyless extract,
so they were not built. State vehicle-finance penetration and historical dealer
counts remain the known gaps in `known_data_gaps.csv`. Nothing was simulated to
stand in for them.

## Commands

```powershell
uv run lab playground --list
uv run lab playground --suite
uv run lab playground --run D01
uv run lab autiqa-status
uv run lab macro-refresh
```

`autiqa-status` only probes. It does not copy rows into the lab database.

# Research questions

Carried over from the original repo vision and extended. The first-paper target:

> **"Structural Evolution of India's Passenger Vehicle Market: A Network Science
> Perspective Using VAHAN Registration Data (2012–2026)"**
> — venue: arXiv `physics.soc-ph` / `cs.SI` → Applied Network Science.

## Core questions

1. **Market structure** — Is India's PV market hub-and-spoke (Maruti dominates
   everywhere) or regionally clustered? *(experiment 003: low modularity says
   hub-and-spoke at OEM–state grain; regional texture lives in state-similarity space)*
2. **Temporal shifts** — How did network topology change around BS6 (Apr 2020)?
3. **COVID effect** — Did concentration rise or fall through 2020–21?
4. **EV transition** — Which states are bridges in EV adoption? Is adoption
   contagion-led (Bass q ≫ p — experiment 002 says yes) and what moves q?
5. **Segment dynamics** — Is the SUV boom uniform or concentrated in specific
   state–OEM pairs?

## Complexity-science extensions

6. **Early-warning signals** — Do variance/autocorrelation rise before regime
   shifts (diesel collapse, EV inflection)? (`complexity.dynamics`)
7. **Market complexity** — Do states with more "complex" OEM portfolios
   (method-of-reflections, `complexity.entropy`) grow faster or resist shocks better?
8. **Coupled covariates** — Income → adoption or adoption → infrastructure?
   Granger tests + panel FE on `panel_state_year`.
9. **Policy counterfactuals** — ABM scenarios: what does a subsidy window or an
   infra build-out do to the adoption S-curve shape? (`simulation.abm`)
10. **Retail vs wholesale** — Once wholesale data lands: inventory build-up as a
    leading indicator of demand misforecasts.

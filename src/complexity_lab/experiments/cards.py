"""Experiment cards: structured background for every experiment and method.

Implements the blueprint's explainability template (§7.5): every analysis the
lab exposes carries its question, method, plain-English concepts, math with a
toy example, interpretation guide, decision use-cases and limitations.
Rendered (a) as collapsible cards in the Streamlit app, (b) as the full guide
page on the published site (experiments/guide.qmd).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    category: str
    tier: str
    data_used: list[str]
    question: str                 # why this matters — business + research question
    method: str                   # what we actually compute
    how_it_works: list[str]       # 3-6 steps
    plain_english: dict[str, str] # term -> layman meaning
    math: str                     # markdown: formula + symbols + toy example
    look_for: list[str]           # what high/low/shape means
    limitations: list[str]
    decisions: list[str]          # who acts on this and how
    related: list[str] = field(default_factory=list)


CARDS: dict[str, Card] = {}


def _add(card: Card) -> None:
    CARDS[card.id] = card


_add(Card(
    id="descriptive-baseline",
    name="Descriptive Baseline — Size, Growth, Mix, Concentration",
    category="Descriptive Statistics",
    tier="Tier 0 — Foundation",
    data_used=["Vahan registrations 2012–2026 (state × month × OEM × fuel)"],
    question="What is the basic shape of India's PV market — how big, how fast-growing, "
             "how concentrated, and how seasonal — before any deeper claim is made?",
    method="Aggregations on the state panels: totals, YoY growth, CAGR, fuel shares, "
           "OEM HHI/entropy, month-of-year seasonality index, state Gini and Zipf fit.",
    how_it_works=[
        "Aggregate registrations to state×year and state×month panels.",
        "Compute growth (YoY, CAGR) per state and nationally.",
        "Compute fuel shares and OEM concentration (HHI, entropy) per state-period.",
        "Normalise each year by its own mean to isolate the seasonal profile.",
        "Fit rank–size (Zipf) and Gini across states for inequality of market size.",
    ],
    plain_english={
        "Market share": "Out of every 100 cars registered, how many belong to one OEM.",
        "HHI": "A concentration score: 10,000 = one company sells everything; "
               "below ~1,500 = competitive market.",
        "Seasonality index": "How a typical March or November compares with an average month "
                             "(1.2 = 20% above average).",
        "Gini": "0 = all states register equally; 1 = one state registers everything.",
    },
    math="**HHI** = Σ (shareᵢ × 100)². Toy: two OEMs at 50% each → 50² + 50² = 5,000. "
         "Four at 25% → 4 × 625 = 2,500 — more players, lower score.\n\n"
         "**CAGR** = (end/start)^(1/years) − 1. Toy: 1.0 L → 1.5 L in 5 years → "
         "(1.5)^0.2 − 1 ≈ 8.4%/yr.",
    look_for=[
        "HHI trending down = market fragmenting (new entrants taking share).",
        "Seasonality: festive (Oct–Nov) and fiscal year-end (March) peaks; "
        "a state deviating from the national profile has local buying rhythms.",
        "Zipf slope near −1 = market sizes follow a power law (few giant states dominate).",
    ],
    limitations=[
        "Latest year is partial — all snapshot KPIs use the last *full* year.",
        "All-India rows are pre-aggregated upstream; never recompute by summing states.",
    ],
    decisions=[
        "Analyst: baseline every report on these numbers before deeper modelling.",
        "OEM planner: seasonality index calibrates monthly targets and stock plans.",
    ],
    related=["oem-state-network", "ev-threshold"],
))

_add(Card(
    id="ev-diffusion-states",
    name="EV Diffusion — Bass Model per State",
    category="Diffusion / Simulation",
    tier="Tier 3 — Diffusion Models",
    data_used=["Vahan EV registrations (monthly, per state)", "income & infra covariates"],
    question="Is each state's EV adoption innovation-driven (ads, policy, curiosity) or "
             "imitation-driven (seeing neighbours drive EVs)? Where is each state on its S-curve?",
    method="Nonlinear least-squares fit of the Bass (1969) cumulative adoption curve per state; "
           "parameters compared against income and charger covariates.",
    how_it_works=[
        "Build cumulative EV registrations per state (monthly).",
        "Fit p (innovation), q (imitation), m (market potential) by curve fitting.",
        "Compute implied peak-adoption time t* = ln(q/p)/(p+q).",
        "Correlate fitted q with per-capita income / charging infrastructure.",
    ],
    plain_english={
        "Innovation coefficient p": "Adoption that happens without social proof — early "
                                    "believers, policy push, novelty.",
        "Imitation coefficient q": "Adoption because others adopted — word of mouth, "
                                   "visible charging stations, neighbour effects.",
        "S-curve": "Slow start → rapid middle → saturation plateau; most technology "
                   "adoption follows this shape.",
    },
    math="Bass: f(t)/[1−F(t)] = p + q·F(t). Cumulative form fitted: "
         "F(t) = m·(1−e^{−(p+q)t}) / (1 + (q/p)·e^{−(p+q)t}).\n\n"
         "Toy: p=0.003, q=0.3 → t* = ln(100)/0.303 ≈ 15 periods to peak adoption rate. "
         "q/p = 100 means imitation dominates 100:1 — adoption is social.",
    look_for=[
        "High q, low p = contagion-driven state: invest in visibility, not subsidies.",
        "Flat curve, fit fails = pre-takeoff state (SHEV shows this everywhere).",
        "States past t* = self-sustaining; before t* = still needs support.",
    ],
    limitations=[
        "m (market potential) is weakly identified early in adoption — wide error bars.",
        "Policy shocks (FAME II) violate the constant-p,q assumption; treat fits as descriptive.",
    ],
    decisions=[
        "Policy: states with low p AND low q need direct intervention, not spillover hopes.",
        "OEM: time EV model launches to states approaching their S-curve inflection.",
    ],
    related=["ev-threshold", "phase-transitions"],
))

_add(Card(
    id="oem-state-network",
    name="OEM–State Bipartite Network — Centrality, Communities, Evolution",
    category="Network Science",
    tier="Tier 1–2 — Network Construction & Communities",
    data_used=["Vahan registrations aggregated to OEM × state × year edges"],
    question="Is India one national car market or several regional ones? Which OEMs bridge "
             "regions, and how did shocks (BS6, COVID, EV era) rewire the structure?",
    method="Weighted bipartite graph (edge = OEM's share in a state); Louvain communities, "
           "centrality tables, and year-by-year modularity/density tracking.",
    how_it_works=[
        "Build one bipartite graph per year: OEM nodes ↔ state nodes, edge weight = share.",
        "Compute degree/strength/betweenness/eigenvector centrality per node.",
        "Detect communities (Louvain) and measure modularity each year.",
        "Project onto states (states linked by similar OEM mix) for the similarity network.",
    ],
    plain_english={
        "Centrality": "How structurally important a node is — a high-betweenness OEM "
                      "connects regions that otherwise behave separately.",
        "Modularity": "How cleanly the network splits into clusters (0 = one blob, "
                      ">0.3 = strong regional camps).",
        "Bipartite": "Two kinds of nodes (OEMs, states); edges only between kinds.",
    },
    math="Modularity Q = (1/2m) Σᵢⱼ [Aᵢⱼ − kᵢkⱼ/2m] δ(cᵢ,cⱼ). "
         "Plain reading: how much more weight falls inside communities than a random "
         "network with the same degrees would put there.\n\n"
         "Toy: 4 nodes, all edges inside 2 pairs → Q ≈ 0.5 (strong split).",
    look_for=[
        "Rising modularity = regionalisation; falling = national homogenisation.",
        "OEMs with high betweenness but mid market share = strategic bridges.",
        "Community membership changes year-over-year = competitive battlegrounds.",
    ],
    limitations=[
        "Louvain is stochastic — we fix the seed; check stability before publishing.",
        "Edge threshold choice shifts communities; see the percolation experiment for "
        "a principled threshold.",
    ],
    decisions=[
        "OEM strategist: identify which regional cluster you under-serve.",
        "Researcher: modularity time series is the paper-ready structural-evolution metric.",
    ],
    related=["phase-transitions", "descriptive-baseline"],
))

_add(Card(
    id="wholesale-retail-nowcast",
    name="Wholesale vs Retail — Channel Structure & Nowcasting",
    category="Forecasting / Supply Chain",
    tier="Tier 1 — Foundational (channel) + Tier 3 (nowcast)",
    data_used=["Wholesale dispatches (local, full coverage 2022-04+)", "Vahan registrations"],
    question="Dealers buy before customers register. Can dispatches tell us this month's "
             "retail number ~45 days before VAHAN settles, and is the channel over- or under-stocked?",
    method="Join national wholesale and retail by month; cross-correlation on growth; "
           "OLS nowcast (retail ~ wholesale + seasonal memory) with rolling out-of-sample backtest.",
    how_it_works=[
        "Compute the wholesale/retail ratio monthly — sustained >1 = stock build.",
        "Cross-correlate monthly growth at lags −6..+6 to find lead/lag.",
        "Fit retail_t ~ wholesale_t + retail_{t−12} on history before each test month.",
        "Score the nowcast vs a seasonal-naive baseline on the last 12 months (MAPE).",
    ],
    plain_english={
        "Nowcast": "An estimate of the present (this month's retail) from data that arrives "
                   "earlier (dispatches), not a prediction of the future.",
        "Channel inventory": "Cars shipped to dealers but not yet registered — the pipeline.",
        "MAPE": "Average % miss. 5% MAPE = forecasts typically off by 5%.",
    },
    math="Nowcast: R̂_t = α + β·W_t + γ·R_{t−12}. Baseline: R̂_t = R_{t−12} × trailing YoY drift.\n\n"
         "Toy: if W_t = 3.6 L units, β ≈ 0.7, R_{t−12} = 3.2 L, γ ≈ 0.3, α ≈ 0.2 L → "
         "R̂ ≈ 0.2 + 2.52 + 0.96 ≈ 3.68 L.",
    look_for=[
        "Ratio > 1.2 for 3+ months = dealer stress (discounts likely follow).",
        "Nowcast beating baseline = wholesale carries genuine same-month information.",
        "Correlation strongest at lag 0 (not +1/+2) = channel passes demand through fast.",
    ],
    limitations=[
        "Wholesale full coverage only from 2022-04 — never compare across the break.",
        "~6% of wholesale volume has unmapped cities (excluded from state views).",
        "Proprietary data: results reproduce only on machines with the source file.",
    ],
    decisions=[
        "Analyst: publish month estimates ~45 days before official data settles.",
        "Dealer/OEM: ratio bands trigger inventory correction conversations.",
    ],
    related=["descriptive-baseline"],
))

_add(Card(
    id="phase-transitions",
    name="Phase Transitions — Percolation & Fuel Regime Dynamics",
    category="Complexity Science",
    tier="Tier 5 — Research Grade",
    data_used=["Vahan OEM×state edges", "fuel shares per state-year"],
    question="Does the market change *gradually* or does it *snap*? Two tests: at what presence "
             "threshold does the OEM–state network disintegrate (percolation), and do states jump "
             "between discrete fuel regimes rather than drifting (Markov regime analysis)?",
    method="(1) Sweep the minimum within-state share for an edge to count; track the giant "
           "connected component — its collapse point is the percolation transition. "
           "(2) Classify each state-year into fuel regimes by transparent rules; estimate the "
           "empirical Markov transition matrix and find absorbing regimes.",
    how_it_works=[
        "Compute every OEM's share within every state.",
        "For each threshold τ ∈ [0.1%, 50%]: keep edges with share ≥ τ, measure the largest "
        "connected component as a fraction of all nodes.",
        "Locate the steepest drop — the critical threshold τ_c.",
        "Separately: label each state-year fossil_dominant / cng_transitioned / ev_emerging / "
        "multi_fuel; count regime-to-regime transitions across 14 years.",
        "Read the diagonal of the transition matrix: ≥95% self-transition = absorbing regime.",
    ],
    plain_english={
        "Phase transition": "A sharp qualitative change from a small quantitative push — "
                            "water → ice, or a connected market → fragmented islands.",
        "Percolation": "Remove weak links one by one; for a long time the network holds, "
                       "then suddenly it shatters. The shattering point is structural truth.",
        "Absorbing state": "A regime you enter but never leave — adoption ratchets, "
                           "it doesn't slide back.",
        "Giant component": "The largest group of OEMs+states still connected to each other.",
    },
    math="Giant component fraction G(τ) = |largest component| / |all nodes|. "
         "τ_c = argmin dG/dτ (steepest collapse).\n\n"
         "Markov: P(regime_b | regime_a) = (# a→b transitions) / (# transitions out of a). "
         "Toy: if 12 of 13 'ev_emerging' state-years stay ev_emerging → "
         "P(stay) = 0.92, nearly absorbing.",
    look_for=[
        "A sharp G(τ) cliff (not gradual decay) = the market has a characteristic "
        "'minimum viable presence' scale — OEM footholds below τ_c don't knit a national network.",
        "ev_emerging as absorbing = the EV transition is a ratchet (one-way door).",
        "fossil_dominant → ev_emerging direct jumps vs the CNG stepping-stone path.",
    ],
    limitations=[
        "Regime rules are transparent but hand-set (5% EV, 15% CNG); HMM-fitted regimes are the "
        "publishable upgrade (see roadmap).",
        "Percolation on 28×35 nodes is small-N; bootstrap before claiming criticality in print.",
    ],
    decisions=[
        "OEM entering a state: τ_c is the empirical minimum share worth fighting for.",
        "Policy: absorbing-regime evidence justifies one-time push incentives (the market "
        "won't relapse once transitioned).",
    ],
    related=["ev-threshold", "oem-state-network"],
))

_add(Card(
    id="ev-threshold",
    name="EV Tipping Points — Threshold Regression per State",
    category="Complexity Science / Econometrics",
    tier="Tier 4 — Dynamical Analysis",
    data_used=["Vahan EV share (state × month)", "income, chargers, fuel prices"],
    question="Is there a share level beyond which EV adoption feeds on itself — visibility, "
             "charging viability, resale confidence — so growth accelerates without new policy?",
    method="Piecewise (hinge) regression of Δshare on lagged share per state: "
           "Δs_t = a + b·s_{t−1} + c·max(0, s_{t−1} − τ); grid-search τ; "
           "positive significant c = self-acceleration past τ (tipping).",
    how_it_works=[
        "First report observed calendar-time momentum: did the latest annual share gain "
        "speed up or slow down versus the prior year?",
        "For each state, build the monthly EV-share series.",
        "Regress each month's share *change* on last month's share *level*, allowing the "
        "slope to change at an unknown threshold τ.",
        "Try all candidate τ values; keep the best-fitting one.",
        "If the above-threshold slope is steeper (c > 0), the state shows positive feedback.",
        "Compare fitted τ* across states against income and charger density.",
    ],
    plain_english={
        "Tipping point": "The level where a trend starts pushing itself — like a rumour "
                         "reaching enough people that everyone hears it twice.",
        "Positive feedback": "More EVs → more chargers & visibility → more EVs.",
        "Hinge term": "A variable that is zero below the threshold and grows above it — "
                      "it lets the same regression have two slopes.",
        "Saturation": "The opposite finding (negative hinge): growth slows past a level — "
                      "early-adopter pool exhausted.",
    },
    math="Δs_t = a + b·s_{t−1} + c·max(0, s_{t−1} − τ) + ε.\n\n"
         "Toy: b = 0.01, c = 0.05, τ = 4%. At s = 3%: growth slope 0.01. At s = 6%: "
         "slope = 0.06 — six times steeper. τ* is where the regime changes.\n\n"
         "Model quality: SSE gain vs the straight line (no threshold). 30%+ gain = the "
         "threshold is real structure, not noise.",
    look_for=[
        "Many states can be accelerating in calendar time even when no stable share threshold "
        "is detected; these are different empirical claims.",
        "Cluster of fitted τ* around similar share levels (e.g. 4–6%) across rich states = "
        "a market-wide critical mass level.",
        "c < 0 instead = saturation (Kerala-style early plateau) — different policy problem.",
        "States below their τ* today = exactly where one push has outsized payoff.",
    ],
    limitations=[
        "Needs enough post-threshold months; late-adopting states give unstable τ*.",
        "Results are sensitive to the analysis era; compare full history, FAME-II, 2022+, "
        "and 2023+ windows before calling a structural threshold.",
        "Tipping is inferred from time-series shape, not causally identified — "
        "the DiD/event-study experiments are the causal companion.",
    ],
    decisions=[
        "Policy: rank states by distance-to-tipping; subsidise the near-threshold ones first.",
        "OEM/charging investor: τ* map = market-entry timing map.",
    ],
    related=["phase-transitions", "ev-diffusion-states"],
))

_add(Card(
    id="hypothesis-tester",
    name="Hypothesis Tester — Correlation, Panel Regression, Changepoints",
    category="Econometrics",
    tier="Tier 2 — Statistical Analysis",
    data_used=["state×year panel with all covariates", "wholesale state series (local)"],
    question="Pick any two-or-more variables and ask: do they move together, does one "
             "predict the other with controls, and when did the relationship break?",
    method="Spearman correlation matrix; fixed-effects panel OLS with entity-clustered "
           "errors; PELT/Binseg changepoint detection; all over a user-chosen period.",
    how_it_works=[
        "Choose variables and a year range (sliders).",
        "Correlation: rank-based (robust to outliers and scale).",
        "Regression: state fixed effects absorb everything constant about a state; "
        "coefficients describe within-state variation.",
        "Changepoints: penalised search for points where the series' statistics shift.",
    ],
    plain_english={
        "Spearman correlation": "Do ranks move together? Immune to a few extreme states.",
        "Fixed effects": "Compare each state with itself over time, not Bihar with Goa.",
        "Clustered errors": "Months within a state aren't independent; errors account for it.",
        "Changepoint": "The date where the data's behaviour statistically changed.",
    },
    math="FE model: y_it = α_i + βx_it + ε_it. β answers: when x rises within a state, "
         "what happens to y in that same state?\n\n"
         "Toy: ev_share on log(income), β = 0.02 → a 10% income rise within a state "
         "associates with +0.2 pp EV share.",
    look_for=[
        "Correlation ≠ regression: if correlation is high but FE β ≈ 0, the cross-state "
        "pattern is compositional (rich states differ in many ways), not within-state.",
        "Changepoints aligning with policy events (BS6, COVID, FAME) validate the method.",
    ],
    limitations=[
        "No instrument = no causality; treat β as conditional association.",
        "Income data is FY, registrations calendar-year; the join is approximate by design.",
    ],
    decisions=[
        "Researcher: this is the screening tool — graduate surviving hypotheses to "
        "experiments with proper identification.",
    ],
    related=["ev-threshold", "descriptive-baseline"],
))

_add(Card(
    id="forecast",
    name="Forecasting — Seasonal Baselines with Honest Backtests",
    category="Forecasting",
    tier="Tier 3 — Intermediate",
    data_used=["any monthly series from the panels (national or state)"],
    question="What will registrations be next 3–12 months — and which model actually "
             "earns its complexity on this series?",
    method="Three models (seasonal-naive-with-drift, Holt-Winters, SARIMA) ranked by "
           "rolling-origin out-of-sample MAPE; fan chart for the winner.",
    how_it_works=[
        "Hold out the last months repeatedly (rolling origins).",
        "Fit each model only on data before each origin; predict; score.",
        "Rank models by average MAPE — the winner is empirical, not assumed.",
        "Refit the winner on the full series for the forward fan chart.",
    ],
    plain_english={
        "Seasonal naive": "Next March ≈ last March (× recent drift). Embarrassingly hard to beat.",
        "Fan chart": "The widening band = growing uncertainty with horizon.",
        "Rolling origin": "Backtest like reality: never let the model see the future.",
    },
    math="MAPE = mean(|forecast − actual| / actual). sNaive: ŷ_{t+h} = y_{t+h−12} × drift, "
         "drift = mean(y_t / y_{t−12}) over last 3 months.",
    look_for=[
        "If sNaive wins, the series is season+drift; complexity isn't earning its keep.",
        "Coverage: ~95% of actuals should fall inside the band; narrower = overconfident.",
    ],
    limitations=[
        "Structural breaks (COVID, BS6) poison training windows — check residuals around them.",
        "State-level low-volume series are noisy; national forecasts are far more stable.",
    ],
    decisions=[
        "Planner: use the winning model's band, not its point, for inventory decisions.",
    ],
    related=["wholesale-retail-nowcast"],
))


_add(Card(
    id="shock-lab",
    name="Shock Lab — Demand & Supply Shocks in the Channel",
    category="Simulation — System Dynamics",
    tier="Tier 3 — Simulation",
    data_used=["Synthetic channel calibrated to Indian PV magnitudes",
               "Optionally compared against retail_wholesale_month signatures"],
    question="When demand collapses (COVID) or supply is cut (chip shortage), how do retail, "
             "dealer inventory and dispatches respond — and where do sales actually get lost?",
    method="Monthly stock-and-flow simulation: latent demand → retail capped by availability; "
           "production targets a stock cover with an adjustment lag; inventory buffers the two. "
           "Shocks are multiplicative windows on demand or production.",
    how_it_works=[
        "Latent demand follows trend × seasonality × shock multiplier.",
        "Retail equals demand unless dealer stock + this month's production can't cover it.",
        "OEMs forecast demand from a trailing mean and produce forecast + inventory correction.",
        "The correction is spread over an adjustment lag — the source of overshoot.",
        "Inventory absorbs every mismatch; lost sales occur only when it hits zero.",
    ],
    plain_english={
        "Stock cover": "Dealer inventory expressed in months of current demand (1.1 = ~5 weeks).",
        "Bullwhip": "Production swings harder than retail because OEMs chase inventory targets — "
                    "the supply chain amplifies demand noise.",
        "Lost sales": "Buyers who walked in but no car was available — demand that never converts.",
        "Pull-forward": "A pre-announced change (BS6, tax) shifts purchases earlier, then payback.",
    },
    math="**I_t = I_{t-1} + P_t − R_t** (inventory identity).\n\n"
         "**P_t = clip(D̂ + (cover·D̂ − I_{t-1})/lag, 0, capacity)** — produce the forecast plus a "
         "fraction of the inventory gap.\n\nToy: demand 100/mo, target cover 1.1, lag 3. If stock "
         "falls to 80, production = 100 + (110−80)/3 = 110 — a 10% overshoot that decays as stock refills.",
    look_for=[
        "Pure demand collapse: inventory & ws/retail spike, zero lost sales — channel stress, not scarcity.",
        "Pure supply cut: retail holds for ~stock-cover months, then lost sales begin — the buffer's value.",
        "After any shock: production overshoots baseline during restock (bullwhip > 1).",
        "Longer adjustment lag = slower but smoother response; shorter = nervier channel.",
    ],
    limitations=[
        "One aggregated OEM and one inventory pool — no competition or substitution between brands.",
        "No price response: real markets discount their way out of inventory gluts.",
        "Parameters are illustrative; calibrate cover/lag against the Wholesale page before quoting numbers.",
    ],
    decisions=[
        "OEM S&OP: size the stock-cover target against shock scenarios, not average months.",
        "Dealer: read ws/retail > 1.2 as push-inventory risk; negotiate billing accordingly.",
        "Analyst: distinguish demand-side from supply-side months in the real wedge series.",
    ],
    related=["wholesale-retail-nowcast", "phase-transitions"],
))


_add(Card(
    id="ev-contagion",
    name="EV Adoption as Contagion on the State Network",
    category="Network Science — Diffusion",
    tier="Tier 3 — Diffusion & Contagion",
    data_used=["Vahan EV shares (state × year)", "State adjacency (shared land borders)",
               "State similarity (income/urbanization)"],
    question="Does EV adoption spread between neighbouring states like a contagion — and which "
             "states are the critical seeds or holdouts of the national cascade?",
    method="Threshold-contagion simulation on the state adjacency graph, seeded by actual early "
           "adopters; compared against the observed adoption order (year each state crossed an "
           "EV-share threshold). Moran's I tests spatial autocorrelation of adoption.",
    how_it_works=[
        "Build the state graph: nodes = states, edges = shared borders.",
        "Mark when each state actually crossed the EV-share threshold (the observed cascade).",
        "Moran's I: do high-EV states cluster geographically more than chance?",
        "Simulate threshold contagion: a state adopts when ≥ τ of its neighbours have adopted; "
        "sweep τ to find where the simulated cascade matches the observed order.",
        "Rank states by cascade influence: how much earlier does the system tip if seeded there?",
    ],
    plain_english={
        "Contagion": "Adoption spreading through exposure — seeing EVs next door normalises them.",
        "Threshold τ": "How much neighbourhood pressure a state needs before it flips.",
        "Moran's I": "A score for geographic clustering: positive = neighbours resemble each other.",
        "Seed state": "Where the cascade starts; good seeds are connected AND influential.",
    },
    math="**Moran's I** = (n/W) · Σᵢⱼ wᵢⱼ(xᵢ−x̄)(xⱼ−x̄) / Σᵢ(xᵢ−x̄)². Ranges ≈ −1…+1; "
         "0 = random geography. Toy: if all high-EV states border each other, numerator terms are "
         "positive products → I > 0.\n\n**Threshold rule**: state i adopts at t+1 if "
         "(adopted neighbours / total neighbours) ≥ τ.",
    look_for=[
        "Moran's I significantly > 0 = adoption is spatially clustered (contagion-consistent).",
        "Low best-fit τ (~0.2) = adoption spreads easily; high τ = states move independently.",
        "States the simulation flips late but reality flipped early = policy-driven jumps (Delhi).",
        "States simulation flips early but reality hasn't = the next adopters to watch.",
    ],
    limitations=[
        "Spatial correlation ≠ causal contagion — common income/policy shocks also cluster.",
        "Adjacency is one channel; media and national OEM launches are non-spatial.",
        "Small n (≈33 states) — treat p-values as indicative, not decisive.",
    ],
    decisions=[
        "Policy: seed charging-infra subsidies in high-influence states for cascade leverage.",
        "OEM: stage EV dealer rollouts along the predicted adoption frontier.",
        "Researcher: the τ-sweep + Moran's I combo is the publishable core (NetSci/Physica A).",
    ],
    related=["ev-diffusion-states", "ev-threshold", "phase-transitions"],
))


_add(Card(
    id="fuel-regimes",
    name="Hidden-Markov Fuel Regimes",
    category="Dynamical Systems — Regime Detection",
    tier="Tier 4 — Temporal Analysis",
    data_used=["Vahan fuel shares (state × year, 5-dim vector)", "Policy events for alignment"],
    question="Which states have genuinely switched energy regime (fossil → CNG/EV-mixed), "
             "which are mid-transition, and which remain fossil-locked — judged by the data, "
             "not by an analyst-chosen threshold?",
    method="A Gaussian hidden Markov model fitted by EM over all states' yearly fuel-mix "
           "vectors. BIC selects the number of latent regimes; Viterbi decoding yields each "
           "state's regime calendar; the fitted matrix gives regime persistence.",
    how_it_works=[
        "Represent each state-year as [petrol, diesel, CNG, EV, hybrid] shares.",
        "Fit one HMM across all states — regimes are market-wide definitions, not per-state.",
        "Pick K (number of regimes) by BIC over K = 2…4.",
        "Viterbi-decode each state's most likely regime path — the regime calendar.",
        "Read the transition matrix: diagonal ≈ persistence; near-zero reverse flows = ratchet.",
    ],
    plain_english={
        "Hidden Markov model": "The fuel mix we see each year is a noisy reflection of an "
                               "underlying 'era' we can't see directly; the HMM infers the eras.",
        "Regime": "A characteristic fuel mixture (e.g. diesel-heavy era vs EV-emerging era).",
        "Viterbi path": "The single most plausible sequence of eras for a state.",
        "Persistence": "Probability a state stays in its current era next year.",
    },
    math="Emission: x_t | regime k ~ N(μ_k, σ²_k) per fuel dimension. Transition: "
         "P(regime_{t+1}=j | regime_t=i) = A_ij.\n\nToy: two regimes with μ_diesel = 0.30 vs "
         "0.10 — a state at diesel share 0.28 is almost surely in regime 1; at 0.18 the HMM "
         "weighs both and lets *neighbouring years* break the tie (that's the Markov part).",
    look_for=[
        "Diagonal of the transition matrix near 1 = sticky eras (structural, not noise).",
        "Zero probability of returning to the fossil regime = the transition is a ratchet.",
        "Cluster of regime-switch years around 2020–2022 = BS6/COVID/EV-policy era break.",
        "States still in the fossil regime in the latest year = the genuine laggards.",
    ],
    limitations=[
        "Yearly grain: ~14 observations per state — K above 4 would overfit (BIC guards this).",
        "Gaussian emissions on shares are an approximation (shares are bounded).",
        "Regime labels are derived from mean vectors — verify them against the means table.",
    ],
    decisions=[
        "OEM: time EV dealer/service investment by a state's regime, not raw EV share.",
        "Policy: states with low transition probability need push (incentives), not patience.",
        "Researcher: the regime calendar + Cox survival on covariates is the publishable unit.",
    ],
    related=["phase-transitions", "ev-threshold", "ev-contagion"],
))


_add(Card(
    id="adoption-network-horserace",
    name="Adoption-Network Inference — the Horse Race",
    category="Network Science — Inference",
    tier="Tier 5 — Research Grade",
    data_used=["Vahan EV shares (state × year)", "State adjacency", "Income/urbanization/infra covariates"],
    question="What actually connects states in the EV transition — geography, economics, or "
             "something else? We let three candidate networks compete at predicting each "
             "state's adoption year from its neighbours.",
    method="Build three networks (land borders; kNN cosine similarity on covariates; "
           "co-adoption = correlated EV-share changes filtered against a circular-shift "
           "permutation null). Leave-one-out: predict each state's threshold-crossing year "
           "as the weighted mean of its neighbours'; score MAE and rank correlation.",
    how_it_works=[
        "Mark each state's EV adoption year (first year above the share threshold).",
        "Candidate 1 — geography: states sharing a border are neighbours.",
        "Candidate 2 — economics: states with similar income/urbanization/infra are neighbours.",
        "Candidate 3 — co-adoption: states whose EV-share *changes* co-move beyond what "
        "autocorrelation noise explains (circular-shift permutation test).",
        "Hide each state, predict its year from neighbours, score each network honestly.",
    ],
    plain_english={
        "Latent network": "The invisible web of influence we try to reconstruct from outcomes.",
        "Circular-shift null": "Rotate one series in time and re-correlate — preserves each "
                               "series' rhythm but destroys true synchrony; real links must beat this.",
        "Leave-one-out": "Cover a state's answer and ask its neighbours to guess it.",
        "MAE (years)": "Average miss of predicted adoption year — smaller is better.",
    },
    math="Edge test: p = P(|corr(Δa, shift(Δb))| ≥ |corr(Δa, Δb)|) under random shifts; keep "
         "edge if p ≤ α and corr > 0.\n\nPrediction: ŷ_i = Σ_j w_ij y_j / Σ_j w_ij over "
         "neighbours j.\n\nToy: state X borders A (2019) and B (2021) → geographic prediction "
         "2020; if X actually adopted 2024, geography misses by 4 years for X.",
    look_for=[
        "Which network wins on MAE — that's the best single model of the influence structure.",
        "Co-adoption beating geography = adoption synchrony is NOT mainly spatial spillover "
        "(think national policy waves, OEM launch timing, income dynamics).",
        "States where every network misses badly = idiosyncratic movers (policy jumps).",
        "The co-adoption network's communities = states that move together — the real 'regions'.",
    ],
    limitations=[
        "~14 yearly observations per state — the co-adoption test has limited power (α matters).",
        "Co-adoption can't separate mutual influence from common shocks; it models synchrony.",
        "The full maximum-entropy (BiCM) version with out-of-sample years is the paper upgrade.",
    ],
    decisions=[
        "Policy: seed states central in the *winning* network, not the prettiest map.",
        "Researcher: this horse-race framing + max-ent upgrade targets Physica A / EPJ Data Science.",
        "Analyst: use the winner's neighbour-mean as a sanity forecast for late adopters.",
    ],
    related=["ev-contagion", "ev-diffusion-states"],
))


_add(Card(
    id="shev-isolation",
    name="SHEV — The Structurally Isolated Technology",
    category="Policy Network Analysis",
    tier="Tier 5 — Lead Paper",
    data_used=["Vahan fuel shares (hybrid visible only from 2024 — classification break)",
               "Policy events database", "UP hybrid tax waiver (Jul 2024) as natural experiment"],
    question="Strong hybrids are the most fuel-efficient non-plug-in technology on sale, yet "
             "stay near 2% share. Is that consumer preference — or structural isolation from "
             "India's incentive architecture (no FAME, 43% effective GST, no policy node)?",
    method="Two pieces: (1) post-2024 Vahan adoption trajectories SHEV vs EV vs CNG with the "
           "incentive map (which policies touch which technology); "
           "(2) difference-in-differences on UP's July-2024 registration-tax waiver — the one "
           "place a SHEV incentive node briefly existed.",
    how_it_works=[
        "Count policy events touching each technology (keyword-classified) — the incentive graph.",
        "Plot share trajectories on the same axis; note the Vahan 2024 classification break.",
        "DiD: UP's hybrid share change after Jul-2024 minus the same change in control states.",
        "Placebo check: re-run the DiD pretending each control state was treated.",
    ],
    plain_english={
        "Structural isolation": "Not present in the incentive network at all — no subsidy, no "
                                "tax break, no mandate references the technology.",
        "Natural experiment": "A policy change that creates treated and untreated groups for us.",
        "DiD (difference-in-differences)": "Compare the change in UP with the change elsewhere — "
                                            "differencing away seasonality and national trends.",
        "ATT": "Average treatment effect on the treated — the share lift attributable to the waiver.",
    },
    math="**ATT** = (UPᵖᵒˢᵗ − UPᵖʳᵉ) − (controlsᵖᵒˢᵗ − controlsᵖʳᵉ).\n\nToy: UP hybrid share "
         "rises 1.0% → 3.4% (+2.4pp) while controls rise 1.0% → 1.2% (+0.2pp) → ATT ≈ +2.2pp.\n\n"
         "Placebo rank p = share of control states whose pseudo-ATT is at least as extreme — "
         "with 8 controls the smallest achievable p is 1/9 ≈ 0.11.",
    look_for=[
        "Policy mentions: EV far exceeds CNG and Hybrid; the UP waiver is the lone hybrid node.",
        "SHEV trajectory flat vs EV's S-curve despite similar product availability windows.",
        "Positive UP ATT that beats all placebos = price/tax, not preference, binds adoption.",
        "The pre-2024 Vahan zero is a classification artifact, so no continuous pre/post curve is claimed.",
    ],
    limitations=[
        "Vahan hybrid data exists only from 2024 — earlier 'zero' is a classification break, "
        "never evidence of zero sales.",
        "One treated state, short post-window; festive timing partially overlaps the waiver.",
        "Wholesale is excluded because the source has no fuel-wise quantity cut.",
    ],
    decisions=[
        "Policy: the quantified counterfactual for GST-rationalisation debates on SHEVs.",
        "OEM (Toyota/Honda/Maruti): which states' tax structures make SHEV pushes viable.",
        "Researcher: this is the lead-paper skeleton — add Bass counterfactual simulation "
        "(GST 43% → 5%) for the full draft.",
    ],
    related=["ev-threshold", "fuel-regimes", "wholesale-retail-nowcast"],
))


_add(Card(
    id="regime-survival",
    name="Regime-Switch Survival — What Accelerates the Transition?",
    category="Survival Analysis — Discrete-Time Hazard",
    tier="Tier 4 — Temporal Analysis",
    data_used=["HMM regime calendar (experiment 008)", "Income & urbanization covariates"],
    question="Which states switch energy regime sooner, and is the timing explained by state "
             "resources (income, urbanization) — or by a common national wave?",
    method="Build a risk set (one row per state-year until first regime switch) from the HMM "
           "calendar; fit a discrete-time logit hazard with standardized covariates plus a "
           "calendar-time trend; read odds ratios per standard deviation.",
    how_it_works=[
        "From the regime calendar, track each state until its first switch (then censor).",
        "Each state-year is a Bernoulli trial: switch or not, given covariates that year.",
        "Logit on the switch indicator = discrete-time survival model (handles ties cleanly).",
        "Kaplan–Meier curve shows the unconditional share of states still un-switched by year.",
        "Compare covariate odds ratios against the calendar-time trend.",
    ],
    plain_english={
        "Risk set": "Only states that haven't switched yet can switch this year — the model "
                    "compares switchers with those still at risk, year by year.",
        "Hazard": "The probability of switching this year given you haven't yet.",
        "Odds ratio per SD": "How much one standard deviation of a covariate multiplies the "
                             "odds of switching (>1 accelerates, <1 delays).",
        "Censoring": "States that never switch still inform the model — they survived.",
    },
    math="P(switch_it = 1 | at risk) = logistic(α + β·zᵢₜ + γ·t). OR = e^β.\n\nToy: β = 0.5 for "
         "income → OR ≈ 1.65: a state 1 SD richer has 65% higher odds of switching this year.",
    look_for=[
        "Significant covariate ORs = resource-driven transition (rich/urban states first).",
        "Only the time trend significant = a national wave hits states almost regardless of "
        "local conditions — consistent with the network horse race (exp 009).",
        "KM curve cliff = the wave year; gentle slope = staggered, idiosyncratic switching.",
    ],
    limitations=[
        "Few events (~15 switches) — wide confidence intervals; treat ORs as directional.",
        "Covariates partly trend with time; the time term absorbs shared growth.",
        "First-switch only; repeat transitions (rare here) are ignored.",
    ],
    decisions=[
        "Policy: if the wave dominates, national instruments beat state-targeted nudges.",
        "OEM: switch-timing forecasts should track policy calendars, not state demographics.",
        "Researcher: with more events (district grain), upgrade to Cox PH with shared frailty.",
    ],
    related=["fuel-regimes", "adoption-network-horserace"],
))


_add(Card(
    id="suv-transition",
    name="The Hatchback→SUV Shift as a Complex Transition",
    category="Segment Dynamics — Complexity Science",
    tier="Tier 3 — Structural Analysis",
    data_used=["Wholesale segment5 taxonomy (native — no mapping needed)",
               "Panel cities: ~40 cities reported continuously since 2017",
               "State grain in the full-coverage era (2022-04+)"],
    question="India flipped from hatchback-dominant to SUV-dominant in under a decade. Was it "
             "a smooth drift or a tipping process — and is there a share level beyond which "
             "the shift self-accelerates?",
    method="SUV share series per city (9-year panel) and per state (full era); hinge "
           "(threshold) regression finds τ* where share growth changes regime; k-means on "
           "segment-share vectors yields state archetypes; OEMs classified by the year their "
           "own portfolio crossed 50% SUV.",
    how_it_works=[
        "Compute monthly SUV share of dispatches per entity (city/state).",
        "Fit Δshare ~ share + hinge(share − τ): positive hinge = self-acceleration past τ*.",
        "Use the ~40 always-reported cities for a coverage-break-proof 2017–2026 window.",
        "Cluster states on full segment vectors → Entry / Transitioning / Aspiration / Premium.",
        "Classify OEMs by when their own SUV share crossed 50% (early/follower/locked).",
    ],
    plain_english={
        "Tipping point τ*": "The SUV share past which adoption feeds on itself (visibility, "
                            "resale confidence, dealer push).",
        "Panel cities": "The same ~40 cities tracked the whole time — immune to the 2022 "
                        "coverage break that contaminates naive long series.",
        "Archetype": "A cluster of states with a similar segment mix — a market 'personality'.",
        "Segment-locked": "An OEM whose portfolio stayed hatchback/sedan-heavy through the shift.",
    },
    math="Hinge model: Δs_t = a + b·s_{t-1} + c·max(0, s_{t-1} − τ). c > 0 ⇒ growth speeds up "
         "past τ. τ* picked by SSE; sse_gain = fit improvement over the linear model.\n\nToy: "
         "below 30% SUV share a city gains 0.2pp/month; past 30% it gains 0.5pp/month → c ≈ 0.3pp.",
    look_for=[
        "Median city τ* ≈ 0.30 — the blueprint's hypothesised 30% threshold, now measured.",
        "Cities/states above their τ* = past the point of no return for hatchback share.",
        "Early movers (Tata, Kia, Hyundai) vs segment-locked (Maruti, Honda, Renault) — the "
        "fitness-landscape story of who navigated the transition.",
        "Archetype map: where Entry markets remain = the last hatchback strongholds.",
    ],
    limitations=[
        "State grain has only the 2022+ window (~48 months) — city panel is the long lens.",
        "Wholesale segments measure what OEMs *ship*, demand is inferred.",
        "k-means archetypes depend on k; treat names as descriptive, not ontological.",
    ],
    decisions=[
        "OEM: prioritise compact-SUV launches in 'Transitioning' archetype states near τ*.",
        "Dealer: hatchback-heavy portfolios in past-τ* cities face structural decline.",
        "Researcher: τ* heterogeneity vs income/roads is the SEG-K01 paper core.",
    ],
    related=["ev-threshold", "phase-transitions", "wholesale-retail-nowcast"],
))


_add(Card(
    id="shev-counterfactual",
    name="SHEV Counterfactual — Adoption at EV-Equivalent Taxation",
    category="Simulation — Policy Scenario",
    tier="Tier 5 — Lead Paper (companion)",
    data_used=["Vahan Strong Hybrid registrations from 2024-01 onward",
               "Bass fit from the diffusion module", "GST schedule (documented assumption)"],
    question="If strong hybrids were taxed like EVs (5% instead of ~43%), what does the fitted "
             "diffusion model imply adoption would have looked like?",
    method="Fit Bass (p, q, m) to cumulative post-break Vahan hybrid registrations; re-project with the "
           "market potential m scaled by a price-elasticity band (e ∈ {−1, −1.5, −2} on a "
           "−26.6% price change) and a 1.2× imitation uplift for parity visibility. "
           "Explicitly a scenario, not a forecast.",
    how_it_works=[
        "Fit the Bass curve to the observed post-2024 Vahan hybrid trajectory.",
        "Note the fitted q ≈ 0.11: weak imitation, consistent with an un-incentivised niche.",
        "Tax parity (43%→5%) ≈ −26.6% consumer price; scale m by (1 + 0.266·|e|).",
        "Project 60 months under each elasticity; compare with the no-change projection.",
        "Report the uplift band, with every assumption stated next to the number.",
    ],
    plain_english={
        "Market potential m": "How many buyers the technology can eventually reach — taxes "
                              "shrink it by pricing people out.",
        "Elasticity e": "How strongly demand responds to price: e = −1.5 means a 10% price cut "
                        "grows demand ~15%.",
        "Counterfactual": "A disciplined what-if: same model, one assumption changed.",
        "Scenario band": "We show a range because the elasticity is assumed, not estimated.",
    },
    math="m' = m·(1 + 0.266·|e|), q' = 1.2·q. Cumulative Bass: F(t) = m'(1−e^{−(p+q')t})/"
         "(1+(q'/p)e^{−(p+q')t}).\n\nToy: m = 260k, e = −1.5 → m' ≈ 364k; with q uplift the "
         "5-year cumulative rises ~1.5×.",
    look_for=[
        "The gap between baseline and scenario curves = the policy-attributable shortfall.",
        "Even e = −1 (conservative) implies ~⅓ more hybrids on the road in 5 years.",
        "Pair with experiment 010's UP DiD: the observed +2.3pp waiver lift is the empirical "
        "anchor that the elasticity band is not fantasy.",
    ],
    limitations=[
        "m-scaling via elasticity is an assumption — the honest core of any counterfactual.",
        "Supply response (OEM model launches under better tax) not modelled — likely makes "
        "these numbers conservative.",
        "The short post-2024 series follows a classification break; wholesale is excluded because "
        "it has no fuel-wise quantity cut.",
    ],
    decisions=[
        "Policy: the quantified cost of the GST wedge in units foregone.",
        "OEM (Toyota/Maruti/Honda): the size of the prize from GST rationalisation advocacy.",
        "Researcher: completes the SHEV paper triad — isolation (010) + causal anchor (UP DiD) "
        "+ counterfactual magnitude (this).",
    ],
    related=["shev-isolation", "ev-diffusion-states"],
))


def get_card(card_id: str) -> Card:
    return CARDS[card_id]


def all_cards() -> list[Card]:
    return list(CARDS.values())

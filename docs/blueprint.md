# India 4-Wheeler Passenger Vehicle Analytics — Research & Engineering Blueprint

> **Purpose**: A comprehensive reference for building a research-grade analytics system for India's 4-Wheeler Passenger Vehicle (4W PV) segment, combining Vahan retail data (2012–2026), wholesale dispatch data (2017–2026), and public supplementary datasets. Covers KPI design, statistical analysis, complexity/network science experiments, forecasting, data enrichment, and app architecture.

---

## 1. Data Assets & Schema

### 1.1 Vahan Retail Data (2012–2026)

State-level monthly retail registrations with the following granularity:

| Dimension | Values |
|---|---|
| Geography | ~35 States / UTs |
| OEM | ~25–30 manufacturers |
| Fuel type | Petrol, Diesel, CNG, EV, Hybrid, LPG, Others |
| Time | Monthly, April 2012 – March/April 2026 |
| Segment filter | 4W PV (filter from total Vahan universe) |

**Limitations**: No model-level breakup; fuel mapping can vary by RTO interpretation; pre-2018 data for some states may be sparse.

### 1.2 Wholesale Dispatch Data (2017–2026)

OEM-to-dealer channel dispatches with richer product detail:

| Dimension | Values |
|---|---|
| Geography | State-level (full coverage April 2022+; ~50-city sample pre-2022) |
| Model | SKU/model level — most granular asset |
| Segment | 4W PV, 4W UV, 2W, 3W, etc. |
| Time | Monthly, April 2017 onwards |
| Fuel breakup | **Not available** — must be inferred by model-to-fuel mapping |

**Key derived variables**:
- `ws_retail_ratio` = wholesale / retail — inventory health indicator
- `channel_fill_months` = rolling inventory estimate
- Fuel-type proxy: map model names to fuel type from public sources (SIAM, OEM catalogues)

### 1.3 Joinable Public Data Sources

| Dataset | Source | Granularity | Use |
|---|---|---|---|
| GDP / GSDP per state | MoSPI, RBI Handbook of Statistics | Annual, state | Income elasticity |
| Per-capita income | MoSPI | Annual, state | Demand driver |
| Urbanisation % | Census 2011 + UIDAI/NSS projections | Decadal + annual estimate | Adoption velocity |
| EV charging infra | BEE / Vahan EV dashboard | Monthly, state | EV correlation |
| Fuel retail prices (petrol/diesel/CNG) | PPAC, IOC | Monthly, city → state | Demand switching |
| FAME II subsidy disbursement | DHI | Monthly, OEM/model | Policy shock variable |
| PLI automotive disbursement | DPIIT | Annual, OEM | Supply-side shock |
| Consumer Sentiment Index | RBI Consumer Survey | Quarterly, 6 cities | Macro softness indicator |
| Interest rates (auto loan) | RBI / SBI lending rate | Monthly | Affordability |
| CPI / WPI inflation | MoSPI | Monthly | Real price deflator |
| NHAI highway projects | NHAI open data | Annual, state | Infrastructure proxy |
| SIAM monthly sales releases | SIAM.in (public PDF) | Monthly, OEM aggregate | Cross-validation |
| JD Power IQS India | Press releases | Annual, model | Quality signal |

---

## 2. Descriptive KPIs

### 2.1 Market Share (MS)

**OEM-level MS** (monthly, state, national):

\[ MS_{oem,t} = \frac{Registrations_{oem,t}}{\sum_{i} Registrations_{i,t}} \times 100 \]

- Track **rolling 3-month MS** and **rolling 12-month MS** to smooth seasonality.
- Flag when any OEM crosses ±1.5 pp threshold month-on-month — significant share shift.

**Segment MS** within 4W PV (Sedan vs. UV vs. Hatchback):
Requires model-to-bodystyle mapping from wholesale data merged back into retail state totals.

### 2.2 Fuel Penetration % (Fuel Pen%)

\[ FuelPen\%_{fuel,t} = \frac{Registrations_{fuel,t}}{Total\_4W\_PV_{t}} \times 100 \]

Key series to track: Petrol, Diesel, CNG, EV, Hybrid. Diesel decline and CNG+EV rise are the structural story of 2019–2026.

### 2.3 MS Change (Share Shift)

\[ \Delta MS_{oem,t} = MS_{oem,t} - MS_{oem,t-12} \]

Visualize as a waterfall chart: gainers on top, losers below. Annotate product launches or recalls.

### 2.4 Channel Inventory Ratio

\[ WS\_Retail\_Ratio_t = \frac{Wholesale\_Dispatches_t}{Retail\_Registrations_t} \]

- **>1.2**: Channel inventory building — potential oversupply
- **0.9–1.2**: Healthy channel
- **<0.8**: Channel depleting — demand may exceed supply or OEM pulling back

### 2.5 Seasonality-Adjusted Growth

\[ YoY\_SA_{t} = \frac{Registrations_t}{Registrations_{t-12}} - 1 \]

Use X-13-ARIMA-SEATS or STL decomposition for seasonal adjustment.

### 2.6 KPI Summary Table for App

| KPI | Data Source | Frequency | Dimensions |
|---|---|---|---|
| Total 4W PV Sales | Vahan | Monthly | National, State |
| OEM Market Share (%) | Vahan | Monthly | OEM × State |
| Fuel Penetration (%) | Vahan | Monthly | Fuel × State |
| YoY Growth (%) | Vahan | Monthly | OEM, Fuel, State |
| MS Change (pp) | Vahan | Monthly | OEM |
| WS/Retail Ratio | Both | Monthly | National, State |
| Channel Fill (months) | Wholesale | Monthly | OEM |
| Wholesale vs Retail Gap | Both | Monthly | OEM, Segment |
| CAGR (3Y, 5Y, 10Y) | Vahan | Snapshot | OEM, Fuel |
| EV Share (%) | Vahan | Monthly | State |
| Herfindahl Index (HHI) | Vahan | Monthly | National, State |

---

## 3. Visualization Design

### 3.1 Time-Series Charts

- **Stacked area chart**: Monthly total sales split by fuel type — shows structural shift from Petrol → Diesel → CNG/EV visually
- **Multi-line MS chart**: Top-6 OEMs market share over time with shaded policy event bands (BS6, FAME II, COVID, GST)
- **Waterfall / diverging bar**: Annual MS change per OEM
- **Heatmap (State × Year)**: EV penetration % — geographically sorted (South → North → East → West)

### 3.2 Channel Intelligence

- **Dual-axis chart**: Wholesale (bars) + Retail (line) on same axis — gap is visible immediately
- **WS/Retail ratio band chart**: Ratio line with color bands (green=healthy, orange=caution, red=stress)

### 3.3 Cross-Sectional / State Maps

- **Choropleth map**: MS by state for a selected OEM — use Plotly or Folium with GeoJSON
- **Bubble scatter**: State urbanisation % (x) vs EV share (y), sized by total volume

### 3.4 OEM Deep-Dive

- **Model-level Treemap**: Wholesale dispatches by model within OEM — shows portfolio mix
- **Model lifecycle chart**: Each model's monthly sales trajectory from launch to end-of-life

---

## 4. Regression & Correlation Analysis

### 4.1 Correlation Analysis

**Variables for pairwise Spearman correlation**:
- `ev_share`, `pc_income`, `urban_pct`, `ev_chargers`, `petrol_price`, `cng_price`, `fame_subsidy_amt`, `loan_rate`

**Recommended methods**:
- Spearman rank correlation (non-normal distributions)
- Partial correlation (controlling for a third variable — e.g., ev_share × ev_chargers controlling for income)
- Point-Biserial correlation for binary policy dummy × continuous sales

### 4.2 Panel Regression (Most Important)

**Setup**: State × Monthly panel (35 states × ~168 months = ~5,880 obs for 4W PV)

**Models to run**:

1. **Pooled OLS** (baseline, ignores state FE)
2. **Fixed Effects (FE / within estimator)**: controls for time-invariant state characteristics
3. **Random Effects (RE)**: if Hausman test fails to reject (p > 0.05), RE is efficient
4. **Two-way FE**: State + Time fixed effects — absorbs both state heterogeneity and common macro shocks
5. **Dynamic Panel (Arellano-Bond GMM)**: handles lagged dependent variable (sales_t-1 predicts sales_t) — critical for autocorrelated sales data

**Key regression specifications**:

\[ \log(Sales_{it}) = \alpha + \beta_1 \log(Income_{it}) + \beta_2 FuelPrice_{it} + \beta_3 LoanRate_t + \beta_4 EV\_Chargers_{it} + \gamma_i + \delta_t + \epsilon_{it} \]

**Interpretation**: \(\beta_1\) is the income elasticity of 4W PV demand; \(\beta_2\) is the own-price fuel effect.

### 4.3 Additional Statistical Methods

| Method | What It Answers | Implementation |
|---|---|---|
| **VAR (Vector Autoregression)** | Do wholesale dispatches Granger-cause retail sales, or vice versa? Lead-lag dynamics between OEMs | `statsmodels.tsa.VAR` |
| **Granger Causality Test** | Does petrol price Granger-cause EV adoption at state level? | `statsmodels.tsa.stattools.grangercausalitytests` |
| **Structural Break Tests (Bai-Perron)** | Where are the statistically significant inflection points in India PV sales? | `ruptures` library |
| **Chow Test** | Did FAME-II (2019) structurally break the EV adoption trend? | Manual F-test |
| **Cointegration (Johansen/Engle-Granger)** | Are petrol price and diesel PV sales cointegrated long-term? | `statsmodels.tsa.johansen` |
| **Error Correction Model (ECM)** | Short-run vs long-run dynamics after cointegration | Follows Johansen test |
| **Quantile Regression** | Does income matter more for upper-quintile EV buyers than median buyers? | `statsmodels.regression.quantile_regression` |
| **Synthetic Control** | What would Maharashtra EV sales have been without FAME II? | Manual synth control |
| **Difference-in-Differences (DiD)** | Impact of a specific state EV policy (e.g., Telangana waiver) vs control states | `causalpy` or manual |
| **Regression Discontinuity (RDD)** | Did BS6 emission cutoff date create a sharp sales discontinuity? | `rdrobust` or manual |
| **LASSO / Ridge Panel Regression** | Which of 20+ macroeconomic variables actually predict 4W PV sales? | `sklearn` with panel structure |
| **Propensity Score Matching (PSM)** | Match states that adopted EV policies vs those that didn't for causal inference | `causalml` |

---

## 5. Complexity Science & Network Science Experiments

This is the deepest analytical frontier. Below are 45 experiments organized from simple to advanced.

### Tier 1 — Foundational Network Construction (Experiments 1–10)

**E1: OEM–State Bipartite Network** (already built)
Nodes: OEMs + States. Edge weight = MS share. Study degree distribution, clustering, modularity.

**E2: State–State Similarity Network**
Connect states if their OEM MS profile (vector) has cosine similarity > threshold. Cluster = regional automotive culture.

**E3: OEM–OEM Competition Network**
Connect two OEMs if they share top-3 states (overlap coefficient > 0.5). Dense cluster = head-on competitive arena.

**E4: Model–State Bipartite Network**
Using wholesale model data: which models sell in which states? Detect model diffusion geography.

**E5: Fuel-Type Transition Network**
Node = (State, Year). Directed edge if a state's dominant fuel shifts. Maps the Petrol→Diesel→CNG→EV transition as a directed graph.

**E6: Temporal Snapshot Networks**
Build annual OEM–State networks for each year 2012–2025. Track: Which edges appear? Which disappear? Which OEMs enter/exit states?

**E7: Weighted Degree Centrality**
For each OEM: sum of edge weights across all states = national reach score. For each state: sum = market openness.

**E8: Betweenness Centrality of OEMs**
Which OEMs serve as "bridges" between otherwise disconnected regional clusters? High betweenness = pan-India player.

**E9: PageRank on OEM–State Network**
Treat state importance (by volume) as authority. PageRank of OEM = influenced by volume of high-volume states.

**E10: Eigenvector Centrality**
An OEM is important if it is connected to important states. Reveals structural dominance beyond pure MS.

### Tier 2 — Community Detection & Clustering (Experiments 11–18)

**E11: Louvain Community Detection** (already built)
Tune resolution parameter (gamma) from 0.5 to 2.0. How does community structure change?

**E12: Leiden Algorithm**
More stable than Louvain; produces better-connected communities. Compare to Louvain output.

**E13: Girvan-Newman (Edge Betweenness)**
Remove highest-betweenness edges iteratively. Reveals hierarchical community structure.

**E14: Spectral Clustering on Adjacency Matrix**
Decompose graph Laplacian eigenvalues. Number of near-zero eigenvalues = natural cluster count.

**E15: Stochastic Block Model (SBM)**
Probabilistic generative model: what block structure best explains the OEM–State network? Use `graph-tool`.

**E16: Regional Community Mapping**
Map detected communities to actual Indian geographic regions. Do South Indian states cluster with South-dominant OEMs (Hyundai)?

**E17: Temporal Community Tracking**
Track community memberships across annual snapshots. Which states shift communities? Corresponds to competitive dynamics.

**E18: Hierarchical Nesting of Communities**
Use Infomap algorithm with nested structure. Are there sub-communities within the "Maruti-dominated North" community?

### Tier 3 — Diffusion & Contagion Models (Experiments 19–26)

**E19: Bass Model on State Graph** (already built)
Fit Bass p/q per state. Visualize p-q plane: which states are innovator-driven vs imitation-driven?

**E20: Network-Aware Bass Model**
Modify Bass model so imitation coefficient q is weighted by adjacency in the state–state network. Adoption spreads along geographic edges.

**E21: SIR Model on EV Adoption**
S = non-EV states, I = actively adopting, R = saturated markets. Run SIR on state network. Identify epidemic threshold.

**E22: Threshold Contagion Model**
Each state adopts EV when fraction of neighboring states exceeds a threshold τ. Sweep τ from 0.1–0.9 to find cascade onset.

**E23: Independent Cascade (IC) Model**
Seed a high-centrality state (Maharashtra). At each step, each infected state infects each neighbor with probability p. Find critical p for full cascade.

**E24: Linear Threshold (LT) Model**
Each state has a threshold; adopts when weighted sum of neighbor influences exceeds it. Models policy diffusion (one state's EV waiver inspires neighbors).

**E25: Watts-Strogatz Rewiring & Small World Coefficient**
Compute sigma = C/C_random ÷ L/L_random. Is the OEM–State network a small world? Rewire edges and observe how quickly adoption spreads.

**E26: Barabási-Albert Preferential Attachment**
Simulate how a new OEM entering India would grow its state coverage under preferential attachment. Compare to actual entry strategies of MG, Kia.

### Tier 4 — Temporal & Dynamic Networks (Experiments 27–33)

**E27: Network Modularity Time Series**
Already computed for OEM–State. Now compute for: State–State network. Fuel–State network. Track all three on same axis.

**E28: Edge Persistence Analysis**
Which OEM–State edges are present in every year? Which appear/disappear? Persistent edges = structural anchors; transient edges = competitive battlegrounds.

**E29: Graph Edit Distance (GED)**
Compute GED between consecutive annual network snapshots. Large GED = year of market disruption. Validate against known events (BS6, COVID, new entrants).

**E30: Temporal Motif Analysis**
In directed time-stamped graphs, identify recurring 3-node motifs (triangles, stars, chains) over time. Motif frequency changes = structural shift.

**E31: Link Prediction**
Train a model (Jaccard, Adamic-Adar, or GNN-based) on network up to 2022 to predict which OEM–State edges emerge in 2023–2025. Evaluate precision@k.

**E32: Network Entropy Over Time**
Shannon entropy of the degree distribution each year. Low entropy = concentrated market (Maruti dominance). Rising entropy = market fragmentation (SUV boom, new entrants).

**E33: Persistence Homology on Sales Manifold**
Treat (State, Time, Sales) as a point cloud. Topological Data Analysis (TDA) using Gudhi or Ripser to find persistent features (loops = cyclical patterns, voids = market gaps).

### Tier 5 — Advanced & Research-Grade (Experiments 34–45)

**E34: Multiplex Network**
Layer 1: OEM–State network (retail share). Layer 2: OEM–State network (wholesale share). Layer 3: OEM–State network (EV share). Analyze inter-layer correlations and multiplex centrality.

**E35: Hypergraph of Automotive Ecosystem**
Hyperedges connect OEM + State + Fuel type simultaneously. Captures three-way relationships beyond pairwise networks.

**E36: Graph Neural Network (GNN) for Demand Forecasting**
Encode state network as graph. Use GraphSAGE or GAT to propagate neighborhood features. Predict next-month EV share for each state using graph structure + time series features.

**E37: Motif-Aware Community Detection**
Weight edges by motif participation count before running community detection. Do motif-weighted communities match geographic clusters better than unweighted?

**E38: Renormalization Group on OEM–State Network**
Apply block renormalization: coarse-grain by merging weakly-connected nodes. Study how market structure simplifies at different scales. Connection to complexity science: self-similarity of market hierarchies.

**E39: Phase Transition Analysis**
Vary edge threshold from 0.001 to 0.1. At which threshold does the network undergo a percolation phase transition (giant component collapses)? The critical threshold is the "minimum viable presence" for an OEM in a state.

**E40: Attractor Analysis via Recurrence Quantification Analysis (RQA)**
Treat state-level EV sales time series as a dynamical system. Compute RQA metrics (recurrence rate, determinism, laminarity). High determinism = predictable adoption trajectory. Low = chaotic/disrupted.

**E41: Entropy Production Rate**
Compute Kolmogorov-Sinai entropy of the sales dynamical system using embedding dimension and Lyapunov exponents. Rising entropy = system becoming unpredictable (market disruption incoming).

**E42: Fitness-Complexity Algorithm (Economic Complexity)**
Adapted from Hausmann/Hidalgo Product Space: compute Fitness of states (diversification of OEM presence) and Complexity of OEMs (ubiquity-corrected). Reveals hidden state-level automotive capability.

**E43: Random Matrix Theory (RMT) Filtering**
Compute correlation matrix of OEM MS time series. Apply RMT to filter noise (Marchenko-Pastur distribution). Remaining structure = true OEM correlations, not sampling noise. Better than naive Pearson.

**E44: Transfer Entropy Between OEMs**
Compute Transfer Entropy from OEM_A sales to OEM_B sales: does Hyundai's volume Granger-cause Kia's volume (same conglomerate)? Does Tata's EV surge transfer entropy to Maruti's EV launch timing?

**E45: Sandpile / Self-Organized Criticality (SOC) Model**
Model market share redistributions as a sandpile: small perturbations (new model launch) can trigger avalanches of MS shifts across the network. Track avalanche size distribution — power law = SOC. Validates complexity science framing of the automotive market.

---

## 6. Forecasting

### 6.1 Benchmark Models

| Model | Rationale | Library |
|---|---|---|
| Naïve Seasonal | Baseline: same month last year | Manual |
| ETS (Error-Trend-Seasonal) | Classic exponential smoothing with multiplicative seasonality | `statsforecast` |
| SARIMA / SARIMAX | Handles seasonality + exogenous regressors (fuel price, loan rate) | `statsmodels` |
| STL + ETS decomposition | Robust to outliers (COVID), separable trend/seasonal/residual | `statsforecast` |

### 6.2 Machine Learning Models

| Model | Strengths | Notes |
|---|---|---|
| LightGBM / XGBoost with lag features | Fast, interpretable, handles non-linearity | Create lag_1, lag_12, rolling_mean_3 features |
| LSTM / GRU | Sequence memory — good for 120+ month series | `PyTorch` or `Keras` |
| Temporal Fusion Transformer (TFT) | Multi-horizon, handles static + dynamic covariates | `pytorch-forecasting` |
| N-BEATS | Pure neural, no feature engineering, interpretable via basis expansion | `neuralforecast` |
| N-HiTS | Multi-rate sampling, strong on long-horizon | `neuralforecast` |

### 6.3 Ensemble & Reconciliation

- **M5-style ensemble**: Weighted average of SARIMA + LightGBM + N-HiTS
- **Hierarchical reconciliation (MinT)**: Forecast at National + State + OEM levels simultaneously; ensure bottom-up sum = top-down total using MinTrace method (`hierarchicalforecast` library)

### 6.4 Forecasting-Specific Features

From your data:
- Lagged wholesale dispatches (ws_t-1, ws_t-2) as leading indicator for retail
- Festive season dummy (Oct-Nov)
- Year-end (March) surge dummy
- BS-norm year dummies
- COVID impact window dummy (2020-04 to 2021-03)

From public data:
- Petrol/diesel retail price (monthly)
- Auto loan interest rate (monthly)
- Consumer Sentiment Index (quarterly, interpolated)
- FAME subsidy disbursement (monthly)

### 6.5 Evaluation Metrics

| Metric | Use Case |
|---|---|
| MAPE | Easy to communicate; sensitive to near-zero values |
| sMAPE | Symmetric version — better for EV states with low base |
| RMSSE | M5-competition standard; robust to outliers |
| Coverage (95% PI) | For prediction intervals — are 95% of actuals within the band? |
| Bias | Are we systematically over/under-forecasting a specific OEM? |

---

## 7. App Architecture Improvements

### 7.1 Experiment Registry System

Every page in the app should declare a metadata block that renders as a sidebar card:

```python
EXPERIMENT_META = {
    "id": "NET-003",
    "name": "OEM–State Bipartite Network",
    "category": "Network Science",
    "tier": "Tier 1 — Foundational",
    "data_used": ["Vahan retail", "State boundaries"],
    "method": "Louvain community detection on bipartite graph",
    "what_we_test": "Do OEMs cluster by regional dominance?",
    "what_to_look_for": "Modularity > 0.15 = distinct regional clustering",
    "limitations": "Threshold parameter sensitive; try 0.001–0.02",
    "related_experiments": ["NET-001", "NET-002", "DIFF-001"],
}
```

Render this as a collapsible "Experiment Card" in the sidebar. Users always know what they are running.

### 7.2 Data Provenance Panel

Global sidebar widget showing:
- Data freshness: "Vahan last loaded: 2026-05 | Wholesale last loaded: 2026-04"
- Row counts: "Vahan: 4W PV = 1,24,560 rows | Wholesale: 4W PV = 43,200 rows"
- Coverage warnings: "Wholesale pre-2022: ~50-city sample — state-level aggregates may be unreliable"
- Active filters: "Segment: 4W PV | States: All | Fuel: All"

### 7.3 Shared Filter State

Use `st.session_state` to persist:
- Selected states
- Date range
- OEM filter
- Fuel filter

All pages read from `session_state["global_filters"]`. A global filter bar at the top of every page lets users change context once without re-setting on each page.

### 7.4 Visualization Standards

| Chart type | Recommended library | Rationale |
|---|---|---|
| Time series | Plotly | Interactive zoom, multi-trace |
| Network graphs | PyVis or vis.js (via streamlit-components) | Force-directed, zoom/pan, node click |
| Choropleth maps | Plotly + GeoJSON | State-level fill |
| Heatmaps | Plotly or Seaborn | State × Time matrices |
| Statistical summaries | Plotly violin / box | Distribution comparison |
| TDA output | Custom matplotlib | Persistence diagrams |
| Sankey flows | Plotly | Fuel transition flows |

### 7.5 Page Structure Template

Every experiment page should follow this consistent layout:

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Experiment Card — sidebar or collapsible]                          │
│  ID | Name | Category | Tier | Data | Method | Output to watch       │
├──────────────────────────────────────────────────────────────────────┤
│  Section 0: Why this matters                                         │
│  (1–2 lines: business question, market relevance, why user should care)│
├──────────────────────────────────────────────────────────────────────┤
│  Section 1: Working & background knowledge                           │
│  (what this method is, how it works, when to use it, assumptions)    │
├──────────────────────────────────────────────────────────────────────┤
│  Section 2: Concepts in plain English                                │
│  (layman explanation of terms like correlation, modularity, entropy) │
├──────────────────────────────────────────────────────────────────────┤
│  Section 3: Math made simple                                         │
│  (formula + symbol legend + worked toy example + interpretation)     │
├──────────────────────────────────────────────────────────────────────┤
│  Section 4: Controls / Parameters                                    │
│  (sliders, dropdowns, date range, threshold, model options)          │
├──────────────────────────────────────────────────────────────────────┤
│  Section 5: Data being used                                          │
│  (dataset names, date coverage, joins, filters, sample caveats)      │
├──────────────────────────────────────────────────────────────────────┤
│  Section 6: Primary Visualization                                    │
│  (main chart/graph, full width, with annotations)                    │
├──────────────────────────────────────────────────────────────────────┤
│  Section 7: Statistical Summary                                      │
│  (3–6 KPI cards + confidence/p-value/error metrics where relevant)   │
├──────────────────────────────────────────────────────────────────────┤
│  Section 8: Interpretation guide                                     │
│  (what high/low values mean, what is good/bad, what changed)         │
├──────────────────────────────────────────────────────────────────────┤
│  Section 9: Decision use-cases                                       │
│  (how OEM, dealer, investor, analyst can use this output)            │
├──────────────────────────────────────────────────────────────────────┤
│  Section 10: Data table & downloads                                  │
│  (underlying data, downloadable CSV, model summary, assumptions)     │
└──────────────────────────────────────────────────────────────────────┘
```

#### 7.5.1 Recommended content inside each section

| Section | What it should contain | Why it matters |
|---|---|---|
| Why this matters | One business question, one research question, one expected insight | Prevents the page from feeling like "analysis for analysis's sake" |
| Working & background knowledge | Method overview, required assumptions, strengths, failure cases | Helps users understand what the method is actually doing behind the chart |
| Concepts in plain English | Layman definitions of each technical term on the page | Makes the page usable by non-technical stakeholders |
| Math made simple | Formula, variable legend, worked example, plain-English reading | Makes statistical output trustworthy and teachable |
| Controls / Parameters | Parameter name, default value, valid range, effect of increasing/decreasing it | Prevents black-box experimentation |
| Data being used | Source, grain, time span, joins, filters, missingness, caveats | Improves data provenance and trust |
| Primary Visualization | Main visual, key annotation, benchmark line, event markers | Turns the page into a decision interface |
| Statistical Summary | KPI cards, uncertainty bands, significance flags | Gives quick takeaways before deeper reading |
| Interpretation guide | "If X rises, it usually means..." and "Do not over-interpret when..." | Avoids misuse |
| Decision use-cases | Actions for product, market, policy, and supply-chain teams | Makes research operational |
| Data table & downloads | Raw data, transformed data, assumptions, export buttons | Supports validation and re-use |

#### 7.5.2 Working & background knowledge block

Every page should include a collapsible explainer titled **How this works** with the following sub-parts:

1. **What is this method?** — one short paragraph.
2. **What question does it answer?** — one sentence.
3. **How does it work step by step?** — 3 to 5 bullets.
4. **What assumptions does it make?** — for example linearity, stationarity, or network threshold sensitivity.
5. **When should it not be trusted?** — small sample, missing data, policy shock, unstable regime.
6. **What is the output?** — coefficient, forecast, p-value, modularity, centrality, etc.

Example:

- **Correlation**: measures whether two things tend to move together.
- **Regression**: estimates how much one factor changes another while holding other factors constant.
- **Modularity**: measures how clearly the network breaks into clusters.
- **Entropy**: measures how ordered or disordered the market structure is.
- **Forecast interval**: gives a range, not just a single-point forecast.

#### 7.5.3 Concepts in plain English block

Each page should have a compact glossary written for a layperson. Suggested format:

| Term | Plain-English meaning | Automotive example |
|---|---|---|
| Correlation | Two things move together, but one may not cause the other | States with more chargers may also have higher EV share |
| Causation | One thing helps produce the other | A subsidy directly lowers EV cost and may lift demand |
| Market share | Out of every 100 cars sold, how many belong to one OEM | 42 out of 100 means 42% MS |
| Penetration | How much of the total market belongs to one fuel or segment | EV penetration of 3% means 3 of every 100 registrations are EVs |
| Modularity | How strongly the market splits into clusters | South Indian states behaving similarly can form one cluster |
| Centrality | How important a node is inside a network | Maharashtra may be central because it connects multiple adoption patterns |
| Forecast | Best estimate of future value using history and drivers | Next 12 months of PV registrations |
| Confidence / prediction interval | The likely range around an estimate | Forecast says 3.5 lakh, but realistic range is 3.2–3.8 lakh |

#### 7.5.4 Math made simple block

Every experiment page should explain the mathematics in four layers:

1. **Formula** — the exact mathematical expression.
2. **Symbols** — what each symbol means in ordinary words.
3. **Toy example** — very small numbers with a manual calculation.
4. **Interpretation** — what the final number means in business language.

Example format:

**Market share**

\[
MS = rac{OEM\ Sales}{Total\ Market\ Sales} 	imes 100
\]

- `OEM Sales` = registrations of one OEM.
- `Total Market Sales` = registrations of all OEMs together.
- If Tata sells 12,000 vehicles and the market is 100,000, then market share is 12%.
- Business meaning: Tata captured 12 out of every 100 registrations.

**Correlation**

- Correlation ranges from -1 to +1.
- Near +1 means both usually rise together.
- Near 0 means no stable relationship.
- Near -1 means one tends to rise when the other falls.
- Layman warning: correlation is a pattern, not proof of cause.

**Regression coefficient**

- If a coefficient on income is 0.8 in a log-log model, then a 1% increase in income is associated with roughly 0.8% higher sales.
- Layman reading: richer states tend to buy more cars, and the model quantifies by how much.

**Modularity**

- Modularity is a score for how cleanly a network separates into groups.
- Higher modularity means stronger clustering.
- Layman reading: the market has distinct regional camps rather than one uniform national pattern.

**Forecast error**

\[
MAPE = rac{1}{n} \sum \left| rac{Actual - Forecast}{Actual} ight| 	imes 100
\]

- This tells us the average percentage miss.
- If MAPE is 6%, forecasts are off by about 6% on average.
- Layman reading: lower is better; it is the model's average mistake size.

#### 7.5.5 Design rule for explainability

For every advanced chart, include three tabs beneath it:

- **Read this chart** — how to look at it in 20 seconds.
- **Concepts** — glossary and assumptions.
- **Math** — formulas and a toy example.

This is especially important for pages such as Panel Regression Lab, Complexity Lab, Forecasting Studio, and Diffusion Lab, where users may otherwise see an impressive output without understanding what exactly it means.

### 7.6 New Pages to Add

| Page | Experiments | Priority |
|---|---|---|
| **Macro Dashboard** | KPIs, MS, Fuel Pen%, WS Ratio | P0 — missing today |
| **OEM Deep Dive** | Model-level Treemap, MS trend, channel health per OEM | P0 |
| **State Intelligence** | Choropleth MS, state CAGR, regression output per state | P1 |
| **Structural Breaks** | Bai-Perron, Chow test, CUSUM | P1 |
| **Panel Regression Lab** | FE/RE/GMM interface, coefficient plots | P1 |
| **Forecasting Studio** | Model selection, feature flags, evaluation scorecard | P1 |
| **Complexity Lab** | All Tier 3–5 experiments; network entropy, TDA, SOC | P2 |
| **Policy Analyser** | DiD, RDD, Synthetic Control for FAME II, BS6, state EV policies | P2 |
| **Data Ingestion** | Upload new monthly data, validate schema, run tests | P0 |

### 7.7 Data Pipeline Improvements

- **Fuel-type proxy for wholesale**: Build a model-name → fuel-type lookup table from SIAM/OEM catalogues. Update monthly as new models launch.
- **Pre-2022 wholesale normalisation**: Scale city-sample data using known state-level shares from 2022 onwards to backfill.
- **Automated consistency checks**: Assert `Σ(wholesale by state) ≈ SIAM national total ± 5%` on each monthly load.
- **Freshness alerts**: If Vahan data is >45 days stale, display a banner on all pages.

---

## 8. Research Output Framework

For each experiment tier, suggested research outputs:

| Tier | Output Type | Venue |
|---|---|---|
| Descriptive KPIs | Blog post / dashboard for SaaS | Vahan Intelligence platform |
| Regression & Correlation | Technical article | LinkedIn / Substack / Beehiiv |
| Network Science Tier 1–2 | White paper | SSRN pre-print |
| Diffusion Models | Conference paper | Complex Systems Society / NetSci |
| Advanced (E33–E45) | Journal paper | Nature Scientific Reports / PLOS ONE / Physica A |
| Forecasting | Product feature + accuracy report | Vahan Intelligence SaaS |

---

## 9. Implementation Roadmap

### Phase 1 (Month 1–2): Foundation
- Build Macro Dashboard with all Descriptive KPIs (Section 2)
- Add global filter state management
- Implement Experiment Card metadata system
- Integrate public data: PPAC fuel prices, RBI loan rates

### Phase 2 (Month 2–4): Statistical Analysis
- Panel Regression Lab (FE, RE, Two-way FE)
- Correlation Heatmap improvements (partial correlation, RMT filtering)
- Granger Causality: wholesale → retail
- Structural break detection (Bai-Perron)

### Phase 3 (Month 3–6): Complexity & Network Science
- Tier 1–3 network experiments (E1–E26)
- Network entropy time series
- Bass model variants (E19–E21)
- Temporal community tracking (E17, E28–E29)

### Phase 4 (Month 5–8): Forecasting Studio
- SARIMA + LightGBM baselines
- TFT / N-HiTS for multi-horizon
- Hierarchical reconciliation
- Prediction interval coverage evaluation

### Phase 5 (Month 8–12): Advanced Research
- GNN demand forecasting (E36)
- Economic Complexity / Fitness algorithm (E42)
- RMT filtering (E43)
- Transfer Entropy (E44)
- TDA / Persistence Homology (E33)
- SOC Sandpile model (E45)


---

## 10. Design Philosophy for Data Presentation

Before any chart or table is built in the app, a single question should govern every decision: *Does this output communicate, or just display?* Data that is accurate but poorly presented is as useless as data that is absent. Every KPI, every graph, every table in this platform should feel like it was designed, not rendered. That means using visual hierarchy — making the most important number the biggest, placing context immediately next to the data point it contextualises, choosing chart types that match the shape of the insight rather than what is easiest to build. It means colour used sparingly and deliberately: one accent colour for the primary signal, muted neutrals for everything else, and never more than two non-neutral hues in a single viewport. It means that whitespace is as important as ink — crowded dashboards hide insights, while clean surfaces let numbers speak. It means that typography carries weight: a KPI card where the metric label and the number are the same size is a missed opportunity; the number should be at least 2.5× larger. It means that motion and interactivity are tools for discovery, not decoration — a tooltip that reveals context on hover, a slider that shows time progression, a click that drills to state level, all make the user feel they are exploring rather than reading. Every page in this app should feel like an editorial decision was made about what the user needs to know first, second, and third — and the visual layout should enforce that sequence. Design sense in data is not about making charts beautiful for aesthetics; it is about making insight inevitable.

---

## 11. Model Count Evolution Over Years

### 11.1 Why Model Count Matters

The number of distinct models available in the market in each year is a **supply-side complexity signal**. When choice expands, competition shifts from price to product differentiation. Model count growth is one of the earliest indicators of segment transitions — the SUV explosion of 2017–2023 was preceded by a rapid increase in compact SUV model count, not a price change or income shock.

**Practical significance**: An OEM strategist watching model count per segment can spot where a competitor is building a portfolio before market share moves. A dealer can anticipate which segments will attract more footfall. A researcher can use model count as an instrumental variable for market complexity in panel regressions.

### 11.2 Data Construction

Using your wholesale data (2017–2026, model-level):

```python
# Count distinct models per segment × year × OEM
model_counts = (
    wholesale_df
    .groupby(['year', 'segment', 'oem'])['model']
    .nunique()
    .reset_index(name='model_count')
)
```

For **fuel-type model count** (since wholesale has no fuel): cross-reference model names against a manually built lookup table (see Section 11.4).

### 11.3 Experiments

| Experiment | What it shows | Practical significance |
|---|---|---|
| **MC-01**: Total 4W PV model count by year | Complexity of buyer choice over time | More models = more fragmented market = lower individual MS per model |
| **MC-02**: Model count by OEM over time | Which OEM is expanding / contracting its portfolio | Maruti's compact car dominance vs Tata/Hyundai's SUV portfolio builds |
| **MC-03**: Model count per segment (Hatchback, Sedan, UV, EV) | Segment-wise product proliferation | Compact SUV model explosion is the story of 2018–2023 |
| **MC-04**: Model survival curves | How long does a model stay in production? | Long-lived models = cash cows; short-lived = failed bets |
| **MC-05**: New model launch frequency per month | Seasonality in launches | Heavy launch cycles before Diwali / Auto Expo indicate OEM strategy |
| **MC-06**: Model count vs segment MS correlation | Does more choice drive more segment share? | Tests the "portfolio breadth buys market" hypothesis |
| **MC-07**: Model churn rate | Models entering and exiting each year | High churn = volatile OEM strategy |
| **MC-08**: Fuel-type model count over time | How many petrol / CNG / EV models existed per year | Structural shift in OEM product planning visible before retail data |

### 11.4 Fuel-Type Proxy for Wholesale

Since wholesale has no fuel breakup, build a model→fuel mapping:

**Sources**:
- SIAM monthly press releases (PDF, scrape-able)
- CarDekho / Cardwale API (unofficial, model specs)
- OEM official websites (model specs pages, scrapeable)
- Vahan model names — cross-match with wholesale model strings using fuzzy matching

**Python approach**:
```python
from rapidfuzz import process
# match wholesale 'model' col to vahan OEM+model strings
# then look up fuel from vahan
```

**Output**: `model_fuel_map.csv` — a static lookup refreshed monthly. Flag models that exist in both petrol and diesel variants as `multi-fuel`.

---

## 12. Fuel Price Integration via APIs

### 12.1 Data Sources & APIs

| Source | Data | Access method | Frequency |
|---|---|---|---|
| **PPAC (Petroleum Planning & Analysis Cell)** | Retail petrol, diesel prices — city-wise | PDF scrape at `ppac.gov.in/content/245_1_PricesPetroleum.aspx` | Monthly |
| **IOC / BPCL / HPCL** | Daily fuel price by city | Unofficial JSON endpoints scraped from their dealer price apps | Daily |
| **PPAC CNG price** | CNG city-wise retail price | PDF scrape | Monthly |
| **Global Brent crude** | International crude benchmark | `yfinance` (`BZ=F`) or `quandl` / `nasdaq-data-link` | Daily |
| **Natural gas price** | Input cost for CNG | `yfinance` (`NG=F`) or EIA API | Daily |

**PPAC scraper skeleton**:
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://ppac.gov.in/content/245_1_PricesPetroleum.aspx"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(r.text, "html.parser")
# Parse tables for petrol/diesel/CNG retail prices
```

**Yfinance for crude**:
```python
import yfinance as yf
brent = yf.download("BZ=F", start="2012-01-01", period="1d")["Close"]
```

### 12.2 State-Level Aggregation

Fuel prices vary by city due to state taxes (VAT/sales tax) and freight. Steps:
1. Download city-level prices
2. Map each city to its state using a `city_state_map.csv`
3. Compute state-level monthly average (volume-weighted if population data available)

**Practical significance**: Petrol/diesel price differential is the single most important driver of fuel-type shift in the Indian PV market. When diesel premium over petrol narrows below ₹5/litre, diesel car sales reliably soften. Encoding this as a monthly state-level variable gives your regression models a causal lever that is well-understood and actionable.

### 12.3 Derived Features from Fuel Price Data

| Feature | Formula | Interpretation |
|---|---|---|
| `diesel_petrol_spread` | Diesel price − Petrol price | Key driver of diesel vs petrol preference |
| `cng_petrol_ratio` | CNG price / Petrol price | When <0.5, CNG becomes very attractive |
| `fuel_real_price` | Nominal price / CPI | Inflation-adjusted affordability |
| `fuel_price_yoy_chg` | (Price_t / Price_t-12) − 1 | Momentum signal |
| `crude_import_price` | Brent in INR | Lagged 3–4 months → feeds domestic retail price |

---

## 13. RTO Life Tax (Road Tax) by State

### 13.1 What is Road Tax / Life Tax?

In India, vehicle registration involves a **one-time lifetime road tax** paid to the state government, calculated as a percentage of the vehicle's ex-showroom price. This is distinct from GST (paid at purchase) and insurance. It varies significantly by state — making a vehicle effectively more expensive in some states than others for an identical model.

**Layman analogy**: If you buy the same phone in two states, you pay the same price. But if you buy the same car in Karnataka vs Maharashtra, you pay a different one-time tax at the RTO, making the on-road price higher in one state.

### 13.2 Tax Rates by State (Indicative, 2024–25)

| State | Road Tax (% of ex-showroom) | EV exemption |
|---|---|---|
| Delhi | 4–10% (slab-based) | Full exemption for EVs |
| Karnataka | 13–18% | 50% reduction for EVs |
| Maharashtra | 7–11% | Full exemption for EVs (select segments) |
| Tamil Nadu | 8–12% | 50% reduction |
| Telangana | 9–12% | 100% exemption for EVs (2023 policy) |
| Gujarat | 6–10% | 100% exemption for EVs |
| UP | 7–10% | 25% reduction |
| Rajasthan | 6–10% | 50% reduction |

**Data source**: State Motor Vehicles Acts; scrape from individual state transport dept websites or compile from LegalDesk / ACKO insurance comparison pages.

### 13.3 Experiments Using Road Tax Data

| Experiment | Method | Practical significance |
|---|---|---|
| **TAX-01**: Road tax vs EV penetration by state | Scatter with regression line | Quantifies policy generosity → adoption conversion rate |
| **TAX-02**: On-road price parity — EV vs ICE by state | Compute effective on-road price gap after tax | Identifies states where EV price parity already exists |
| **TAX-03**: Road tax elasticity of PV demand | Panel FE regression with road tax as covariate | Estimates how much a 1pp tax increase reduces registrations |
| **TAX-04**: Tax reform event study | Before/after DiD when a state changes EV tax policy | Tests if Telangana's waiver caused a measurable EV surge |
| **TAX-05**: OEM pricing strategy by state | Wholesale price (if available) × tax = on-road premium | Do OEMs adjust their base price to neutralise high-tax states? |

---

## 14. Policy Events Database

### 14.1 What is a Policy Event?

A **policy event** is any government action — national or state — that creates a measurable shift in the incentive to buy, produce, or register a vehicle. Encoding these as dated dummy variables (or continuous treatment variables) transforms your regression from a descriptive model into a causal analysis instrument.

### 14.2 Key Policy Events Catalogue

| Event | Date | Type | Expected direction of effect | How to detect in data |
|---|---|---|---|---|
| **GST rollout** | July 2017 | Tax restructure | Short-term demand pull-forward before July; post-July normalization | Sales spike in June 2017, dip July–Aug |
| **BS4 end / BS6 start** | April 2020 | Emission norm | Massive BS4 inventory liquidation in Feb–March 2020; sharp drop in April | Extreme March 2020 spike → April collapse |
| **COVID lockdown — wave 1** | Apr–Jun 2020 | Demand shock | Near-zero registrations | Volume → 0 |
| **FAME I** | April 2015 | EV subsidy | Early EV adoption incentive | Small EV share lift in 2015–2016 |
| **FAME II** | April 2019 | EV subsidy | Significant EV cost reduction | Break in EV penetration trend post-2019 |
| **FAME III / PM e-DRIVE** | Sep 2024 | EV subsidy | EV acceleration; 2W/3W focus | EV share inflection in 2024 |
| **PLI Auto Scheme** | Sep 2021 | Supply-side | OEM capex → new models in 2–3 year lag | Model count rise 2023–2025 |
| **Production subsidy for CNG** | Ongoing | Fuel availability | CNG availability in tier-2 cities | CNG penetration state × time |
| **Scrappage Policy** | Oct 2021 | Demand stimulus | Old vehicle replacement + small new-vehicle bounce | Age profile shift; marginal demand lift |
| **RBI rate hike cycle** | May 2022–Feb 2023 | Monetary policy | EMI increase → demand softness | Loan rate × volume correlation |
| **RBI rate cut cycle** | 2024–2025 | Monetary policy | EMI decrease → demand recovery | Same |
| **Delhi odd-even / diesel ban threat** | 2015–2019 | Regulatory risk | Diesel demand suppression in Delhi | Diesel share fall in Delhi 2016–2017 |
| **Telangana EV road tax waiver** | 2023 | State EV policy | EV adoption spike in Telangana | DiD vs similar states |
| **Gujarat EV policy** | 2021 | State EV policy | Strong EV adoption acceleration | Gujarat EV penetration relative to peers |
| **New connected car / AIS 140 mandate** | April 2018 | Safety norm | Small demand disruption (compliance cost) | Volume dip in commercial; marginal PV effect |

### 14.3 How to Use Policy Events in the App

**Annotation layer**: Every time-series chart should support a toggle "Show policy events" that overlays vertical dashed lines with tooltips explaining the event.

**Treatment variable encoding**:
- Binary dummy: `bs6_post = 1 if date >= 2020-04-01`
- Continuous treatment: `fame2_subsidy_amt_inr` — actual disbursement amount per state per month
- Ramp variable: `months_since_fame2` — allows gradual treatment effect

**Practical significance**: Without annotating policy events, charts tell you *what* happened. With events, they tell you *why*. That is the difference between a dashboard and an analysis tool. When a client sees EV share rising in 2019, they need to immediately know whether it was FAME II, natural income growth, or charging infrastructure — the annotation layer forces that question to the surface.

### 14.4 Event-Specific Experiments

| Experiment | Method | Practical significance |
|---|---|---|
| **POL-01**: BS6 transition demand cliff | Structural break test (Chow / Bai-Perron) on March 2020 | Quantifies the inventory clearing effect and BS6 disruption size |
| **POL-02**: FAME II EV adoption lift | Difference-in-Differences (states with high vs low FAME-eligible vehicles) | Causal estimate of FAME II's effectiveness |
| **POL-03**: GST pre-buy effect | Regression discontinuity at June/July 2017 boundary | How many months of demand were pulled forward |
| **POL-04**: State road-tax EV waiver impact | DiD: treated state vs synthetic control | Which state waiver design worked best |
| **POL-05**: Rate hike / rate cut elasticity | VAR: loan rate → PV sales lag structure | How many months does a rate change take to affect volumes |
| **POL-06**: Scrappage uptake spatial map | State-level scrappage registrations vs new-vehicle delta | Whether scrappage generated incremental demand or was purely a swap |

---

## 15. Segment Transition Experiments

### 15.1 The Structural Story

India's 4W PV market underwent one of the most dramatic segment transitions in any major auto market globally: from hatchback-dominant in 2014 to compact-SUV-dominant by 2023. This was not smooth — it was a series of tipping points driven by road quality improvements, aspirational income effects, and product launches. Understanding *which states are SUV-heavy, which are still hatchback-loyal, and which are transitioning* gives both OEMs and policy analysts a geography of aspiration.

**Layman analogy**: Think of it as a food preference transition. In 2012, most restaurants served idli-dosa (hatchbacks — essential, economical). By 2024, the most popular item on the menu became a premium thali (SUV — more indulgent, more aspirational). But not every region switched at the same pace. The segment experiment maps where each state is on that journey.

### 15.2 Segment Taxonomy

| Segment code | Description | Price band (approx.) | Representative models |
|---|---|---|---|
| Hatchback | Small, 3-box alternative, entry | ₹4–10L | Alto, WagonR, i10, Punch |
| Sedan | 3-box, mid-premium | ₹8–20L | Dzire, Amaze, City, Verna |
| Compact SUV / UV | Sub-4m or 4–4.5m UV | ₹8–22L | Nexon, Venue, Brezza, Sonet |
| Mid-SUV / UV | 4.5m+ UV | ₹15–30L | Creta, Seltos, Hector |
| Full-size SUV | Premium UV | ₹25–60L | Fortuner, Endeavour, Tucson |
| Luxury sedan/SUV | Premium/imported | ₹40L+ | BMW 3 Series, GLE, XUV700 Adv |
| EV (dedicated platform) | Fuel = Electric | ₹10–50L | Nexon EV, Tata Curvv, MG ZS EV |
| MPV | Multi-purpose 6–8 seaters | ₹10–35L | Innova, Ertiga, Carens |

*Segment coding must be done from model names in wholesale data — map using a `model_segment_map.csv`.*

### 15.3 State-Level Segment Experiments

| Experiment | Method | Practical significance |
|---|---|---|
| **SEG-01**: Segment share by state, current year | 100% stacked bar, sorted by SUV share | Immediately identifies SUV-heavy vs hatchback-loyal states |
| **SEG-02**: Segment transition trajectory per state | Animated stacked area over 2012–2026 | Captures the speed of aspirational shift in each state |
| **SEG-03**: SUV penetration vs GSDP per capita | Scatter: SUV share (Y) × income (X) | Establishes income threshold for SUV tipping point |
| **SEG-04**: Hatchback dependency index | Share of hatchback in state's total PV sales | Identifies states where entry OEMs (Maruti) still dominate |
| **SEG-05**: Segment transition speed | Year-on-year SUV share gain per state | States climbing fastest = most fertile ground for compact SUV OEMs |
| **SEG-06**: State segmentation clustering | K-means on segment share vector (all states) | Groups states into archetypes: Entry, Transitioning, Aspiration, Premium |
| **SEG-07**: Urban vs rural segment proxy | Compare tier-1 city heavy states vs dispersed states | Tests whether urban concentration drives SUV share |
| **SEG-08**: Sedan collapse analysis | Track sedan share 2015–2026 by state | Sedans have been dying — find which states bucked the trend and why |
| **SEG-09**: EV segment entry pattern | Which segment (hatchback EV or SUV EV) is growing faster? | Informs whether EVs are a mass market or aspirational product in India |
| **SEG-10**: Model-level segment cannibalisation | Does Brezza eat Dzire share within Maruti? | Uses wholesale model × segment data to detect intra-OEM cannibalisation |
| **SEG-11**: Segment HHI over time | Herfindahl Index computed on segment shares, not OEM shares | Measures whether the market is becoming more diversified across segments |
| **SEG-12**: Premium segment index by state | Share of vehicles priced above ₹15L | Alternative income proxy; tracks luxury penetration geography |

### 15.4 State Archetypes (Suggested Typology)

After running SEG-06 clustering, states will broadly fall into these archetypes:

| Archetype | Defining traits | Example states |
|---|---|---|
| **Entry Market** | >60% hatchback, low income, low EV | Bihar, Jharkhand, Assam |
| **Transitioning** | Compact SUV rising fast, hatchback still 40–50% | Rajasthan, MP, Odisha |
| **Aspiration Majority** | Compact + mid SUV dominant, hatchback <35% | Gujarat, Haryana, Punjab |
| **Metro Premium** | Mid+full SUV strong, EV emerging, high income | Maharashtra, Karnataka, Delhi |
| **EV Pioneer** | EV penetration >5%, strong policy support | Delhi, Telangana, Goa |

**Practical significance for OEMs**: An OEM launching a compact SUV should prioritise Transitioning states. An OEM launching an EV should target EV Pioneer and Metro Premium states first. A hatchback OEM defending market share needs a clear strategy for Entry Markets being pressured by aspirational upgrades.

---

## 16. Practical Significance — Summary Framework

Every experiment in this system should have its practical significance written using a consistent 3-sentence format, structured as follows:

1. **The finding**: What the output shows in one sentence.
2. **Who cares**: Which stakeholder (OEM, dealer, investor, regulator, researcher) acts on this.
3. **The action**: What decision becomes easier, more accurate, or more timely as a result.

**Example (for SEG-03 — SUV penetration vs income)**:

*States with per-capita GSDP above approximately ₹2.5 lakh show SUV share crossing 50% — a reliable income-threshold tipping point. OEM product planners and investors assessing India market entry decisions care about this finding most directly. It makes the decision of when to launch a compact SUV in a new state systematic rather than intuition-driven.*

**Example (for TAX-02 — EV on-road price parity)**:

*In 2024, Delhi and Telangana are the only two large states where the on-road price of a Tata Nexon EV is lower than its petrol equivalent after road tax and subsidy are accounted for. EV OEMs prioritising their state-level marketing and charging infra investments will find this table directly actionable. It converts a policy landscape into a commercial priority map.*


---

## 17. PhD Research Experiments Portfolio (All Segments — v5.1)

This section integrates the full PhD application research portfolio into the app's experiment system. Every project is mapped to the Page Structure Template from Section 7.5 — with its data source, method, what to look for, practical significance, and complexity science framing.

### 17.1 Data Join Architecture

Understanding which dataset powers which experiment is the single most important constraint:

| Analysis type | Data available | What it enables |
|---|---|---|
| Fuel transition dynamics | Vahan only | EV / CNG / SHEV / petrol / diesel analysis |
| Segment dynamics | Wholesale only | Hatchback → SUV structural shift; OEM segment strategies |
| OEM channel dynamics | Both joined at OEM × State × Month | Wedge, nowcasting, competitive share |
| Geographic supply strategy | Wholesale only | Which states OEMs prioritise for dispatch |
| Technology adoption networks | Vahan only | Max entropy, Bass diffusion, HMM, diffusion on graph |
| Policy impact on adoption | Vahan + policy events | Event study, price elasticity |
| Infra-adoption coupling | Vahan + infra data | CNG/EV infra as diffusion accelerant |

**Critical constraint**: Wholesale has no fuel split — "Nexon" includes EV + Petrol + Diesel variants under one nameplate. Vahan has no model or segment information. The join at OEM × State × Month is fuel-agnostic and segment-agnostic.

---

### 17.2 Lead Research Paper — The SHEV Paper

**Experiment ID**: SHEV-01  
**Category**: Policy Network Analysis  
**Data**: Vahan 2012–2026 + policy timeline  
**Method**: Bass diffusion fitting per state; policy network construction (directed graph); panel regression (SHEV share as dependent variable, policy intensity as covariate)

**The finding**: Strong Hybrid Electric Vehicles (SHEVs) have failed to achieve meaningful adoption in India — below 1% market share across all states — despite being the most fuel-efficient non-EV technology available. They are ineligible for FAME subsidies, taxed at 28% GST, and structurally absent from the consumer incentive graph.

**Complexity science framing**: This is not a policy design failure alone — it is a story about structural isolation in a policy network. India's incentive architecture was designed around a binary (fossil ↔ electric). SHEVs occupy no node in the incentive graph. In complex adaptive systems, being absent from a network is equivalent to being isolated from the diffusion process. No adoption cascade can ignite from a node that does not exist.

**What to look for**:
- Bass S-curves flat for SHEV vs proper S-curve for CNG and EV
- Policy network diagram: SHEV appears as an isolated node with no incentive edges
- Panel regression: policy intensity coefficient is insignificant for SHEV, significant for EV and CNG

**Practical significance**: If the SHEV GST is cut from 28% to 5% (consistent with fuel-efficient vehicles), the simulation (Project E) predicts an immediate S-curve ignition. This is a direct policy recommendation quantifiable from the data. For OEMs like Toyota and Honda, SHEV's trapped position represents billions in stranded product investment.

**Sub-experiments within SHEV-01**:
- S-curve comparison: SHEV vs CNG vs BEV across top 10 states
- Policy network diagram with structural isolation visualised
- Panel regression table with policy coefficient
- Wholesale angle: Toyota and Honda dispatch volumes to states are flat and low relative to conventional model dispatch — consistent with near-zero SHEV registration

---

### 17.3 Vahan-Driven Experiments

#### Project A — Maximum Entropy Inference of India's EV Adoption Network

**Experiment ID**: NET-A01  
**Category**: Network Science — Advanced  
**Tier**: Tier 5 — Research Grade  
**Data**: Vahan 2012–2026 + per capita GSDP + EV charging density + policy timing

**The question**: Can we reconstruct the latent network structure governing EV adoption diffusion across Indian states from partial Vahan registration data — and does the inferred network predict future adoption trajectories better than standard panel models?

**Method (start to finish)**:
1. Build state × year EV adoption rate matrix from Vahan
2. Construct three network types: geographic adjacency (shared borders), economic similarity (cosine similarity of state feature vectors), and maximum entropy (BiCM/CReMa from NEMtropy — infer edge weights from observed co-adoption patterns under marginal constraints)
3. Run Bass-on-graph diffusion on all three networks
4. Compare forecasting accuracy: train 2013–2021, test 2022–2025

**Plain English**: We do not observe how states influence each other's EV adoption directly. We only see outcomes (registration counts). Maximum entropy asks: given what we observe, what is the most likely network connecting these states — without assuming more than the data tells us? It is like reconstructing a conversation from only the topics discussed, not the words.

**What to look for**:
- Maximum entropy network should outperform geographic and economic similarity benchmarks in forecasting accuracy
- Hub states (seed nodes for adoption cascades) — Maharashtra, Karnataka
- Structurally isolated states — those that need targeted policy, not spillover

**Practical significance**: This tells policy makers which states to seed first for maximum national EV adoption cascade effect. It also tells investors which states are likely to show EV adoption acceleration before the income data would predict.

**IMT fit**: Direct application of Squartini's NEMtropy methods. Potential co-authorship paper.

---

#### Project B — Fuel Regime Transitions: Markov Chains, Hidden States, Phase Detection

**Experiment ID**: TRANS-B01  
**Category**: Dynamical Systems — Hidden Markov Models  
**Tier**: Tier 4 — Temporal Analysis  
**Data**: Vahan 2012–2026 + GSDP per capita + EV charger count + CNG station count + fuel prices

**The question**: Which states have undergone genuine fuel regime transitions, which are in a transitional phase, and which remain fossil-locked?

**Method**:
1. Build 5-dimensional fuel-type share vector per state per year: [petrol%, diesel%, CNG%, EV%, SHEV%]
2. Markov chain analysis: discretise into fossil-dominant, CNG-transitioned, EV-emerging, multi-fuel; compute 14-year transition matrix
3. Hidden Markov Model (hmmlearn): fit latent energy regimes (K=2,3,4 — select via AIC/BIC); Viterbi algorithm produces "regime calendar" per state
4. Map transition dates to policy shocks (BS6 April 2020, FAME II March 2019, PM E-DRIVE 2024)
5. Cox proportional hazards: time-to-regime-transition as outcome; income, infra, fuel price, policy shock as covariates

**Plain English**: A Markov chain is a model of how a system jumps between states — like a board game where your next position depends only on where you are now, not where you have been. The Hidden Markov Model goes further: it infers the invisible game board from only the moves you can see.

**What to look for**:
- Distribution of time-to-transition: exponential = memoryless; heavy-tailed = path-dependent (complexity signature)
- Absorbing states in the Markov matrix — once a state enters EV-emerging, does it return to fossil-dominant?
- Regime calendar map: which states transitioned earliest, which are still transitioning in 2026?

**Practical significance**: Identifies fossil-locked states where OEMs should not yet invest in EV-only dealer training. Identifies CNG-transitioned states as natural candidates for EV transition support. Tells NBFC lenders where EV loan products will find early traction.

---

#### Project C — Fuel Price Elasticity of Fleet Composition

**Experiment ID**: ECON-C01  
**Category**: Panel Econometrics — Natural Experiment  
**Tier**: Tier 2 — Regression Analysis  
**Data**: Vahan 2012–2026 + PPAC state fuel prices + PNGRB CNG prices + EV infra + GSDP

**The question**: Indian state fuel prices vary by ₹10–15/L due to state VAT differences. Do high-fuel-price states show faster fleet recomposition toward fuel-efficient technologies?

**Method**:
1. Collect state-level monthly petrol/diesel/CNG prices from PPAC/PNGRB
2. Construct relative fuel price = state price / national average
3. Two-way fixed effects panel regression (state FE + year FE)
4. Instrument fuel prices using crude oil price × state VAT rate (IV strategy)
5. Threshold regression for non-linear price effects
6. Network extension: states with similar fuel price trajectories → fuel regime network

**Key formula**:

`Fuel_Type_Share(i,t) = β × FuelPriceDiff(i,t) + γ × EVInfra(i,t) + δ × CNGInfra(i,t) + θ × GSDP_PerCapita(i,t) + State_FE + Year_FE + ε`

**What to look for**:
- Is β for CNG share positive and significant? This confirms price-driven switching
- What is the threshold price differential at which switching accelerates?
- Placebo test on luxury vehicle share — should show no price sensitivity

**Practical significance**: Every ₹1/L rise in petrol relative to CNG shifts approximately X% of new buyers to CNG — a number this project quantifies for the first time at state level. OEMs can use this to forecast fuel-mix demand in each state as fuel prices evolve.

---

#### Project G — Finance Penetration as Adoption Amplifier

**Experiment ID**: ECON-G01  
**Category**: Panel Econometrics — Threshold Analysis  
**Tier**: Tier 2 — Regression Analysis  
**Data**: Vahan 2012–2026 + SIAM/FADA finance penetration + RBI credit data + GSDP + EV infra

**The question**: Does finance penetration act as a structural threshold for EV adoption — a binding constraint separate from income?

**Complexity science framing**: Finance infrastructure is a hidden layer of the adoption network. Below a threshold finance penetration level, even willing buyers cannot convert — a structural barrier invisible to income-only models.

**Method**:
1. Compile state-level finance penetration from SIAM, FADA, NBFC/bank annual reports
2. Panel regression: EV_Share(i,t) as function of FinPen, GSDP, EVInfra, FuelPrice + State_FE + Year_FE
3. Threshold regression: estimate τ* — the finance penetration level below which EV adoption is near zero
4. OEM captive finance analysis: do OEMs with captive finance arms achieve higher EV share in low-bank-penetration states?

**What to look for**:
- Is the finance penetration coefficient significant after controlling for income? If yes, credit access is a separate binding constraint
- Threshold τ* — which states are currently below it?
- Captive finance compensation effect: Tata Motors Finance vs states with weak bank presence

**Practical significance**: Identifies states where launching EV-specific loan products would unlock demand that income data alone would not predict. Direct input for NBFC product strategy.

---

#### Project I — State Policy as Natural Experiment: PESTEL Event Study at Scale

**Experiment ID**: POL-I01  
**Category**: Causal Inference — Difference-in-Differences  
**Tier**: Tier 2 — Statistical Analysis  
**Data**: Vahan 2012–2026 + 100+ state policy events database

**The question**: Can a curated database of 100+ state policy events, matched to Vahan monthly data, causally identify which policy types most effectively accelerate fuel technology adoption?

**Complexity science framing**: Policies propagate — a state enacting an EV subsidy exerts competitive pressure on adjacent states. Policy diffusion on the state network is a complexity phenomenon: the epidemiology of policy adoption.

**Method**:
1. Build PESTEL policy event database: each event coded with state, date, policy_type, vehicle_category, fuel_type, intensity, PESTEL_tag
2. Stacked Difference-in-Differences across all treatment events by policy category
3. Synthetic control for high-impact single-state events (Delhi EV policy 2020, Telangana 2023)
4. Survival model: time-to-policy-adoption as outcome; whether an adjacent state has already enacted the policy as key covariate → tests policy contagion on state adjacency network

**What to look for**:
- Average treatment effect per policy type: which policy category (subsidy vs tax waiver vs mandate) has the largest effect?
- Policy contagion: is the survival model coefficient on "adjacent state already adopted" positive and significant?
- Synthetic control: what would Delhi's EV adoption have been without the 2020 EV policy?

**Practical significance**: The first systematic evidence on which Indian state EV policy design works. If road tax waivers outperform subsidy disbursements per rupee of public expenditure, that is a direct policy recommendation with fiscal implications.

---

### 17.4 Combined Supply + Demand Experiments

#### Project D — OEM Competitive Dynamics: Wholesale vs Retail Market Position

**Experiment ID**: CHAN-D01  
**Category**: Supply Chain Analysis — Competitive Intelligence  
**Tier**: Tier 1 — Foundational  
**Data**: Wholesale (2011–2026) + Vahan (2012–2026) joined at OEM × State × Month

**The question**: For each OEM, in each state, each month — does its wholesale dispatch share match its retail registration share?

**Key derived metric — Market Position Gap (MPG)**:

`MPG = wholesale_share(oem,state,t) − retail_share(oem,state,t)`

- MPG > 0: OEM dispatching more than its retail share → inventory building, push strategy
- MPG < 0: OEM registering more than it dispatches → supply-constrained, high dealer throughput
- MPG ≈ 0: OEM in channel equilibrium

**Method**:
1. Compute MPG matrix: every OEM × State × Month, 2012–2026
2. Classify OEMs by rolling 12-month average MPG: Supply-push / Demand-constrained / Equilibrium / Volatile
3. State-level supply prioritisation heatmap: wholesale rank vs retail rank per state
4. Event study: how quickly does OEM wholesale adjust to demand shocks (festive season, COVID, BS6)?
5. OEM competition network: edge weight = correlation of state-wise MPG patterns; Louvain community detection

**What to look for**:
- Which OEMs are consistently supply-push (Maruti pre-2020)?
- Which states are systematically under-served despite demand?
- Wholesale response lag to Vahan demand signal — shorter lag = more responsive supply chain

**Practical significance**: The MPG matrix is a live competitive intelligence instrument. An OEM with a rising MPG in Maharashtra is building inventory — a signal of either overconfidence or an upcoming promotional push. For investors, a persistently negative MPG (demand > supply) is a production capacity bottleneck signal.

---

#### Project F — The Wholesale-Retail Wedge: Channel Inventory and Systemic Stress

**Experiment ID**: CHAN-F01  
**Category**: Supply Chain Analysis — Bullwhip Effect  
**Tier**: Tier 1 — Foundational  
**Data**: Wholesale + Vahan joined at OEM × State × Month

**The question**: Can the monthly wholesale-retail wedge serve as a real-time systemic stress indicator — signalling market disruptions before they appear in headline data?

**Key metric**:

`Wedge(state,t) = total_wholesale(state,t) − total_vahan(state,t)`

`Bullwhip(state) = Var(monthly wholesale change) / Var(monthly retail change)`

**Method**:
1. Compute monthly wedge: state-level and OEM × state-level
2. Identify stress events: rolling 3-month SD of wedge > 2σ of historical distribution
3. Map stress events to known shocks: BS6 phase-out (March–April 2020), COVID lockdown (April–June 2020), semiconductor shortage (2021–22), FAME II demand cliff (March 2024)
4. Bullwhip coefficient per state per year; OEM-level Bullwhip comparison
5. Granger causality: does cumulative wedge level Granger-cause next-month Vahan registrations at 1–3 month lags?

**What to look for**:
- BS6 period: expect massive positive wedge (BS4 inventory clearing)
- COVID: retail collapses, wholesale freezes simultaneously — wedge near zero
- Semiconductor shortage: wholesale constrained, retail draws down existing stock — negative wedge
- Which OEMs have highest Bullwhip (most amplified supply chains)?

**Practical significance**: A rising wedge ratio above 1.2 is a dealer inventory stress signal — dealers are holding more stock than they are selling. This is an early warning of either demand softness or OEM over-pushing. Published 2–3 months before SIAM's own aggregate statistics, this is a genuine information edge for subscribers of Vahan Intelligence.

---

#### Project J — Demand Nowcasting: Wholesale as Leading Indicator of Retail

**Experiment ID**: FORE-J01  
**Category**: Forecasting — Machine Learning  
**Tier**: Tier 3 — Intermediate Forecasting  
**Data**: Wholesale + Vahan joined at OEM × State × Month + fuel prices + policy dummies

**The question**: Can OEM × state wholesale volumes in month T forecast Vahan registrations in month T+1, T+2, T+3 with meaningful accuracy above naive baseline?

**Why this is practically valuable**: Vahan reporting lags by ~45 days. Wholesale data is known before Vahan is released. This is a real-time information advantage.

**Features at month T**:
- wholesale(oem, state, t), t-1, t-2
- cumulative_wedge(oem, state, t)
- vahan(oem, state, t-1) — lagged retail
- fuel_price(state, t)
- policy_dummy(state, t)
- month_of_year (seasonality)
- OEM fixed effect, state fixed effect

**Method**:
1. Baseline models: Naive (retail[t+1] = wholesale[t]), AR(1) on Vahan, OLS with lagged wholesale
2. ML models: LightGBM (non-linearity + seasonality + policy dummies), LSTM (12-month sequence)
3. Train 2012–2022, test 2023–2025; evaluate RMSE, MAPE per OEM and per state
4. SHAP values: decompose contribution of each feature to forecast accuracy
5. Forecastability breakdown: which OEMs and states are most/least predictable and why?

**What to look for**:
- Does LightGBM MAPE beat naive by more than 10%? If yes, wholesale is a genuine leading indicator
- SHAP: is the wholesale lag the dominant predictor or does the wedge level add independent information?
- Hypothesis: Tata EV is less forecastable than Maruti because FAME policy timing dominates retail, not wholesale

**Practical significance**: This is the most directly deployable project. It can be packaged as a premium feature in Vahan Intelligence: subscribers see a 30-day forward estimate of registrations by OEM and state before official data releases.

---

### 17.5 Wholesale-Driven Experiment

#### Project K — India's Structural Segment Shift: Hatchback to SUV as Complex Transition

**Experiment ID**: SEG-K01  
**Category**: Segment Dynamics — Complexity Science  
**Tier**: Tier 3 — Advanced Structural Analysis  
**Data**: Wholesale only (OEM × Model × Segment × State × Month, 2011–2026)

**The question**: Can the hatchback-to-SUV transition be characterised as a complex adaptive system phenomenon — with tipping points, OEM competitive cascades, and state-level heterogeneity?

**Why this is novel**: Segment transition analysis at this granularity has never been done for India. Vahan does not have segment information. This is a unique analytical opportunity available exclusively from the supply data.

**Complexity science framing**:
- **Threshold effects**: Once SUV share crosses ~30% in a state, hatchback decline accelerates — positive feedback loop
- **Competitive cascades**: Maruti's entry into compact SUV (Brezza, Fronx) normalised SUV ownership at a lower price point, triggering OEM segment repositioning cascades
- **State heterogeneity**: Rural states with poor roads adopted SUVs earlier; urban congested states stayed hatchback-dominant longer
- **OEM fitness landscape**: OEMs that were hatchback-only in 2011 faced existential transition — their wholesale evolution reveals who navigated successfully

**Method**:
1. Segment share matrix: `segment_share(seg, oem, state, t) = wholesale(seg, oem, state, t) / total_wholesale(oem, state, t)`
2. Tipping point detection: threshold regression `∆SUV_share(state,t) = α + β×SUV_share(state,t-1) + γ×(SUV_share > τ*) + controls + ε` — estimate τ* per state
3. OEM segment transition trajectories: classify OEMs as Early movers / Fast followers / Late adapters / Segment-locked
4. State-level segment adoption network: cosine similarity of segment share vectors; Louvain community detection; track 2011–2026
5. Granger causality: does OEM A's SUV share Granger-cause OEM B's share decline in same state?

**What to look for**:
- Do wealthier states have lower tipping thresholds (transition at lower SUV saturation)?
- Did first-mover advantage in segment transition persist for Hyundai?
- Does the state-level network homogenise (converging to similar segment mixes) or diverge over 15 years?

**Practical significance**: An OEM launching a compact SUV should prioritise Transitioning states (SUV share 20–40%, fast-growing). This is more precise than targeting states by income alone. The tipping point map gives a specific SUV share level at which OEM entry is most commercially rational.

---

### 17.6 Contextual Data Experiment

#### Project H — Dealer Distribution Networks: Market Access and Fleet Transition

**Experiment ID**: DIST-H01  
**Category**: Distribution Infrastructure Analysis  
**Tier**: Tier 2 — Regression Analysis  
**Data**: Wholesale + Vahan + dealer count (OEM × State × Year from FADA/OEM reports)

**The question**: Does dealer network coverage independently predict technology adoption trajectories? Are EV and CNG adoption deserts partly explained by dealer network deserts?

**Key metrics**:
- `wholesale_per_dealer(oem,state,t)` = supply efficiency
- `retail_per_dealer(oem,state,t)` = demand efficiency
- `dealer_wedge_per_outlet` = wholesale per dealer − retail per dealer

**Market Access Index (MAI)**: weighted combination of dealer density (outlets per million population), geographic coverage (outlets per 1000 km²), EV-certified dealer share, rural-urban dealer distribution.

**Method**:
1. Compile OEM × State × Year dealer count matrix from FADA reports
2. Compute dealer throughput metrics and MAI
3. Panel regression: Fuel_Share(i,t) = β₁×DealerDensity(i,t) + β₂×EVInfra(i,t) + β₃×FinPen(i,t) + β₄×GSDP_PC(i,t) + State_FE + Year_FE + ε
4. Test: does dealer density predict EV/CNG adoption independently of charging infrastructure?

**What to look for**:
- Is dealer density coefficient significant after controlling for EV chargers? If yes, dealer network is a separate infrastructure constraint
- Which states have a high MAI but low EV share — policy target states
- EV-certified dealer threshold: minimum certified dealer density before EV adoption self-sustains

**Practical significance**: If EV adoption deserts are partly dealer deserts (not just charger deserts), the policy implication changes: EV infra investment alone will not unlock these markets. OEM dealer certification mandates become the priority intervention.

---

### 17.7 Five Short Skill-Building Experiments

#### Short Project 1 — Fleet Technology Diversity Index (FTDI)

**Experiment ID**: ENT-SP01  
**Timeline**: 10–15 days  
**Data**: Vahan (fuel diversity) + Wholesale (segment diversity)

**Method**: Shannon entropy of fuel-type share per state per month from Vahan; parallel Segment Diversity Index from wholesale.

`FTDI(state,t) = −Σ share_fuel × log(share_fuel)`

**Output**: 4 choropleth maps (2015, 2019, 2022, 2025) of fuel diversity; time series of aggregate FTDI vs segment diversity index; test correlation between fuel diversification and segment diversification timing.

**Plain English**: Shannon entropy measures disorder. A state selling only petrol cars scores near zero entropy — very ordered. A state with a healthy mix of petrol, diesel, CNG, and EV scores higher — more diverse. We track whether India is becoming more or less diverse in its fuel choices.

**Practical significance**: High and rising FTDI = market in structural transition, high uncertainty for OEM planning. Low FTDI = stable, predictable market. A state's FTDI trajectory is an OEM's planning risk indicator.

---

#### Short Project 2 — Bass Diffusion S-Curves: Multi-Fuel Fitting

**Experiment ID**: DIFF-SP02  
**Timeline**: 10–15 days  
**Data**: Vahan only

**Method**: `f(t) = (p + q×F(t)) × (1 − F(t))` fitted per state per fuel using `scipy.optimize.curve_fit`. Produces p (innovation), q (imitation), M (market potential) per state.

**Output**: S-curves for top 10 states across EV, CNG, SHEV. Core visual for the SHEV paper — SHEV flatline vs CNG proper S-curve vs EV early-stage.

**Plain English**: The Bass model asks: how does a new product spread through a population? Some people adopt early because of advertising or curiosity (innovators). Most people adopt after seeing their neighbours do it (imitators). The S-curve shows this: slow start, rapid middle, plateau at saturation.

**Practical significance**: States where EV is still in the early flat portion of the S-curve are where OEM infrastructure investment now will pay off at scale in 3–5 years. States past the inflection point are already self-sustaining — they need less OEM support, more production capacity.

---

#### Short Project 3 — SIR on Graph: EV Contagion Simulation

**Experiment ID**: DIFF-SP03  
**Timeline**: 14–15 days  
**Data**: Vahan + India state adjacency graph

**Method**: SIR compartmental model on the state adjacency graph. S = non-EV states, I = actively adopting, R = saturated. Calibrate β (infection rate) and γ (recovery rate) on Vahan EV data. Animate the 2012–2026 spread.

**Plain English**: EV adoption spreading from Maharashtra to Karnataka to Tamil Nadu looks structurally like a disease spreading through a population where states that share borders are likely to "infect" each other through shared economic ties, OEM dealer networks, and aspirational spillover. The SIR model maps this spread mathematically.

**What to look for**: Which states are "superspreaders" (high centrality + early adoption)? Which states are structurally isolated and need targeted intervention rather than spillover?

**Practical significance**: Strongest possible interview demonstration piece for IMT Lucca. Identifies the 3 states where concentrated EV policy support would produce the fastest national-level cascade.

---

#### Short Project 4 — OEM Market Share Race: Wholesale vs Retail

**Experiment ID**: CHAN-SP04  
**Timeline**: 10–12 days  
**Data**: Wholesale + Vahan joined at OEM × State × Month

**Method**: Animated side-by-side bar chart race: wholesale dispatch share (left panel) vs retail registration share (right panel) for top 8 OEMs nationally, animated 2012–2026. OEM × State MPG heatmap for 2024. MPG time series with policy event annotations.

**Three OEM archetypes that will emerge**:
- **Consistent leaders**: High wholesale AND retail share (Maruti nationally)
- **Supply-heavy**: High wholesale, lower retail — inventory building
- **Demand-heavy**: Lower wholesale, higher retail — supply-constrained, selling out faster than restocking

**Practical significance**: The animated bar chart race is interview-ready in minutes. It demonstrates that you can transform 15 years of proprietary data into a legible, compelling competitive dynamics story for any audience — academic or industry. This is core to the Vahan Intelligence SaaS pitch.

---

#### Short Project 5 — Festive Season Supply Chain Timing

**Experiment ID**: SEAS-SP05  
**Timeline**: 12–14 days  
**Data**: Wholesale + Vahan joined at OEM × State × Month

**Method**: Seasonal decomposition (multiplicative, period=12) per OEM; cross-correlation analysis to measure supply lead time (how many months ahead wholesale peaks relative to retail); year-over-year lead time evolution per OEM; state-level lead time heatmap.

**Three patterns that emerge**:
- **Early pre-positioners**: Wholesale peaks August–September, 2–3 months before October–November retail spike (Maruti, Hyundai)
- **Late responders**: Wholesale peaks in October itself — reactive, likely run out of stock mid-festive season
- **Over-preppers**: Wholesale peaks in July–August but retail does not respond as strongly — post-festive inventory hangover

**Complexity science connection**: Cross-correlation of supply and demand signals is a version of information flow analysis — formally connected to Transfer Entropy and Granger causality. Supply-to-demand information transfer framing gives this a complexity science vocabulary that resonates directly with IMT's NETWORKS group.

**Practical significance**: Supply chain timing efficiency is something every OEM analyst cares about but has rarely been measured empirically at this granularity. An OEM with a consistently short lead time (supply pre-positions accurately) should show lower festive season stockouts and higher retail conversion.

---

### 17.8 Project E — The Synthesis Simulation: India's Fleet Transition 2012–2035

**Experiment ID**: SIM-E01  
**Category**: Agent-Based / Compartmental Simulation — Policy Scenarios  
**Tier**: Tier 5 — Research Grade (Build Last — Synthesises All Others)  
**Data**: Vahan + all contextual data + calibrated parameters from Projects A, B, C, G, I

**The question**: Can a calibrated compartmental model on India's state network reproduce the observed 2012–2026 dynamics and make credible forward projections to 2035 under different policy scenarios?

**Model architecture**: Each state s has a fleet composition vector F(s,t) = [Petrol(s,t), Diesel(s,t), CNG(s,t), EV(s,t), SHEV(s,t)]. Transition rate for EV is a function of infra density (logistic), fuel price differential, subsidy level, spillover from neighbouring states (network diffusion), income, and Bass-style imitation.

**Six policy scenarios**:

| Scenario | Key parameter change | 2035 insight |
|---|---|---|
| Baseline | Current trajectory continues | Reference case |
| FAME removal | PM E-DRIVE subsidy ends 2027 | How much does subsidy removal delay EV peak? |
| SHEV GST cut | GST reduced 28% → 5% | Can SHEV ignite an S-curve from a flat baseline? |
| Carbon tax | ₹5/L surcharge on petrol/diesel | Fuel price shock vs EV charger investment — which works faster? |
| CNG infra push | 10,000 new CNG stations by 2030 | Is India at risk of locking into CNG rather than going directly to EV? |
| Accelerated EV | Subsidy maintained + fast infra | What is the earliest national 30% EV share date? |

**Network surgery experiments**:
- Remove high-centrality states (Maharashtra, Karnataka): how much does delayed infra rollout here slow the rest of the network?
- Seed state experiments: if you could choose 3 states for concentrated EV support, which 3 produce the fastest national cascade?
- Threshold sensitivity: is the 2030 EV outcome robust or knife-edge?

**The interview showpiece**: Side-by-side animation — left panel = model simulation, right panel = actual Vahan data 2012–2026. Where the model diverges from reality (Maharashtra adopted faster than predicted, UP more diesel-locked than income suggests) — those divergences are the PhD research agenda.

**Feeds from**: Short Project 2 (Bass priors), Short Project 3 (SIR network), Project B (HMM regime parameters), Project A (max entropy edge weights), Project C (fuel price coefficient), Project I (policy shock timing).

**Target journals**: Applied Energy, Energy Policy, Journal of Cleaner Production, Physica A.

---

### 17.9 Full Experiment Registry

| Experiment ID | Name | Data | Tier | PhD fit | App priority |
|---|---|---|---|---|---|
| SHEV-01 | SHEV Structural Isolation | Vahan + policy | Research | Highest | P1 |
| NET-A01 | Max Entropy EV Network | Vahan + infra | Research | Highest | P3 |
| TRANS-B01 | HMM Fuel Regime Transitions | Vahan + infra | Advanced | Highest | P2 |
| ECON-C01 | Fuel Price Elasticity | Vahan + PPAC | Intermediate | High | P2 |
| CHAN-D01 | OEM MPG Competitive Dynamics | Both joined | Foundational | High | P2 |
| SIM-E01 | Fleet Transition Simulation | Vahan + all | Research | Highest | P3 |
| CHAN-F01 | Wholesale-Retail Wedge | Both joined | Foundational | High | P1 |
| ECON-G01 | Finance Penetration Threshold | Vahan + FinPen | Intermediate | High | P3 |
| DIST-H01 | Dealer Distribution Networks | Both + dealer | Intermediate | Medium | P3 |
| POL-I01 | PESTEL Policy Event Study | Vahan + policy DB | Intermediate | High | P2 |
| FORE-J01 | Demand Nowcasting | Both joined | Intermediate | Medium | P1 |
| SEG-K01 | Hatchback-to-SUV Transition | Wholesale only | Advanced | High | P2 |
| ENT-SP01 | Fleet Technology Diversity Index | Both | Foundational | Medium | P1 |
| DIFF-SP02 | Bass S-Curves Multi-Fuel | Vahan | Foundational | High | P1 |
| DIFF-SP03 | SIR EV Contagion on Graph | Vahan | Intermediate | Highest | P1 |
| CHAN-SP04 | OEM Share Race Animated | Both joined | Foundational | High | P1 |
| SEAS-SP05 | Festive Season Timing | Both joined | Foundational | High | P1 |


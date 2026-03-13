# Complexity Lab — Pillar 3C

> **Personal OS**: Blog → Automation → **Projects** → Research

Network science analysis of Indian passenger vehicle registration data. This is the most intellectually original project — and the direct foundation for original research papers.

**Key insight**: Your Vahan dataset (OEMs × models × states × months) is a rich bipartite network that no academic has structured the way you have. This is your moat.

## First Paper Target

> **"Structural Evolution of India's Passenger Vehicle Market: A Network Science Perspective Using VAHAN Registration Data (2015–2025)"**

- **Data**: Vahan registration dataset (unique access + extraction skills)
- **Method**: NetworkX temporal graphs, Louvain community detection, centrality evolution
- **Finding**: How BSVI transition, COVID, and EV policy shifted OEM-State network topology
- **Venue**: arXiv `physics.soc-ph` or `cs.SI` → Applied Network Science (Springer Open Access)

## Dataset Schema

```
data/
├── nodes/
│   ├── oems.csv          ← OEM node list (Maruti, Hyundai, Tata, ...)
│   ├── models.csv        ← Model node list with segment, fuel type
│   └── states.csv        ← State node list with region metadata
└── edges/
    └── registrations.csv ← Edge list: oem, state, month, year, count
```

**Edge schema** (`registrations.csv`):
```
oem_id, model_id, state_id, year, month, registrations, fuel_type, segment
```

## Analysis Toolkit

### Core: NetworkX

```python
import networkx as nx
import pandas as pd

# Build bipartite graph: OEM <-> State
G = nx.Graph()
G.add_nodes_from(oem_list, bipartite=0)
G.add_nodes_from(state_list, bipartite=1)
G.add_weighted_edges_from([(oem, state, registrations)])

# Key metrics
nx.degree_centrality(G)        # Which OEM dominates which states
nx.betweenness_centrality(G)   # Bridging nodes (e.g., CNG segment)
nx.community.louvain_communities(G)  # Market clusters
```

### Temporal Analysis: NetworkX-Temporal

```python
# Monthly time-series graph evolution
# Track: how did BSVI transition change network topology?
# Track: COVID impact on market concentration
# Track: EV policy effect on OEM-State connections
```

### Visualization: Gephi Export

```python
# Export to GEXF for Gephi visualization
nx.write_gexf(G, "vahan_market_network.gexf")
# In Gephi: Layout → ForceAtlas2 → Color by community
```

## Project Structure

```
complexity-lab/
├── data/
│   ├── nodes/
│   │   ├── oems.csv
│   │   ├── models.csv
│   │   └── states.csv
│   └── edges/
│       └── registrations.csv
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_network_construction.ipynb
│   ├── 03_centrality_analysis.ipynb
│   ├── 04_community_detection.ipynb
│   └── 05_temporal_evolution.ipynb
├── src/
│   ├── build_graph.py       ← Graph construction utilities
│   ├── metrics.py           ← Centrality and community metrics
│   ├── visualize.py         ← Gephi export and matplotlib plots
│   └── temporal.py          ← Time-series graph analysis
├── outputs/
│   ├── graphs/              ← GEXF files for Gephi
│   ├── figures/             ← Publication-quality figures
│   └── reports/             ← Intermediate analysis reports
├── papers/
│   └── paper-01/
│       ├── draft.md         ← Working paper draft
│       ├── abstract.md
│       └── references.bib
├── requirements.txt
└── README.md
```

## Research Questions

1. **Market structure**: Is India's PV market a hub-spoke network (Maruti dominates all states) or does it have regional clusters?
2. **Temporal shifts**: How did network topology change before/after BSVI transition (April 2020)?
3. **COVID effect**: Did market concentration increase or decrease during 2020-21?
4. **EV transition**: Which states are network bridging nodes for EV adoption?
5. **Segment dynamics**: Is the SUV boom a global shift or concentrated in specific state-OEM pairs?

## Dependencies

```
networkx >= 3.6
pandas
numpy
matplotlib
scipy
python-igraph  (for large graph algorithms)
gephi-toolkit  (for automated Gephi exports)
jupyter
```

## Part of the Four-Pillar System

```
Pillar 1: personal-blog
Pillar 2: social-automation
Pillar 3A: msil-work-tool
Pillar 3B: commercialize-analytics
Pillar 3C: complexity-lab (this repo) ← feeds directly into Pillar 4
Pillar 4:  research-platform
```

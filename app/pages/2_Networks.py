"""Networks: OEM–state bipartite structure, communities, temporal evolution."""

import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query

from complexity_lab.networks import build as nb
from complexity_lab.networks import metrics as nm

st.set_page_config(page_title="Networks", layout="wide")
st.title("OEM–State Network")

edges = query("SELECT * FROM oem_state_edges")
years = sorted(edges["year"].unique())
year = st.slider("Year", int(years[0]), int(years[-1]), int(years[-2]))
min_share = st.slider("Edge threshold (OEM share of state)", 0.0, 0.10, 0.005, 0.005, format="%.3f")

g = nb.share_weighted_graph(edges[edges["year"] == year], min_share=min_share)
comm = nm.communities(g)
cent = nm.centrality_table(g)

c1, c2, c3 = st.columns(3)
c1.metric("Nodes / edges", f"{g.number_of_nodes()} / {g.number_of_edges()}")
c2.metric("Louvain modularity", f"{comm.attrs['modularity']:.3f}")
c3.metric("Communities", comm.attrs["n_communities"])

pos = nx.spring_layout(g, weight="weight", seed=42, k=0.6)
edge_x, edge_y = [], []
for u, v in g.edges():
    edge_x += [pos[u][0], pos[v][0], None]
    edge_y += [pos[u][1], pos[v][1], None]
node_df = pd.DataFrame(
    {
        "node": list(g.nodes),
        "x": [pos[n][0] for n in g.nodes],
        "y": [pos[n][1] for n in g.nodes],
        "kind": [g.nodes[n].get("kind", "?") for n in g.nodes],
        "community": [comm.loc[n, "community"] for n in g.nodes],
        "strength": [cent.loc[n, "strength"] for n in g.nodes],
    }
)
fig = go.Figure()
fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=0.4, color="#bbb"), hoverinfo="none"))
for kind, symbol in [("oem", "square"), ("state", "circle")]:
    d = node_df[node_df["kind"] == kind]
    fig.add_trace(
        go.Scatter(
            x=d["x"], y=d["y"], mode="markers+text", text=d["node"], textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                symbol=symbol, size=8 + 40 * d["strength"] / max(node_df["strength"].max(), 1e-9),
                color=d["community"], colorscale="Portland", line=dict(width=1, color="#444"),
            ),
            name=kind, hovertext=d["node"],
        )
    )
fig.update_layout(height=620, showlegend=True, xaxis_visible=False, yaxis_visible=False,
                  margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Temporal evolution")
graphs = nb.temporal_graphs(edges)
evo = nm.temporal_metric_series(graphs).reset_index()
metric = st.selectbox("Metric", ["modularity", "density", "n_communities", "n_edges"])
st.line_chart(evo.set_index("period")[metric], height=280)

st.subheader("Centrality table")
st.dataframe(cent.head(25), use_container_width=True)

"""Network Lab: stable market-structure views, communities, and cross-links."""

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_app_shell, render_card, render_finding

from complexity_lab.networks import build as nb
from complexity_lab.networks import inference as ni
from complexity_lab.networks import metrics as nm

st.set_page_config(page_title="Network Lab | Complexity Lab", layout="wide")
page = render_app_shell(
    "Network Lab",
    section="Explain",
    description=(
        "Explore stable OEM-state structure, state similarity, inferred EV co-adoption, "
        "community membership, and the links that bridge communities."
    ),
    evidence="Derived",
    limitations=(
        "Observed OEM-state edges come from registrations; inferred EV links are statistical.",
        "Communities depend on edge definition and threshold and do not establish causality.",
        "Cross-community links are market bridges, not proof of information transmission.",
    ),
)
render_card("oem-state-network")

edges = query("SELECT * FROM oem_state_edges")
years = sorted(int(value) for value in edges["year"].unique())
latest = min(page.filters.year_end, page.cutoff.latest_complete_year)

control_a, control_b, control_c, control_d = st.columns([1.2, 1, 1, 1])
mode = control_a.selectbox(
    "Network mode",
    ["OEM-state (observed)", "State similarity (observed)", "EV co-adoption (inferred)"],
)
year = control_b.slider("Year", years[0], years[-1], latest)
compare_year = control_c.slider("Compare with", years[0], years[-1], max(years[0], year - 1))
min_share = control_d.slider(
    "Edge threshold",
    0.0,
    0.10,
    0.005,
    0.005,
    format="%.3f",
    help="Within-state OEM share for observed bipartite edges.",
)


def _shares(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(["state_code", "maker"], as_index=False)["regs"].sum()
    grouped["share"] = grouped["regs"] / grouped.groupby("state_code")["regs"].transform("sum")
    return grouped


@st.cache_data(ttl=3600)
def _coadoption_graph() -> nx.Graph:
    panel = query(
        """
        SELECT state_code, year, ev_share
        FROM experiment_state_year
        ORDER BY state_code, year
        """
    )
    wide = panel.pivot(index="year", columns="state_code", values="ev_share")
    return ni.coadoption_graph(wide, alpha=0.10, n_permutations=150)


selected_edges = edges[edges["year"] == year]
previous_edges = edges[edges["year"] == compare_year]

if mode == "OEM-state (observed)":
    graph = nb.share_weighted_graph(selected_edges, min_share=min_share)
    previous_graph = nb.share_weighted_graph(previous_edges, min_share=min_share)
elif mode == "State similarity (observed)":
    graph = nb.state_similarity_graph(selected_edges, min_similarity=max(0.5, 1 - min_share * 5))
    previous_graph = nb.state_similarity_graph(
        previous_edges, min_similarity=max(0.5, 1 - min_share * 5)
    )
    nx.set_node_attributes(graph, "state", "kind")
    nx.set_node_attributes(previous_graph, "state", "kind")
else:
    graph = _coadoption_graph()
    previous_graph = graph.copy()
    nx.set_node_attributes(graph, "state", "kind")
    nx.set_node_attributes(previous_graph, "state", "kind")

if graph.number_of_edges() == 0:
    st.warning("No edges survive this threshold. Lower the threshold.")
    st.stop()

membership = nm.communities(graph)
centrality = nm.centrality_table(graph)
summary = nm.community_summary(graph, membership)
cross_links = nm.cross_community_edges(graph, membership)
changes = nm.edge_changes(previous_graph, graph)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Nodes", graph.number_of_nodes())
k2.metric("Edges", graph.number_of_edges())
k3.metric("Communities", membership.attrs["n_communities"])
k4.metric("Modularity", f"{membership.attrs['modularity']:.3f}")
k5.metric("Cross-community links", len(cross_links))
render_finding(
    f"The {year} {mode.lower()} network resolves into "
    f"{membership.attrs['n_communities']} communities. "
    f"{len(cross_links)} edges bridge different communities; these links are listed below.",
    label="Network verdict",
)

tab_matrix, tab_structure, tab_communities, tab_compare, tab_robustness = st.tabs(
    ["Matrix", "Structural view", "Communities and cross-links", "Compare periods", "Robustness"]
)

with tab_matrix:
    if mode == "OEM-state (observed)":
        shares = _shares(selected_edges)
        top_oems = (
            shares.groupby("maker")["share"].sum().nlargest(18).index
        )
        matrix = shares[shares["maker"].isin(top_oems)].pivot_table(
            index="state_code",
            columns="maker",
            values="share",
            fill_value=0,
        )
        matrix = matrix.loc[matrix.max(axis=1).sort_values(ascending=False).index]
        fig = px.imshow(
            matrix,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            labels={"color": "state share"},
            title=f"State by OEM market-share matrix, {year}",
        )
        fig.update_layout(height=760)
        st.plotly_chart(fig, width="stretch")
    else:
        adjacency = nx.to_pandas_adjacency(graph, weight="weight")
        ordered_nodes = membership.sort_values("community").index
        adjacency = adjacency.reindex(index=ordered_nodes, columns=ordered_nodes, fill_value=0)
        fig = px.imshow(
            adjacency,
            aspect="auto",
            color_continuous_scale="Viridis",
            title=f"Adjacency matrix: {mode}, {year}",
        )
        fig.update_layout(height=720)
        st.plotly_chart(fig, width="stretch")

with tab_structure:
    all_nodes = sorted(graph.nodes)
    if mode == "OEM-state (observed)":
        oems = sorted(node for node in all_nodes if graph.nodes[node].get("kind") == "oem")
        states = sorted(node for node in all_nodes if graph.nodes[node].get("kind") == "state")
        positions = {
            **{
                node: (-1.0, index - (len(oems) - 1) / 2)
                for index, node in enumerate(oems)
            },
            **{
                node: (1.0, index - (len(states) - 1) / 2)
                for index, node in enumerate(states)
            },
        }
    else:
        positions = nx.circular_layout(sorted(graph.nodes))

    ego_options = ["All nodes", *sorted(graph.nodes)]
    ego = st.selectbox("Ego network", ego_options)
    visible_nodes = set(graph.nodes)
    if ego != "All nodes":
        visible_nodes = {ego, *graph.neighbors(ego)}
    visible = graph.subgraph(visible_nodes)

    figure = go.Figure()
    for source, target, attrs in visible.edges(data=True):
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        source_community = membership.loc[source, "community"]
        target_community = membership.loc[target, "community"]
        cross = source_community != target_community
        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={
                    "width": 0.5 + 8 * float(attrs.get("weight", 1.0)),
                    "color": "#E4572E" if cross else "rgba(120,120,120,.35)",
                    "dash": "dash" if cross else "solid",
                },
                hoverinfo="text",
                text=f"{source} ↔ {target}<br>weight={float(attrs.get('weight', 1.0)):.3f}",
                showlegend=False,
            )
        )
    nodes = pd.DataFrame(
        {
            "node": list(visible.nodes),
            "x": [positions[node][0] for node in visible.nodes],
            "y": [positions[node][1] for node in visible.nodes],
            "kind": [graph.nodes[node].get("kind", "state") for node in visible.nodes],
            "community": [membership.loc[node, "community"] for node in visible.nodes],
            "strength": [centrality.loc[node, "strength"] for node in visible.nodes],
        }
    )
    for kind, symbol in [("oem", "square"), ("state", "circle")]:
        subset = nodes[nodes["kind"] == kind]
        if subset.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=subset["x"],
                y=subset["y"],
                mode="markers+text",
                text=subset["node"],
                textposition="top center",
                marker={
                    "symbol": symbol,
                    "size": 10 + 22 * subset["strength"] / max(nodes["strength"].max(), 1e-9),
                    "color": subset["community"],
                    "colorscale": "Portland",
                    "line": {"width": 1, "color": "#444"},
                },
                name=kind,
            )
        )
    figure.update_layout(
        height=760,
        xaxis_visible=False,
        yaxis_visible=False,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
    )
    st.plotly_chart(figure, width="stretch")
    st.caption(
        "Node positions are deterministic across years. Orange dashed edges cross communities."
    )

with tab_communities:
    st.subheader("Community list")
    if mode == "OEM-state (observed)":
        display = summary.copy()
        display["cross_share"] = display["cross_share"].map(lambda value: f"{value:.1%}")
        st.dataframe(display, hide_index=True, width="stretch")
        st.download_button(
            "Download community list",
            summary.to_csv(index=False),
            file_name=f"network_communities_{year}.csv",
            mime="text/csv",
        )
    else:
        members = membership.reset_index().rename(columns={"index": "node"})
        st.dataframe(members.sort_values(["community", "node"]), hide_index=True, width="stretch")

    st.subheader("Cross-community links")
    if cross_links.empty:
        st.info("No edges cross the detected communities at this threshold.")
    else:
        st.dataframe(cross_links, hide_index=True, width="stretch")
        st.download_button(
            "Download cross-community links",
            cross_links.to_csv(index=False),
            file_name=f"network_cross_links_{year}.csv",
            mime="text/csv",
        )
        flow = nm.community_flow_matrix(graph, membership)
        st.plotly_chart(
            px.imshow(
                flow,
                text_auto=".2f",
                color_continuous_scale="Oranges",
                title="Cross-community link-weight matrix",
                labels={"x": "state community", "y": "OEM community", "color": "weight"},
            ),
            width="stretch",
        )

with tab_compare:
    births = int((changes["status"] == "born").sum())
    deaths = int((changes["status"] == "died").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Edge births", births, f"{compare_year} → {year}")
    c2.metric("Edge deaths", deaths, f"{compare_year} → {year}")
    c3.metric("Net edge change", graph.number_of_edges() - previous_graph.number_of_edges())
    st.dataframe(changes.head(50), hide_index=True, width="stretch")

with tab_robustness:
    thresholds = np.array([0.001, 0.0025, 0.005, 0.01, 0.02, 0.05, 0.08])
    rows = []
    if mode == "OEM-state (observed)":
        for threshold in thresholds:
            candidate = nb.share_weighted_graph(selected_edges, min_share=float(threshold))
            if candidate.number_of_edges() == 0:
                continue
            candidate_communities = nm.communities(candidate)
            rows.append(
                {
                    "threshold": threshold,
                    "nodes": candidate.number_of_nodes(),
                    "edges": candidate.number_of_edges(),
                    "communities": candidate_communities.attrs["n_communities"],
                    "modularity": candidate_communities.attrs["modularity"],
                }
            )
        sensitivity = pd.DataFrame(rows)
        st.plotly_chart(
            px.line(
                sensitivity,
                x="threshold",
                y=["communities", "modularity"],
                markers=True,
                title="Threshold sensitivity",
            ),
            width="stretch",
        )
        st.dataframe(sensitivity, hide_index=True, width="stretch")
    else:
        st.info(
            "Threshold robustness is defined directly for the observed OEM-state network. "
            "Inferred-network uncertainty is controlled by its permutation filter."
        )

st.subheader("Centrality")
st.dataframe(centrality.reset_index().head(30), hide_index=True, width="stretch")

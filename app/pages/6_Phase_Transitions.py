"""Phase Transitions: percolation of the OEM–state network, EV tipping/saturation
thresholds, fuel-regime Markov dynamics — interactive versions of experiments 005/006."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_card

from complexity_lab.complexity import transitions as tr

st.set_page_config(page_title="Phase Transitions", layout="wide")
st.title("Phase Transitions & Thresholds")

tab_perc, tab_tip, tab_regime, tab_hmm = st.tabs(
    ["Percolation", "EV tipping / saturation", "Fuel regimes (Markov)", "Fuel regimes (HMM)"]
)

edges = query("SELECT * FROM oem_state_edges")
max_year = int(edges["year"].max()) - 1

with tab_perc:
    render_card("phase-transitions")
    year = st.slider("Year", int(edges["year"].min()), max_year, max_year)
    lo, hi = st.select_slider(
        "Threshold sweep range (within-state share)",
        options=[0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5],
        value=(0.001, 0.5),
    )
    curve = tr.percolation_curve(
        edges[edges["year"] == year], thresholds=np.geomspace(lo, hi, 40)
    )
    tau_c = tr.critical_threshold(curve)

    c1, c2 = st.columns([2, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["threshold"], y=curve["giant_frac"],
                                 mode="lines+markers", name="giant component"))
        fig.add_trace(go.Scatter(x=curve["threshold"],
                                 y=curve["n_components"] / curve["n_components"].max(),
                                 mode="lines", name="components (scaled)", line={"dash": "dot"}))
        fig.add_vline(x=tau_c, line_dash="dash", line_color="#A4243B",
                      annotation_text=f"τ_c ≈ {tau_c:.1%}")
        fig.update_layout(xaxis_type="log", title=f"Percolation curve, {year}",
                          xaxis_title="edge threshold (share)", yaxis_title="giant fraction")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.metric("Critical threshold τ_c", f"{tau_c:.1%}")
        st.markdown(
            "The network holds together until edges below the **market-leader scale** "
            "are required — then it shatters. τ_c is the empirical *minimum viable "
            "presence* for participating in the national market structure."
        )

    taus = {int(y): tr.critical_threshold(tr.percolation_curve(g))
            for y, g in edges.groupby("year") if int(y) <= max_year}
    st.plotly_chart(
        px.line(pd.Series(taus).sort_index(), markers=True,
                title="τ_c by year — has the market's cohesion scale moved?",
                labels={"index": "year", "value": "τ_c"}).update_layout(showlegend=False),
        use_container_width=True,
    )

with tab_tip:
    render_card("ev-threshold")
    share_col = st.selectbox("Technology share", ["ev_share", "cng_share"])
    smooth = st.slider("Smoothing window (months)", 1, 9, 3, step=2)
    cutoff = st.select_slider("Use data through", options=["2023-12 (FAME era)", "latest"],
                              value="latest")
    mp = query(
        f"SELECT state_code, year, month, {share_col} FROM panel_state_month "
        "WHERE state_code <> 'ALL' ORDER BY state_code, year, month"
    )
    if cutoff.startswith("2023"):
        mp = mp[(mp["year"] < 2024)]
    tips = tr.tipping_summary(mp, share_col, smooth_window=smooth)
    if tips.empty:
        st.warning("No states reached the minimum share for scanning.")
    else:
        tips = tips[tips["sse_gain"].notna()]
        tips["verdict"] = np.where(tips["sse_gain"] < 0.1, "no clear threshold",
                                   np.where(tips["hinge_coef"] > 0, "tipping ↑", "saturation ↓"))
        c1, c2, c3 = st.columns(3)
        c1.metric("States scanned", len(tips))
        c2.metric("Tipping (accelerating)", int((tips["verdict"] == "tipping ↑").sum()))
        c3.metric("Saturating", int((tips["verdict"] == "saturation ↓").sum()))

        plot = tips.reset_index()
        plot["tau_pct"] = plot["tau"] * 100
        fig = px.scatter(plot, x="tau_pct", y="sse_gain", color="verdict",
                         text="state_code", size="max_share",
                         title="Threshold τ* per state — where growth changes regime",
                         labels={"tau_pct": "τ* (share %)", "sse_gain": "model gain vs linear"})
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)

        pick = st.selectbox("Inspect a state", sorted(plot["state_code"]))
        s = mp[mp["state_code"] == pick].reset_index(drop=True)
        s["smoothed"] = s[share_col].rolling(smooth, center=True, min_periods=1).mean()
        srow = tips.loc[pick]
        figs = px.line(s, y=["smoothed"], x=s.index,
                       title=f"{pick}: {share_col} (smoothed) — τ* = {srow['tau']:.2%}, "
                             f"{srow['verdict']}")
        figs.add_hline(y=srow["tau"], line_dash="dash", line_color="#A4243B")
        st.plotly_chart(figs, use_container_width=True)

with tab_regime:
    panel_year = query("SELECT * FROM panel_state_year WHERE state_code <> 'ALL'")
    regimes = tr.classify_regimes(panel_year[panel_year["year"] <= max_year])
    matrix = tr.regime_transition_matrix(regimes)
    absorbing = tr.absorbing_regimes(matrix, threshold=0.9)

    c1, c2 = st.columns([3, 2])
    with c1:
        order = regimes[regimes["year"] == max_year].sort_values("regime")["state_code"].tolist()
        cal = regimes.pivot_table(index="state_code", columns="year", values="regime",
                                  aggfunc="first").reindex(order)
        code = {"fossil_dominant": 0, "multi_fuel": 1, "cng_transitioned": 2, "ev_emerging": 3}
        fig = go.Figure(go.Heatmap(
            z=cal.replace(code).values, x=cal.columns, y=cal.index,
            colorscale=[[0, "#B8B8B8"], [0.33, "#86BBD8"], [0.66, "#758E4F"], [1, "#E4572E"]],
            colorbar={"tickvals": [0, 1, 2, 3],
                      "ticktext": ["fossil", "multi-fuel", "CNG", "EV-emerging"]},
        ))
        fig.update_layout(title="Regime calendar", height=700)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.plotly_chart(
            px.imshow(matrix.round(2), text_auto=True, color_continuous_scale="Blues",
                      title="P(next | current)"),
            use_container_width=True,
        )
        st.metric("Absorbing regimes (≥90% self)", ", ".join(absorbing) or "none")
        st.markdown(
            "**Reading**: an absorbing regime is a one-way door. If `ev_emerging` is "
            "not absorbing yet, states near the 5% EV line can still slip back — the "
            "transition has not ratcheted."
        )


with tab_hmm:
    render_card("fuel-regimes")
    st.caption(
        "Rule-free counterpart of the Markov tab: a hidden Markov model lets the data "
        "choose the regimes (BIC selects K), then Viterbi-decodes each state's era path."
    )

    @st.cache_data(ttl=3600, show_spinner="Fitting HMMs (K = 2..4, EM with restarts)...")
    def _fit_hmm():
        from complexity_lab.complexity.regimes import fit_fuel_regimes, transition_years

        p = query(
            "SELECT state_code, year, petrol_share, diesel_share, cng_share, ev_share, "
            "hybrid_share FROM panel_state_year "
            "WHERE year < (SELECT MAX(year) FROM panel_state_year) ORDER BY state_code, year"
        )
        res = fit_fuel_regimes(p)
        return (res["selection"], res["regime_means"], res["transition_matrix"],
                res["calendar"], transition_years(res["calendar"]))

    selection, means, tmat, cal, trans = _fit_hmm()
    best_k = int(selection["bic"].idxmin())
    c1, c2, c3 = st.columns(3)
    c1.metric("Regimes chosen by BIC", best_k)
    c2.metric("Stickiest persistence", f"{tmat.to_numpy().diagonal().max():.1%}")
    c3.metric("Modal switch year",
              int(trans["year"].mode().iloc[0]) if not trans.empty else "-")

    st.dataframe(means.round(3), use_container_width=True)
    pivot = cal.pivot(index="state_code", columns="year", values="regime")
    order = pivot.mean(axis=1).sort_values().index
    fig = px.imshow(pivot.loc[order], aspect="auto", color_continuous_scale="Viridis",
                    title="HMM regime calendar (Viterbi paths)")
    fig.update_layout(height=700, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(
        px.imshow(tmat.round(2), text_auto=True, color_continuous_scale="Blues",
                  title="Fitted transition matrix"),
        use_container_width=True,
    )

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
from common import query, render_app_shell, render_card

from complexity_lab.complexity import dynamics
from complexity_lab.complexity import transitions as tr

st.set_page_config(page_title="Transitions and Regimes | Complexity Lab", layout="wide")
page = render_app_shell(
    "Transitions and Regimes",
    section="Explain",
    description="Look for thresholds, early warnings, percolation, and latent fuel regimes.",
    evidence="Estimated",
    limitations=(
        "Thresholds and regimes are model-dependent summaries of observed histories.",
        "Early-warning indicators are diagnostics, not deterministic predictions.",
    ),
)

tab_perc, tab_tip, tab_regime, tab_hmm = st.tabs(
    ["Percolation", "EV tipping / saturation", "Fuel regimes (Markov)", "Fuel regimes (HMM)"]
)

edges = query("SELECT * FROM oem_state_edges")
max_year = min(page.filters.year_end, page.cutoff.latest_complete_year)

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
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.metric("Critical threshold τ_c", f"{tau_c:.1%}")
        st.markdown(
            "The network holds together until edges below the **market-leader scale** "
            "are required — then it shatters. τ_c is the empirical *minimum viable "
            "presence* for participating in the national market structure."
        )

    @st.cache_data(ttl=3600, show_spinner="Computing τ_c for every year…")
    def _tau_by_year(max_y: int) -> pd.Series:
        e = query("SELECT * FROM oem_state_edges")
        return pd.Series(
            {int(y): tr.critical_threshold(tr.percolation_curve(g))
             for y, g in e.groupby("year") if int(y) <= max_y}
        ).sort_index()

    st.plotly_chart(
        px.line(_tau_by_year(max_year), markers=True,
                title="τ_c by year — has the market's cohesion scale moved?",
                labels={"index": "year", "value": "τ_c"}).update_layout(showlegend=False),
        width="stretch",
    )

with tab_tip:
    render_card("ev-threshold")
    share_col = st.selectbox("Technology share", ["ev_share", "cng_share"])
    smooth = st.slider("Smoothing window (months)", 1, 9, 3, step=2)
    window_label = st.selectbox(
        "Structural-threshold window",
        [
            "Full history (2012+)",
            "FAME-II era (2019-04 to 2024-03)",
            "Recent adoption era (2022+)",
            "Current surge (2023+)",
        ],
        help=(
            "The hinge test is sensitive to the selected policy/adoption era. "
            "Full history remains the default; all windows are compared below."
        ),
    )
    mp = query(
        f"SELECT state_code, year, month, date, {share_col} FROM panel_state_month "
        "WHERE state_code <> 'ALL' ORDER BY state_code, year, month"
    )
    annual = query(
        f"SELECT state_code, year, {share_col} FROM panel_state_year "
        "WHERE state_code <> 'ALL' AND year <= "
        "(SELECT MAX(CAST(period AS INTEGER)) FROM data_period_status "
        " WHERE source = 'vahan' AND completeness_status = 'complete') "
        "ORDER BY state_code, year"
    )
    momentum = tr.recent_acceleration_summary(annual, share_col)
    latest_momentum_year = int(momentum["year"].max()) if not momentum.empty else None
    observed_accelerating = (
        int((momentum["momentum_verdict"] == "accelerating").sum())
        if not momentum.empty
        else 0
    )
    dates = pd.to_datetime(mp["date"])
    windows = {
        "Full history (2012+)": mp,
        "FAME-II era (2019-04 to 2024-03)": mp[
            (dates >= pd.Timestamp("2019-04-01"))
            & (dates <= pd.Timestamp("2024-03-01"))
        ],
        "Recent adoption era (2022+)": mp[dates >= pd.Timestamp("2022-01-01")],
        "Current surge (2023+)": mp[dates >= pd.Timestamp("2023-01-01")],
    }
    selected_mp = windows[window_label]
    tips = tr.tipping_summary(selected_mp, share_col, smooth_window=smooth)
    if tips.empty:
        st.warning("No states reached the minimum share for scanning.")
    else:
        tips = tips[tips["sse_gain"].notna()]
        tips["verdict"] = np.where(
            tips["sse_gain"] < 0.1,
            "no clear threshold",
            np.where(
                tips["hinge_coef"] > 0,
                "feedback threshold",
                "saturation threshold",
            ),
        )
        structural_tipping = int((tips["verdict"] == "feedback threshold").sum())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("States scanned", len(tips))
        c2.metric(
            f"Observed acceleration, {latest_momentum_year}",
            observed_accelerating,
            help="Latest annual share gain exceeded the prior year's gain by more than 0.1 pp.",
        )
        c3.metric(
            "Self-reinforcing thresholds",
            structural_tipping,
            help="Positive hinge and at least 10% SSE improvement over the linear model.",
        )
        c4.metric(
            "Saturation thresholds",
            int((tips["verdict"] == "saturation threshold").sum()),
        )
        st.info(
            f"These answer different questions. **{observed_accelerating} states show "
            f"observed calendar-time acceleration in {latest_momentum_year}**, while "
            f"**{structural_tipping} show a robust self-reinforcing share threshold** "
            "in the selected window. Acceleration does not automatically prove tipping."
        )

        window_rows = []
        for label, frame in windows.items():
            candidate = tr.tipping_summary(frame, share_col, smooth_window=smooth)
            valid = (
                candidate[candidate["sse_gain"].notna()]
                if not candidate.empty
                else candidate
            )
            window_rows.append(
                {
                    "window": label,
                    "states_scanned": len(valid),
                    "feedback_thresholds": (
                        int(
                            (
                                (valid["hinge_coef"] > 0)
                                & (valid["sse_gain"] >= 0.1)
                            ).sum()
                        )
                        if not valid.empty
                        else 0
                    ),
                    "saturation_thresholds": (
                        int(
                            (
                                (valid["hinge_coef"] < 0)
                                & (valid["sse_gain"] >= 0.1)
                            ).sum()
                        )
                        if not valid.empty
                        else 0
                    ),
                }
            )
        st.dataframe(pd.DataFrame(window_rows), hide_index=True, width="stretch")
        with st.expander("Observed latest-year momentum by state"):
            st.dataframe(
                momentum.sort_values("acceleration_pp", ascending=False).reset_index(),
                hide_index=True,
                width="stretch",
            )

        plot = tips.reset_index()
        plot["tau_pct"] = plot["tau"] * 100
        fig = px.scatter(plot, x="tau_pct", y="sse_gain", color="verdict",
                         text="state_code", size="max_share",
                         title="Threshold τ* per state — where growth changes regime",
                         labels={"tau_pct": "τ* (share %)", "sse_gain": "model gain vs linear"})
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, width="stretch")

        pick = st.selectbox("Inspect a state", sorted(plot["state_code"]))
        s = selected_mp[selected_mp["state_code"] == pick].reset_index(drop=True)
        s["smoothed"] = s[share_col].rolling(smooth, center=True, min_periods=1).mean()
        srow = tips.loc[pick]
        figs = px.line(s, y=["smoothed"], x="date",
                       title=f"{pick}: {share_col} (smoothed) — τ* = {srow['tau']:.2%}, "
                             f"{srow['verdict']}")
        figs.add_hline(y=srow["tau"], line_dash="dash", line_color="#A4243B")
        st.plotly_chart(figs, width="stretch")

        stability_rows = []
        for window_size in [1, 3, 5, 7, 9]:
            candidate = tr.tipping_summary(
                selected_mp,
                share_col,
                smooth_window=window_size,
            )
            if pick in candidate.index:
                stability_rows.append(
                    {
                        "smoothing_window": window_size,
                        "tau": candidate.loc[pick, "tau"],
                        "sse_gain": candidate.loc[pick, "sse_gain"],
                        "hinge_coef": candidate.loc[pick, "hinge_coef"],
                    }
                )
        stability = pd.DataFrame(stability_rows)
        if not stability.empty:
            tau_sd = stability["tau"].std()
            verdict = (
                "no credible transition"
                if srow["sse_gain"] < 0.1 or tau_sd > 0.03
                else "stable feedback threshold"
                if srow["hinge_coef"] > 0
                else "stable saturation transition"
            )
            st.info(
                f"Verdict: **{verdict}**. Threshold stability SD across smoothing "
                f"windows: {tau_sd:.2%}."
            )
            st.plotly_chart(
                px.line(
                    stability,
                    x="smoothing_window",
                    y="tau",
                    markers=True,
                    title="Threshold stability across smoothing windows",
                ),
                width="stretch",
            )

        warnings = dynamics.early_warning_signals(
            s.set_index(pd.to_datetime(s["date"]))[share_col],
            window=24,
        ).reset_index(names="date")
        variance_trend = dynamics.kendall_tau_trend(warnings["variance"])
        ac_trend = dynamics.kendall_tau_trend(warnings["autocorr1"])
        st.plotly_chart(
            px.line(
                warnings,
                x="date",
                y=["variance", "autocorr1"],
                title="Early-warning indicators (rolling detrended series)",
            ),
            width="stretch",
        )
        st.caption(
            f"Kendall trend: variance τ={variance_trend['tau']:.2f}; "
            f"lag-1 autocorrelation τ={ac_trend['tau']:.2f}. "
            "These are diagnostics, not deterministic predictions."
        )

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
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.plotly_chart(
            px.imshow(matrix.round(2), text_auto=True, color_continuous_scale="Blues",
                      title="P(next | current)"),
            width="stretch",
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

    st.dataframe(means.round(3), width="stretch")
    pivot = cal.pivot(index="state_code", columns="year", values="regime")
    order = pivot.mean(axis=1).sort_values().index
    fig = px.imshow(pivot.loc[order], aspect="auto", color_continuous_scale="Viridis",
                    title="HMM regime calendar (Viterbi paths)")
    fig.update_layout(height=700, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")
    st.plotly_chart(
        px.imshow(tmat.round(2), text_auto=True, color_continuous_scale="Blues",
                  title="Fitted transition matrix"),
        width="stretch",
    )

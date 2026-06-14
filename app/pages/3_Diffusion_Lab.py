"""Diffusion Lab: Bass fits per state + forward scenarios with policy levers."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_app_shell, render_card

from complexity_lab.simulation.diffusion import (
    bass_cumulative,
    fit_bass,
    prepare_adoption_series,
    project_bass,
)

st.set_page_config(page_title="Diffusion Lab | Complexity Lab", layout="wide")
page = render_app_shell(
    "Diffusion Lab",
    section="Explain",
    description="Fit and stress-test technology-adoption curves against observed state histories.",
    evidence="Estimated",
    limitations=(
        "Bass parameters are fitted descriptions, not structural causal estimates.",
        "Forward paths are scenarios and remain distinct from observations.",
    ),
)
render_card("ev-diffusion-states")
st.caption(
    "All post-onset data is used — the default trim only removes the pre-introduction "
    "zero months at the start (they tell the Bass model nothing) and the partial trailing "
    "months. Override everything below and run your own window experiments."
)

fuel = st.radio("Technology", ["EV", "CNG"], horizontal=True)
col = "ev_regs" if fuel == "EV" else "cng_regs"

panel = query(
    f"""SELECT state_code, state_name, year, month, date, {col} AS adopt
        FROM panel_state_month ORDER BY state_code, year, month"""
)
state_options = sorted(panel["state_name"].unique())
default_state = "All India"
if page.filters.states:
    match = panel.loc[
        panel["state_code"] == page.filters.states[0], "state_name"
    ].drop_duplicates()
    if not match.empty:
        default_state = match.iloc[0]
state = st.selectbox("State", state_options, index=state_options.index(default_state))
series = panel[panel["state_name"] == state].reset_index(drop=True)
data_min, data_max = int(series["year"].min()), int(series["year"].max())

st.subheader("Fit window — you choose what the model sees")
w1, w2, w3, w4 = st.columns([2, 1, 1, 1])
fit_y0, fit_y1 = w1.slider("Years entering the fit", data_min, data_max,
                           (data_min, data_max), key="fit_window")
auto_onset = w2.toggle("Auto onset trim", value=True,
                       help="Start the series at the first month with ≥ threshold cumulative "
                            "units. Off = fit from the window start, zeros included.")
onset_units = w3.slider("Onset threshold (units)", 0, 500, 50, 10,
                        disabled=not auto_onset)
drop_last = w4.slider("Drop trailing months", 0, 6, 2,
                      help="VAHAN's most recent months are partial. Applied only when the "
                           "window reaches the end of the data.")

window = series[series["year"].between(fit_y0, fit_y1)].reset_index(drop=True)
effective_drop = drop_last if fit_y1 >= data_max else 0
cum = prepare_adoption_series(
    window["adopt"], drop_last=effective_drop,
    onset_units=onset_units if auto_onset else 0.0,
)
if cum.empty or len(cum) < 8:
    st.warning(f"{state}: not enough {fuel} adoption inside this window to fit "
               "(widen the window or lower the onset threshold).")
    st.stop()
end_idx = len(window) - effective_drop
dates = window["date"].iloc[end_idx - len(cum): end_idx].reset_index(drop=True)
st.caption(f"Fitting on **{len(cum)} months**: {dates.iloc[0]:%b %Y} → {dates.iloc[-1]:%b %Y} "
           f"({int(cum.iloc[-1]):,} cumulative units).")

fit = fit_bass(cum)
m_at_bound = bool(np.isfinite(fit.get("m", np.nan)) and fit["m"] >= 0.95 * cum.iloc[-1] * 50)
from complexity_lab.viz import indian_axis, kpi_value  # noqa: E402

c1, c2, c3, c4 = st.columns(4)
c1.metric("p (innovation)", f"{fit['p']:.4f}" if pd.notna(fit["p"]) else "—",
          help="Spontaneous adoption rate per month — media, launches, intrinsic interest")
c2.metric("q (imitation)", f"{fit['q']:.3f}" if pd.notna(fit["q"]) else "—",
          help="Social-contagion rate — healthy consumer durables run ~0.3–0.5")
c3.metric("m (potential)", kpi_value(fit["m"]) if pd.notna(fit["m"]) else "—",
          "at bound — distrust" if m_at_bound else None,
          help="Eventual cumulative market the curve is heading toward")
c4.metric("R²", f"{fit['r2']:.4f}" if pd.notna(fit["r2"]) else "—")
if m_at_bound:
    st.warning(
        "The fitted market potential sits at the optimiser's bound: this S-curve hasn't "
        "bent yet, so m (and any projection) is an extrapolation, not an estimate."
    )

st.subheader("Scenario levers")
s1, s2, s3, s4 = st.columns(4)
q_mult = s1.slider("Imitation ×", 0.5, 2.0, 1.0, 0.05, help="Social contagion strength (visibility, word of mouth)")
p_mult = s2.slider("Innovation ×", 0.5, 3.0, 1.0, 0.05, help="Early-adopter pull (launches, incentives)")
m_mult = s3.slider("Market potential ×", 0.5, 3.0, 1.0, 0.1, help="Eventual addressable market (infra, price parity)")
horizon = s4.slider("Horizon (months)", 24, 120, 60, 12)

if pd.notna(fit["p"]):
    t_hist = np.arange(len(cum), dtype=float)
    proj = project_bass(fit, horizon=len(cum) + horizon, p_mult=p_mult, q_mult=q_mult, m_mult=m_mult)
    fitted = bass_cumulative(t_hist, fit["p"], fit["q"], fit["m"])
    future_dates = pd.date_range(dates.iloc[0], periods=len(proj), freq="MS")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=cum, name="Observed (cumulative)", mode="lines",
                             line={"width": 3}))
    fig.add_trace(go.Scatter(x=dates, y=fitted, name="Bass fit", mode="lines",
                             line={"dash": "dot"}))
    fig.add_trace(go.Scatter(x=future_dates, y=proj["cumulative"], name="Scenario",
                             mode="lines"))
    fig.add_vline(x=dates.iloc[-1], line_dash="dash", line_color="#888", opacity=0.5)
    fig.update_layout(height=440, yaxis_title=f"Cumulative {fuel} registrations",
                      title=f"{state}: observed vs fit vs scenario (levers reshape the whole curve)")
    indian_axis(fig)
    st.plotly_chart(fig, width="stretch")
else:
    st.warning("Could not fit Bass model for this series (too small / degenerate).")

st.subheader("Window sensitivity — how much do the parameters depend on your choice?")


@st.cache_data(ttl=3600, show_spinner="Refitting across start years…")
def _start_year_scan(state_name: str, value_col: str, drop: int, onset: float) -> pd.DataFrame:
    p = query(
        f"""SELECT year, month, date, {value_col} AS adopt FROM panel_state_month
            WHERE state_name = '{state_name.replace("'", "''")}'
            ORDER BY year, month"""
    )
    rows = []
    for sy in range(int(p["year"].min()), int(p["year"].max()) - 1):
        w = p[p["year"] >= sy].reset_index(drop=True)
        c = prepare_adoption_series(w["adopt"], drop_last=drop, onset_units=onset)
        if c.empty or len(c) < 8:
            continue
        f = fit_bass(c)
        if not np.isfinite(f.get("p", np.nan)):
            continue
        rows.append({
            "start_year": sy, "n_months": len(c), "p": f["p"], "q": f["q"], "m": f["m"],
            "r2": f["r2"], "m_at_bound": bool(f["m"] >= 0.95 * c.iloc[-1] * 50),
        })
    return pd.DataFrame(rows)


if st.toggle("Scan start years", value=False,
             help="Refit the model once per possible start year — see which conclusions "
                  "are robust to the window choice and which are artifacts of it."):
    scan = _start_year_scan(state, col, drop_last, onset_units if auto_onset else 0.0)
    if scan.empty:
        st.info("No fittable windows for this selection.")
    else:
        long = scan.melt(id_vars=["start_year", "m_at_bound"],
                         value_vars=["p", "q", "m"], var_name="param")
        figs = px.line(long, x="start_year", y="value", facet_col="param", markers=True,
                       facet_col_spacing=0.06,
                       title=f"{state}: fitted Bass parameters vs fit start year")
        figs.update_yaxes(matches=None, showticklabels=True)
        figs.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(figs, width="stretch")
        st.dataframe(scan.set_index("start_year").round(5), width="stretch")
        st.caption(
            "Reading: a flat stretch means the window barely matters there — the estimate is "
            "structural. Parameters that jump as zeros enter (early start years) are exactly "
            "the distortion the default onset trim removes. Hollow trust: any row with "
            "m_at_bound = True."
        )

st.subheader(f"Cross-state Bass parameters ({fuel})")


@st.cache_data(ttl=3600, show_spinner="Fitting all states…")
def _fit_all(value_col: str) -> pd.DataFrame:
    from complexity_lab.simulation.diffusion import fit_bass_by_state

    p = query(
        f"""SELECT state_code, year, month, {value_col}
            FROM panel_state_month WHERE state_code <> 'ALL'
            ORDER BY state_code, year, month"""
    )
    fits = fit_bass_by_state(p, value_col=value_col, min_total=1000).reset_index()
    names = query("SELECT state_code, state_name FROM dim_state")
    return fits.merge(names, on="state_code")

if st.toggle("Fit all states", value=False):
    fits = _fit_all(col)
    ok = fits.dropna(subset=["p", "q"])
    solid = ok[~ok["m_at_bound"]]
    st.caption(
        f"{len(ok)} states fit; {int(ok['m_at_bound'].sum())} have m at the bound "
        "(early-curve — shown hollow, their m is not interpretable)."
    )
    figp = px.scatter(
        solid, x="p", y="q", text="state_code", hover_name="state_name", size="m",
        title="Innovation (p) vs imitation (q) by state — size = market potential",
    )
    bound = ok[ok["m_at_bound"]]
    if not bound.empty:
        figp.add_scatter(x=bound["p"], y=bound["q"], mode="markers+text",
                         text=bound["state_code"], textposition="top center",
                         marker={"symbol": "circle-open", "size": 10, "color": "#999"},
                         name="m at bound")
    figp.update_traces(textposition="top center")
    st.plotly_chart(figp, width="stretch")
    st.dataframe(
        fits.set_index("state_code")[["state_name", "p", "q", "m", "m_at_bound",
                                      "r2", "peak_time", "n_months_fit"]].round(4),
        width="stretch",
    )

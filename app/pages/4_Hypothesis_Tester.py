"""Hypothesis Tester: pick panel variables -> correlations, FE regression, changepoints."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import query, render_card

from complexity_lab.analysis import econometrics

st.set_page_config(page_title="Hypothesis Tester", layout="wide")
st.title("Hypothesis Tester")
render_card("hypothesis-tester")
st.caption(
    "Quick interactive checks on the state×year panel. Covariates carry quality flags "
    "(see docs/data-dictionary.md) — treat 'approximate'/'estimate' series accordingly."
)

panel = query("SELECT * FROM panel_state_year WHERE state_code <> 'ALL'")
numeric_cols = [
    "total_regs", "ev_regs", "cng_regs", "ev_share", "cng_share", "yoy_growth",
    "hhi_oem", "entropy_oem", "n_oems", "pc_income_inr", "urban_pct",
    "cng_stations", "ev_chargers", "petrol_price_inr", "diesel_price_inr", "cng_price_inr",
]

tab_corr, tab_reg, tab_cp = st.tabs(["Correlations", "Panel regression", "Changepoints"])

with tab_corr:
    cols = st.multiselect("Variables", numeric_cols, default=["ev_share", "pc_income_inr", "urban_pct", "ev_chargers"])
    method = st.radio("Method", ["spearman", "pearson"], horizontal=True)
    if len(cols) >= 2:
        corr = econometrics.correlation_matrix(panel, cols, method=method)
        st.plotly_chart(
            px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1),
            use_container_width=True,
        )
        x, y = st.selectbox("x", cols, index=1), st.selectbox("y", cols, index=0)
        st.plotly_chart(
            px.scatter(panel.dropna(subset=[x, y]), x=x, y=y, color="zone" if "zone" in panel else None,
                       hover_name="state_name", trendline="ols", log_x=st.checkbox("log x")),
            use_container_width=True,
        )

with tab_reg:
    y = st.selectbox("Dependent variable", numeric_cols, index=numeric_cols.index("ev_share"))
    x = st.multiselect("Regressors", [c for c in numeric_cols if c != y], default=["pc_income_inr"])
    fe_entity = st.checkbox("State fixed effects", value=True)
    fe_time = st.checkbox("Year fixed effects", value=False)
    if x and st.button("Run regression"):
        try:
            res = econometrics.panel_ols(panel, y=y, x=x, entity_effects=fe_entity, time_effects=fe_time)
            coefs = pd.DataFrame({"coef": res.params, "se": res.bse, "p": res.pvalues})
            st.dataframe(coefs.loc[["const", *x]], use_container_width=True)
            st.caption(f"n = {int(res.nobs)}, R² = {res.rsquared:.3f} (cluster-robust SEs by state)")
        except Exception as e:  # noqa: BLE001 — surface modelling errors to the user
            st.error(f"Regression failed: {e}")

with tab_cp:
    month_panel = query("SELECT * FROM panel_state_month ORDER BY year, month")
    state = st.selectbox("State", sorted(month_panel["state_name"].unique()),
                         index=sorted(month_panel["state_name"].unique()).index("All India"))
    var = st.selectbox("Series", ["total_regs", "ev_share", "cng_share", "hhi_oem"])
    series = month_panel[month_panel["state_name"] == state].reset_index(drop=True)
    n_bkps = st.slider("Number of breakpoints", 1, 8, 3)
    s = series[var].astype(float)
    bkps = econometrics.changepoints(s, n_bkps=n_bkps)
    fig = px.line(series, x="date", y=var, title=f"{var} — {state}")
    for b in bkps:
        fig.add_vline(x=series.loc[b, "date"], line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Detected breaks at: {[str(series.loc[b, 'date'])[:7] for b in bkps]}")

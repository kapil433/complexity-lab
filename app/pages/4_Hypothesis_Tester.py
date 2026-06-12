"""Hypothesis Tester: pick panel variables -> correlations, FE regression, changepoints."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query, render_card, year_range_slider

from complexity_lab.analysis import econometrics

st.set_page_config(page_title="Hypothesis Tester", layout="wide")
st.title("Hypothesis Tester")
render_card("hypothesis-tester")
st.caption(
    "Quick interactive checks on the state×year panel. Reference variables are not "
    "equally available: nominal and constant-price income are annual, urbanization "
    "is Census 2011, chargers and CNG stations are sparse cross-sections, and fuel "
    "prices may use proxy fallbacks."
)

with st.expander("Reference-data availability", expanded=False):
    availability = query(
        """SELECT dataset, status, geography, time_coverage, temporal_type,
                  quality_summary, not_available
           FROM reference_availability
           WHERE dataset IN ('state_income', 'state_income_constant',
                             'state_road_length', 'state_personal_loans',
                             'urbanization', 'cng_stations',
                             'ev_charging', 'fuel_prices', 'population',
                             'road_tax', 'financing', 'dealer_counts')
           ORDER BY CASE status
                      WHEN 'usable' THEN 1 WHEN 'constrained' THEN 2 ELSE 3 END,
                    dataset"""
    )
    st.dataframe(availability, use_container_width=True, hide_index=True)
    st.caption(
        "Unavailable datasets are excluded from modelling controls. Constrained "
        "datasets require the period and quality shown above."
    )

panel = query("SELECT * FROM panel_state_year WHERE state_code <> 'ALL'")

# Wholesale covariates (local-only data): annual state dispatches + ws/retail ratio.
_tables = {r[0] for r in get_connection().execute("SHOW TABLES").fetchall()}
HAS_WS = "wholesale" in _tables
if HAS_WS:
    ws_year = query(
        """SELECT state_code, year, SUM(wholesale) AS wholesale_units
           FROM ws_state_month WHERE date >= '2022-04-01'
           GROUP BY state_code, year"""
    )
    panel = panel.merge(ws_year, on=["state_code", "year"], how="left")
    panel["ws_retail_ratio"] = panel["wholesale_units"] / panel["total_regs"]

numeric_cols = [
    "total_regs", "ev_regs", "cng_regs", "ev_share", "cng_share", "yoy_growth",
    "hhi_oem", "entropy_oem", "n_oems", "pc_income_inr",
    "pc_income_constant_2011_12_inr", "urban_pct",
    "cng_stations", "ev_chargers", "petrol_price_inr", "diesel_price_inr", "cng_price_inr",
    "regs_per_1000_capita",
]
if HAS_WS:
    numeric_cols += ["wholesale_units", "ws_retail_ratio"]

y0, y1 = year_range_slider(panel, key="ht_years")
panel = panel[panel["year"].between(y0, y1)]
st.caption(
    f"Period: {y0}–{y1} · {len(panel)} state-year observations"
    + (" · wholesale columns cover 2022+ (full-coverage era) only" if HAS_WS else "")
)

tab_corr, tab_reg, tab_cp = st.tabs(["Correlations", "Panel regression", "Changepoints"])

with tab_corr:
    cols = st.multiselect(
        "Variables",
        numeric_cols,
        default=[
            "ev_share",
            "pc_income_constant_2011_12_inr",
            "urban_pct",
            "ev_chargers",
        ],
    )
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
    x = st.multiselect(
        "Regressors",
        [c for c in numeric_cols if c != y],
        default=["pc_income_constant_2011_12_inr"],
    )
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

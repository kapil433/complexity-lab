"""Hypothesis Tester: pick panel variables -> correlations, FE regression, changepoints."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, query, render_app_shell, render_card

from complexity_lab.analysis import econometrics
from complexity_lab.persistence import save_research_item

st.set_page_config(page_title="Causal Lab | Complexity Lab", layout="wide")
page = render_app_shell(
    "Causal Lab",
    section="Explain",
    description="Interrogate correlations, panel regressions, and structural breaks with visible limits.",
    evidence="Derived",
    limitations=(
        "Correlation and fixed-effects regression do not automatically identify causal effects.",
        "Unavailable controls are excluded; constrained fields retain their caveats.",
    ),
)
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
           WHERE dataset IN ('state_income_constant',
                             'state_gsdp', 'state_population_annual',
                             'state_credit_depth', 'vehicle_lifetime_tax',
                             'policy_events_canonical',
                             'state_road_length', 'cng_stations',
                             'ev_charging', 'fuel_prices', 'known_data_gaps')
           ORDER BY CASE status
                      WHEN 'usable' THEN 1 WHEN 'constrained' THEN 2 ELSE 3 END,
                    dataset"""
    )
    st.dataframe(availability, width="stretch", hide_index=True)
    st.caption(
        "Unavailable datasets are excluded from modelling controls. Constrained "
        "datasets require the period and quality shown above."
    )

panel = query("SELECT * FROM experiment_state_year")

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
    "hhi_oem", "entropy_oem", "n_oems", "real_pc_income_inr", "urban_pct",
    "real_gsdp_lakh", "real_gsdp_growth_pct",
    "population_mn", "urban_population_mn", "rural_population_mn",
    "broad_credit_per_capita_inr", "broad_credit_growth_pct",
    "petrol_price_inr", "diesel_price_inr", "cng_price_inr",
    "regs_per_1000_population",
]
if HAS_WS:
    numeric_cols += ["wholesale_units", "ws_retail_ratio"]

y0, y1 = page.filters.year_start, page.filters.year_end
panel = panel[panel["year"].between(y0, y1)]
st.caption(
    f"Period: {y0}–{y1} · {len(panel)} state-year observations"
    + (" · wholesale columns cover 2022+ (full-coverage era) only" if HAS_WS else "")
)

st.subheader("Frame the hypothesis")
h1, h2, h3, h4 = st.columns(4)
hypothesis_outcome = h1.selectbox(
    "Outcome",
    ["ev_share", "cng_share", "total_regs", "yoy_growth"],
)
hypothesis_driver = h2.selectbox(
    "Primary driver",
    [
        "real_pc_income_inr",
        "urban_pct",
        "broad_credit_per_capita_inr",
        "petrol_price_inr",
        "cng_price_inr",
    ],
)
expected_sign = h3.selectbox("Expected sign", ["positive", "negative", "uncertain"])
identification = h4.selectbox(
    "Identification strategy",
    ["Descriptive association", "Two-way fixed effects", "First difference", "Event study / DiD"],
)
lag = st.slider("Driver lag (years)", 0, 3, 0)
if lag:
    panel[f"{hypothesis_driver}_lag{lag}"] = panel.groupby("state_code")[
        hypothesis_driver
    ].shift(lag)
    hypothesis_driver = f"{hypothesis_driver}_lag{lag}"
    numeric_cols.append(hypothesis_driver)

availability_preview = pd.DataFrame(
    [
        {
            "variable": variable,
            "non_missing": int(panel[variable].notna().sum()),
            "missing_pct": float(panel[variable].isna().mean()),
            "within_state_sd": float(
                panel.groupby("state_code")[variable].std().median(skipna=True)
            ),
        }
        for variable in [hypothesis_outcome, hypothesis_driver]
    ]
)
st.dataframe(
    availability_preview.style.format(
        {"missing_pct": "{:.1%}", "within_state_sd": "{:.4g}"}
    ),
    hide_index=True,
    width="stretch",
)

tab_corr, tab_reg, tab_cp = st.tabs(["Descriptive association", "Econometric model", "Changepoints"])

with tab_corr:
    cols = st.multiselect(
        "Variables",
        numeric_cols,
        default=[
            "ev_share",
            "real_pc_income_inr",
            "urban_pct",
            "broad_credit_per_capita_inr",
        ],
    )
    method = st.radio("Method", ["spearman", "pearson"], horizontal=True)
    if len(cols) >= 2:
        corr = econometrics.correlation_matrix(panel, cols, method=method)
        st.plotly_chart(
            px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1),
            width="stretch",
        )
        x, y = st.selectbox("x", cols, index=1), st.selectbox("y", cols, index=0)
        st.plotly_chart(
            px.scatter(panel.dropna(subset=[x, y]), x=x, y=y, color="zone" if "zone" in panel else None,
                       hover_name="state_name", trendline="ols", log_x=st.checkbox("log x")),
            width="stretch",
        )

with tab_reg:
    y = st.selectbox(
        "Dependent variable",
        numeric_cols,
        index=numeric_cols.index(hypothesis_outcome),
    )
    x = st.multiselect(
        "Regressors",
        [c for c in numeric_cols if c != y],
        default=[hypothesis_driver] if hypothesis_driver in numeric_cols else [],
    )
    fe_entity = st.checkbox("State fixed effects", value=True)
    fe_time = st.checkbox("Year fixed effects", value=True)
    if x and st.button("Run regression"):
        near_invariant = [
            variable
            for variable in x
            if panel.groupby("state_code")[variable].std().median(skipna=True) < 1e-9
        ]
        if fe_entity and near_invariant:
            st.warning(
                "Near-time-invariant under state fixed effects: "
                + ", ".join(near_invariant)
                + ". Coefficients may be weakly or not identified."
            )
        try:
            res = econometrics.panel_ols(panel, y=y, x=x, entity_effects=fe_entity, time_effects=fe_time)
            coefs = pd.DataFrame(
                {
                    "coef": res.params,
                    "se": res.bse,
                    "p": res.pvalues,
                    "ci_low": res.conf_int()[0],
                    "ci_high": res.conf_int()[1],
                }
            )
            selected_coefs = coefs.loc[[item for item in ["const", *x] if item in coefs.index]].copy()
            selected_coefs["effect_per_1sd"] = [
                selected_coefs.loc[index, "coef"]
                * (panel[index].std() if index in panel else 1)
                for index in selected_coefs.index
            ]
            selected_coefs["n"] = int(res.nobs)
            st.dataframe(selected_coefs, width="stretch")
            coefficient_plot = selected_coefs.drop(index="const", errors="ignore").reset_index(
                names="variable"
            )
            if not coefficient_plot.empty:
                fig_coef = px.scatter(
                    coefficient_plot,
                    x="coef",
                    y="variable",
                    error_x=coefficient_plot["ci_high"] - coefficient_plot["coef"],
                    error_x_minus=coefficient_plot["coef"] - coefficient_plot["ci_low"],
                    title="Coefficient estimates with 95% intervals",
                )
                fig_coef.add_vline(x=0, line_dash="dash")
                st.plotly_chart(fig_coef, width="stretch")
            identifying_variation = (
                "within-state changes over time, net of common year shocks"
                if fe_entity and fe_time
                else "within-state changes over time"
                if fe_entity
                else "pooled between-state and within-state variation"
            )
            st.info(
                f"Identifying variation: {identifying_variation}. "
                f"n={int(res.nobs)}, R²={res.rsquared:.3f}; cluster-robust SEs by state."
            )
            result_card = {
                "outcome": y,
                "regressors": x,
                "expected_sign": expected_sign,
                "identification": identifying_variation,
                "lag": lag,
                "n": int(res.nobs),
                "r_squared": float(res.rsquared),
                "coefficients": selected_coefs.reset_index(names="variable").to_dict("records"),
            }
            notes = st.text_area("Research-card notes", key="causal_notes")
            if st.button("Save hypothesis and result"):
                save_research_item(
                    "hypothesis",
                    title=f"{y} explained by {', '.join(x)}",
                    parameters={
                        "expected_sign": expected_sign,
                        "identification_strategy": identification,
                        "entity_effects": fe_entity,
                        "time_effects": fe_time,
                        "lag": lag,
                    },
                    result=result_card,
                    data_cutoff=page.cutoff.latest_period,
                    notes=notes,
                )
                st.success("Hypothesis card saved to Saved Questions.")
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
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Detected breaks at: {[str(series.loc[b, 'date'])[:7] for b in bkps]}")

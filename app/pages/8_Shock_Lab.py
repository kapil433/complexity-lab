"""Scenario and Shock Lab: calibrated presets, Monte Carlo, and saved comparisons."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import get_connection, render_app_shell, render_card

from complexity_lab.persistence import save_research_item
from complexity_lab.simulation.shocks import (
    ShockConfig,
    ShockWindow,
    run_shock_sim,
    shock_summary,
)
from complexity_lab.viz import indian_axis, kpi_value

st.set_page_config(page_title="Scenario and Shock Lab | Complexity Lab", layout="wide")
page = render_app_shell(
    "Scenario and Shock Lab",
    section="Anticipate",
    description=(
        "Calibrate the channel to observed registrations, replay historical signatures, "
        "run Monte Carlo uncertainty, compare scenarios, and save reproducible cards."
    ),
    evidence="Simulated",
    limitations=(
        "Every scenario output is simulated and visually separated from observations.",
        "Historical presets target directional signatures, not exact causal reconstruction.",
        "Wholesale has no fuel cut; calibration uses total channel volumes only.",
    ),
)
render_card("shock-lab")

PRESETS = {
    "Custom": {"d_mult": 0.5, "d_start": 24, "d_len": 3, "s_mult": 1.0, "s_start": 24, "s_len": 6},
    "COVID wave 1": {"d_mult": 0.15, "d_start": 24, "d_len": 3, "s_mult": 0.2, "s_start": 24, "s_len": 2},
    "Chip shortage": {"d_mult": 1.0, "d_start": 24, "d_len": 1, "s_mult": 0.70, "s_start": 24, "s_len": 12},
    "BS6 pre-buy and payback": {"d_mult": 1.30, "d_start": 22, "d_len": 2, "s_mult": 0.75, "s_start": 24, "s_len": 3},
    "Festive overbuild": {"d_mult": 1.20, "d_start": 24, "d_len": 2, "s_mult": 1.25, "s_start": 23, "s_len": 4},
    "Demand boom": {"d_mult": 1.35, "d_start": 24, "d_len": 9, "s_mult": 1.0, "s_start": 24, "s_len": 1},
}

observed = get_connection().execute(
    """
    SELECT date, total_regs
    FROM panel_state_month
    WHERE state_code = 'ALL'
      AND date <= MAKE_DATE(?, 12, 1)
    ORDER BY date
    """,
    [page.cutoff.latest_complete_year],
).df()
calibration_options = {
    "Latest complete 12 months": observed.tail(12),
    "Pre-COVID 2019": observed[pd.to_datetime(observed["date"]).dt.year == 2019],
    "Post-COVID 2023": observed[pd.to_datetime(observed["date"]).dt.year == 2023],
}

with st.sidebar:
    st.header("Scenario controls")
    preset_name = st.selectbox("Preset", list(PRESETS))
    calibration_name = st.selectbox("Calibration period", list(calibration_options))
    preset = PRESETS[preset_name]
    n_months = st.slider("Simulation months", 24, 120, 60)
    d_mult = st.slider("Demand multiplier", 0.0, 2.0, float(preset["d_mult"]), 0.05)
    d_start = st.slider("Demand shock start", 0, 100, int(preset["d_start"]))
    d_len = st.slider("Demand shock length", 1, 24, int(preset["d_len"]))
    s_mult = st.slider("Supply multiplier", 0.0, 1.5, float(preset["s_mult"]), 0.05)
    s_start = st.slider("Supply shock start", 0, 100, int(preset["s_start"]))
    s_len = st.slider("Supply shock length", 1, 24, int(preset["s_len"]))
    target_cover = st.slider("Target stock cover", 0.5, 3.0, 1.1, 0.1)
    adjustment_lag = st.slider("Production adjustment lag", 1.0, 12.0, 3.0, 0.5)

calibration = calibration_options[calibration_name]
base_demand = float(calibration["total_regs"].mean())
monthly_growth = float(
    observed.set_index(pd.to_datetime(observed["date"]))["total_regs"].pct_change(12).tail(12).mean()
    / 12
)
tables = {row[0] for row in get_connection().execute("SHOW TABLES").fetchall()}
observed_ratio = 1.0
if "retail_wholesale_month" in tables:
    ratio = get_connection().execute(
        """
        SELECT AVG(ws_retail_ratio)
        FROM retail_wholesale_month
        WHERE date >= '2022-04-01'
        """
    ).fetchone()[0]
    observed_ratio = float(ratio or 1.0)

cfg = ShockConfig(
    n_months=n_months,
    base_demand=base_demand,
    monthly_growth=monthly_growth,
    target_cover=target_cover,
    initial_inventory_cover=target_cover,
    adjustment_lag=adjustment_lag,
    demand_shocks=[ShockWindow(d_start, d_start + d_len, d_mult)] if d_mult != 1 else [],
    supply_shocks=[ShockWindow(s_start, s_start + s_len, s_mult)] if s_mult != 1 else [],
)
baseline_cfg = ShockConfig(
    n_months=n_months,
    base_demand=base_demand,
    monthly_growth=monthly_growth,
    target_cover=target_cover,
    initial_inventory_cover=target_cover,
    adjustment_lag=adjustment_lag,
)
baseline = run_shock_sim(baseline_cfg)
result = run_shock_sim(cfg)
summary = shock_summary(result, baseline)

st.caption(
    f"Calibration: {calibration_name}; mean demand {base_demand:,.0f} units/month; "
    f"observed full-era wholesale/retail ratio {observed_ratio:.2f}."
)
k = st.columns(5)
k[0].metric("Lost sales", kpi_value(summary["total_lost_sales"]))
k[1].metric("Retail gap", kpi_value(summary["retail_vs_baseline_gap"]))
k[2].metric("Peak inventory cover", summary["peak_inventory_cover"])
k[3].metric("Recovery month", summary["recovery_month"] or "Not recovered")
k[4].metric("Bullwhip ratio", summary["bullwhip_ratio"])

figure = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.4, 0.3, 0.3],
    subplot_titles=[
        "SIMULATED demand, retail, and production",
        "SIMULATED dealer inventory",
        "SIMULATED wholesale/retail ratio",
    ],
)
month = result["month"]
figure.add_scatter(x=month, y=result["demand"], name="simulated demand", line={"dash": "dot"}, row=1, col=1)
figure.add_scatter(x=month, y=result["retail"], name="simulated retail", row=1, col=1)
figure.add_scatter(x=month, y=result["production"], name="simulated production", row=1, col=1)
figure.add_scatter(
    x=month,
    y=baseline["retail"],
    name="simulated baseline",
    line={"dash": "dash"},
    opacity=0.5,
    row=1,
    col=1,
)
figure.add_scatter(x=month, y=result["inventory_cover_months"], name="inventory cover", row=2, col=1)
figure.add_scatter(x=month, y=result["ws_retail_ratio"], name="channel ratio", row=3, col=1)
for windows, color in [
    (cfg.demand_shocks, "rgba(31,119,180,0.12)"),
    (cfg.supply_shocks, "rgba(214,39,40,0.12)"),
]:
    for window in windows:
        for row in (1, 2, 3):
            figure.add_vrect(
                x0=window.start,
                x1=window.end,
                fillcolor=color,
                line_width=0,
                row=row,
                col=1,
            )
figure.update_layout(height=760, hovermode="x unified")
indian_axis(figure, max_value=float(result["demand"].max()))
st.plotly_chart(figure, width="stretch")

tab_history, tab_monte, tab_compare, tab_save = st.tabs(
    ["Observed signature", "Monte Carlo", "Compare presets", "Save scenario"]
)
with tab_history:
    history = observed.tail(60).copy()
    history["index_100"] = 100 * history["total_regs"] / history["total_regs"].iloc[0]
    st.plotly_chart(
        px.line(
            history,
            x="date",
            y="index_100",
            title="OBSERVED Vahan registration signature (index = 100)",
        ),
        width="stretch",
    )
    st.caption(
        "The observed series is shown separately. It is not overlaid as if the simulation were a forecast."
    )

with tab_monte:
    rng = np.random.default_rng(42)
    draws = []
    for _ in range(120):
        sampled_d_mult = max(0, rng.normal(d_mult, 0.08))
        sampled_s_mult = max(0, rng.normal(s_mult, 0.06))
        sampled_d_len = max(1, round(rng.normal(d_len, 1.5)))
        sampled_s_len = max(1, round(rng.normal(s_len, 2)))
        sampled = ShockConfig(
            **{
                **baseline_cfg.__dict__,
                "demand_shocks": [ShockWindow(d_start, d_start + sampled_d_len, sampled_d_mult)]
                if d_mult != 1
                else [],
                "supply_shocks": [ShockWindow(s_start, s_start + sampled_s_len, sampled_s_mult)]
                if s_mult != 1
                else [],
            }
        )
        draws.append(shock_summary(run_shock_sim(sampled), baseline))
    monte = pd.DataFrame(draws)
    st.dataframe(monte.describe(percentiles=[0.1, 0.5, 0.9]).T, width="stretch")
    st.plotly_chart(
        px.histogram(monte, x="retail_vs_baseline_gap", title="Monte Carlo retail-gap range"),
        width="stretch",
    )

with tab_compare:
    rows = []
    for name, preset_values in PRESETS.items():
        if name == "Custom":
            continue
        candidate = ShockConfig(
            **{
                **baseline_cfg.__dict__,
                "demand_shocks": [
                    ShockWindow(
                        preset_values["d_start"],
                        preset_values["d_start"] + preset_values["d_len"],
                        preset_values["d_mult"],
                    )
                ]
                if preset_values["d_mult"] != 1
                else [],
                "supply_shocks": [
                    ShockWindow(
                        preset_values["s_start"],
                        preset_values["s_start"] + preset_values["s_len"],
                        preset_values["s_mult"],
                    )
                ]
                if preset_values["s_mult"] != 1
                else [],
            }
        )
        rows.append({"scenario": name, **shock_summary(run_shock_sim(candidate), baseline)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

with tab_save:
    payload = {
        "preset": preset_name,
        "calibration_period": calibration_name,
        "base_demand": base_demand,
        "observed_channel_ratio": observed_ratio,
        "parameters": {
            "demand_multiplier": d_mult,
            "demand_start": d_start,
            "demand_length": d_len,
            "supply_multiplier": s_mult,
            "supply_start": s_start,
            "supply_length": s_len,
            "target_cover": target_cover,
            "adjustment_lag": adjustment_lag,
        },
        "summary": summary,
    }
    notes = st.text_area("Scenario notes")
    if st.button("Save scenario card"):
        save_research_item(
            "scenario",
            title=f"{preset_name} | {calibration_name}",
            parameters=payload["parameters"],
            result=payload,
            data_cutoff=page.cutoff.latest_period,
            notes=notes,
        )
        st.success("Scenario saved to Saved Questions.")
    st.download_button(
        "Download scenario card",
        json.dumps(payload, indent=2, default=str),
        file_name="scenario-card.json",
        mime="application/json",
    )

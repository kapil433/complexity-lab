"""Forecast Studio: benchmarked, vintage-aware forecasts with saved cards."""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import events_toggle_and_overlay, get_connection, query, render_app_shell, render_card

from complexity_lab.analysis.forecast import MODELS, benchmark
from complexity_lab.persistence import list_research_items, save_research_item
from complexity_lab.viz import indian_axis

st.set_page_config(page_title="Forecast Studio | Complexity Lab", layout="wide")
page = render_app_shell(
    "Forecast Studio",
    section="Anticipate",
    description=(
        "Forecast national, state, OEM, and observed Vahan-fuel registrations with "
        "rolling-origin model selection, interval checks, and saved vintages."
    ),
    evidence="Estimated",
    limitations=(
        "Forecasts are evaluated projections, not observed registrations.",
        "Wholesale forecasts are not fuel forecasts because wholesale has no fuel cut.",
        "Exogenous features are excluded unless their history covers the selected training period.",
    ),
)
render_card("forecast")

SERIES = {
    "Total registrations": None,
    "EV registrations": "EV",
    "CNG registrations": "CNG",
    "Petrol registrations": "Petrol",
    "Diesel registrations": "Diesel",
    "Strong Hybrid registrations": "Strong Hybrid",
}

with st.form("forecast_controls"):
    c1, c2, c3, c4, c5 = st.columns(5)
    scope = c1.selectbox("Scope", ["National", "State", "OEM"])
    series_label = c2.selectbox("Series", list(SERIES))
    horizon = c3.slider("Horizon", 1, 12, 6)
    n_origins = c4.slider("Backtest origins", 4, 16, 8)
    interval_target = c5.slider("Coverage target", 0.70, 0.99, 0.90, 0.01)

    states = query("SELECT state_code, state_name FROM dim_state ORDER BY state_name")
    makers = query(
        "SELECT DISTINCT maker FROM registrations WHERE state_code = 'ALL' ORDER BY maker"
    )["maker"].tolist()
    if scope == "State":
        default_state = page.filters.states[0] if page.filters.states else "MH"
        entity = st.selectbox(
            "State",
            states["state_code"],
            index=int((states["state_code"] == default_state).idxmax()),
            format_func=lambda code: states.set_index("state_code").loc[code, "state_name"],
        )
    elif scope == "OEM":
        default_oem = page.filters.oems[0] if page.filters.oems else "Maruti Suzuki"
        entity = st.selectbox(
            "OEM",
            makers,
            index=makers.index(default_oem) if default_oem in makers else 0,
        )
    else:
        entity = "ALL"
    submitted = st.form_submit_button("Run backtest and forecast", type="primary")

if not submitted and "forecast_result" not in st.session_state:
    st.info("Choose a scope and run the benchmark. Results can be saved as a forecast vintage.")
    st.stop()

fuel = SERIES[series_label]
complete_cutoff = pd.Timestamp(f"{page.cutoff.latest_complete_year}-12-01")
if scope in {"National", "State"}:
    state_code = "ALL" if scope == "National" else entity
    if fuel is None:
        frame = get_connection().execute(
            """
            SELECT date, total_regs AS y
            FROM panel_state_month
            WHERE state_code = ?
            ORDER BY date
            """,
            [state_code],
        ).df()
    else:
        frame = get_connection().execute(
            """
            SELECT MAKE_DATE(year, month, 1) AS date, SUM("count") AS y
            FROM registrations
            WHERE state_code = ? AND fuel = ?
            GROUP BY year, month
            ORDER BY date
            """,
            [state_code, fuel],
        ).df()
else:
    if fuel is None:
        frame = get_connection().execute(
            """
            SELECT MAKE_DATE(year, month, 1) AS date, SUM("count") AS y
            FROM registrations
            WHERE state_code = 'ALL' AND maker = ?
            GROUP BY year, month
            ORDER BY date
            """,
            [entity],
        ).df()
    else:
        frame = get_connection().execute(
            """
            SELECT MAKE_DATE(year, month, 1) AS date, SUM("count") AS y
            FROM registrations
            WHERE state_code = 'ALL' AND maker = ? AND fuel = ?
            GROUP BY year, month
            ORDER BY date
            """,
            [entity, fuel],
        ).df()

frame["date"] = pd.to_datetime(frame["date"])
training = frame[frame["date"] <= complete_cutoff]
series = pd.Series(
    training["y"].to_numpy(),
    index=pd.DatetimeIndex(training["date"]),
    name=series_label,
).asfreq("MS")
if series.dropna().shape[0] < 30:
    st.warning("This selection is too short for a meaningful rolling-origin forecast.")
    st.stop()

bench = benchmark(series, horizon=horizon, n_origins=n_origins)
best = bench.iloc[0]["model"]
forecast = MODELS[best](series, horizon)
result_payload = {
    "scope": scope,
    "entity": entity,
    "series": series_label,
    "training_cutoff": str(series.index.max().date()),
    "horizon": horizon,
    "champion": best,
    "metrics": bench.to_dict("records"),
    "forecast": forecast.reset_index(names="date").to_dict("records"),
}
st.session_state["forecast_result"] = result_payload

st.subheader("Model scorecard")
st.dataframe(
    bench.style.format(
        {
            "mape": "{:.1%}",
            "wape": "{:.1%}",
            "mae": "{:,.0f}",
            "bias": "{:+,.0f}",
            "interval_coverage": "{:.1%}",
            "naive_relative_skill": "{:+.1%}",
        }
    ),
    hide_index=True,
    width="stretch",
)
champion = bench.iloc[0]
if champion["model"] == "seasonal_naive" or champion["naive_relative_skill"] <= 0:
    st.warning("No complex model beat the seasonal-naive benchmark for this selection.")
else:
    st.success(
        f"{best} beat seasonal naive by {champion['naive_relative_skill']:.1%} on MAPE."
    )
if champion["interval_coverage"] < interval_target:
    st.warning(
        f"Historical interval coverage is {champion['interval_coverage']:.1%}, "
        f"below the selected {interval_target:.0%} target."
    )

figure = go.Figure()
history = series.tail(48)
figure.add_scatter(x=history.index, y=history.values, name="observed", line={"color": "#1f77b4"})
figure.add_scatter(
    x=forecast.index,
    y=forecast["mean"],
    name=f"{best} forecast",
    line={"color": "#d62728", "dash": "dot"},
)
figure.add_scatter(x=forecast.index, y=forecast["hi"], line={"width": 0}, showlegend=False)
figure.add_scatter(
    x=forecast.index,
    y=forecast["lo"],
    fill="tonexty",
    name="95% interval",
    line={"width": 0},
    fillcolor="rgba(214,39,40,0.15)",
)
figure.add_vline(
    x=series.index.max().timestamp() * 1000,
    line_dash="dash",
    annotation_text="training cutoff",
)
figure.update_layout(
    title=f"{scope}: {entity} | {series_label} | {horizon}-month forecast",
    hovermode="x unified",
    yaxis_title="registrations / month",
)
indian_axis(figure)
figure = events_toggle_and_overlay(figure)
st.plotly_chart(figure, width="stretch")

left, right = st.columns(2)
with left:
    st.dataframe(forecast.round(0), width="stretch")
    st.download_button(
        "Download forecast CSV",
        forecast.to_csv().encode(),
        f"forecast_{scope}_{entity}_{series_label}.csv",
    )
with right:
    notes = st.text_area("Forecast notes")
    if st.button("Save forecast vintage"):
        save_research_item(
            "forecast",
            title=f"{scope} {entity}: {series_label}",
            parameters={
                "scope": scope,
                "entity": entity,
                "series": series_label,
                "horizon": horizon,
                "n_origins": n_origins,
            },
            result=result_payload,
            data_cutoff=page.cutoff.latest_period,
            notes=notes,
        )
        st.success("Forecast vintage saved to Saved Questions.")
    st.download_button(
        "Download forecast card",
        json.dumps(result_payload, indent=2, default=str),
        file_name="forecast-card.json",
        mime="application/json",
    )

saved = list_research_items()
saved_forecasts = saved[saved["kind"] == "forecast"]
if not saved_forecasts.empty:
    with st.expander("Saved forecast vintages"):
        st.dataframe(
            saved_forecasts[["title", "data_cutoff", "created_at", "notes"]],
            hide_index=True,
            width="stretch",
        )

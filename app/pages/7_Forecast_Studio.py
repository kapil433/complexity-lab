"""Forecast Studio: benchmarked short-horizon forecasts with honest backtests."""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[1]))
from common import events_toggle_and_overlay, query, render_card

from complexity_lab.analysis.forecast import MODELS, benchmark

st.set_page_config(page_title="Forecast Studio", layout="wide")
st.title("Forecast Studio — benchmarked short-horizon forecasts")
render_card("forecast")

with st.form("forecast_controls"):
    c1, c2, c3, c4 = st.columns(4)
    states = query("SELECT DISTINCT state_code FROM panel_state_month ORDER BY state_code")
    state = c1.selectbox("State", states["state_code"], index=int((states["state_code"] == "ALL").idxmax()))
    series_name = c2.selectbox("Series", ["total_regs", "ev_regs", "cng_regs", "petrol_regs", "diesel_regs"])
    horizon = c3.slider("Horizon (months)", 1, 12, 6)
    n_origins = c4.slider("Backtest origins", 4, 16, 8)
    submitted = st.form_submit_button("Run backtest & forecast", type="primary")

if not submitted and "fs_last" not in st.session_state:
    st.info("Choose a series and press **Run backtest & forecast** — results stay cached, "
            "so repeat runs are instant.")
    st.stop()
st.session_state["fs_last"] = True

df = query(
    f"""SELECT date, {series_name} AS y FROM panel_state_month
        WHERE state_code = '{state}' ORDER BY date"""
)
# trim trailing partial months (VAHAN lag): drop the last 2 observations
series = pd.Series(
    df["y"].to_numpy()[:-2], index=pd.DatetimeIndex(df["date"]) [:-2], name=series_name
).asfreq("MS")

if series.dropna().shape[0] < 30:
    st.warning("Series too short for a meaningful backtest on this selection.")
    st.stop()


@st.cache_data(ttl=3600, show_spinner="Backtesting all models (rolling origins)…")
def _bench(state_: str, series_name_: str, horizon_: int, n_origins_: int) -> pd.DataFrame:
    d = query(
        f"""SELECT date, {series_name_} AS y FROM panel_state_month
            WHERE state_code = '{state_}' ORDER BY date"""
    )
    s = pd.Series(d["y"].to_numpy()[:-2], index=pd.DatetimeIndex(d["date"])[:-2]).asfreq("MS")
    return benchmark(s, horizon=horizon_, n_origins=n_origins_)


bench = _bench(state, series_name, horizon, n_origins)

st.subheader("Which model earns the right to forecast this series?")
cols = st.columns(len(bench))
for i, row in bench.iterrows():
    cols[i].metric(
        ("🏆 " if i == 0 else "") + row["model"],
        f"{row['mape']:.1%}" if pd.notna(row["mape"]) else "—",
        help=f"Mean MAPE over {row['n_origins']} rolling {horizon}-month backtests",
    )

best = bench.iloc[0]["model"]
fc = MODELS[best](series, horizon)

fig = go.Figure()
hist = series.tail(48)
fig.add_scatter(x=hist.index, y=hist.values, name="actual", line={"color": "#1f77b4"})
fig.add_scatter(x=fc.index, y=fc["mean"], name=f"{best} forecast",
                line={"color": "#d62728", "dash": "dot"})
fig.add_scatter(x=fc.index, y=fc["hi"], line={"width": 0}, showlegend=False)
fig.add_scatter(x=fc.index, y=fc["lo"], fill="tonexty", name="95% interval",
                line={"width": 0}, fillcolor="rgba(214,39,40,0.15)")
fig.update_layout(title=f"{state} · {series_name} — {horizon}-month forecast ({best})",
                  margin={"t": 50}, hovermode="x unified")
fig = events_toggle_and_overlay(fig)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Forecast table & download"):
    out = fc.round(0)
    st.dataframe(out, use_container_width=True)
    st.download_button("Download CSV", out.to_csv().encode(), f"forecast_{state}_{series_name}.csv")

st.caption(
    "The last 2 months of VAHAN data are dropped before fitting (reporting lag makes them "
    "partial). The champion model is chosen by rolling-origin backtest MAPE — not by looks."
)

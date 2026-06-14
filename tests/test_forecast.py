import numpy as np
import pandas as pd

from complexity_lab.analysis.forecast import MODELS, backtest, benchmark, seasonal_naive


def _seasonal_series(n=72, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    season = 1 + 0.25 * np.sin(2 * np.pi * (t % 12) / 12)
    y = 1000 * (1.004**t) * season * rng.normal(1, 0.03, n)
    return pd.Series(y, index=pd.date_range("2018-01-01", periods=n, freq="MS"))


def test_seasonal_naive_shape_and_band():
    s = _seasonal_series()
    fc = seasonal_naive(s, horizon=6)
    assert len(fc) == 6
    assert (fc["hi"] >= fc["mean"]).all() and (fc["lo"] <= fc["mean"]).all()
    assert (fc[["mean", "lo", "hi"]] >= 0).all().all()
    # next-Jan forecast should be near last-Jan value scaled by drift
    assert abs(fc["mean"].iloc[0] / s.iloc[-12] - 1) < 0.25


def test_all_models_run_and_backtest_scores():
    s = _seasonal_series()
    for name in MODELS:
        res = backtest(s, name, horizon=3, n_origins=4)
        assert res["n_origins"] >= 3, name
        assert np.isfinite(res["mape"]), name
        assert res["mape"] < 0.25, f"{name} mape {res['mape']}"


def test_benchmark_ranks_models():
    s = _seasonal_series()
    table = benchmark(s, horizon=3, n_origins=4)
    assert {
        "model",
        "mape",
        "wape",
        "mae",
        "bias",
        "interval_coverage",
        "naive_relative_skill",
        "n_origins",
    } == set(table.columns)
    assert table["mape"].is_monotonic_increasing
    assert len(table) == len(MODELS)

import numpy as np
import pandas as pd
import pytest

from complexity_lab.analysis import descriptive, distributions


def test_hhi_uniform_shares():
    # 4 equal players -> HHI = 4 * (0.25^2) * 10000 = 2500
    assert descriptive.hhi(pd.Series([0.25] * 4)) == pytest.approx(2500)


def test_hhi_monopoly():
    assert descriptive.hhi(pd.Series([1.0])) == pytest.approx(10000)


def test_entropy_uniform_is_log_n():
    h = descriptive.shannon_entropy(pd.Series([0.25] * 4))
    assert h == pytest.approx(np.log(4))
    assert descriptive.shannon_entropy(pd.Series([0.25] * 4), normalize=True) == pytest.approx(1.0)


def test_cagr_doubling():
    s = pd.Series([100, 0, 0, 0, 0, 200], dtype=float).replace(0, np.nan).dropna()
    # 100 -> 200 over 1 step in the dropna'd series: cagr computed on remaining points
    s = pd.Series([100.0, 200.0])
    assert descriptive.cagr(s) == pytest.approx(1.0)


def test_seasonality_profile_flat_series():
    rows = [
        {"year": y, "month": m, "total_regs": 100}
        for y in (2020, 2021)
        for m in range(1, 13)
    ]
    prof = descriptive.seasonality_profile(pd.DataFrame(rows))
    assert prof["seasonal_index"].min() == pytest.approx(1.0)
    assert prof["seasonal_index"].max() == pytest.approx(1.0)


def test_gini_extremes():
    assert distributions.gini(np.array([1.0, 1.0, 1.0, 1.0])) == pytest.approx(0.0, abs=1e-9)
    g = distributions.gini(np.array([0.0, 0.0, 0.0, 100.0]))
    assert g == pytest.approx(0.75, abs=1e-9)


def test_zipf_exponent_on_zipfian_data():
    sizes = pd.Series([1000 / r for r in range(1, 51)])
    fit = distributions.zipf_exponent(sizes)
    assert fit["slope"] == pytest.approx(-1.0, abs=0.01)
    assert fit["r2"] > 0.999


def test_concentration_series_two_periods():
    df = pd.DataFrame(
        {
            "year": [2020, 2020, 2021, 2021],
            "maker": ["A", "B", "A", "B"],
            "regs": [50, 50, 90, 10],
        }
    )
    out = descriptive.concentration_series(df, "year", "maker")
    assert out.loc[2020, "hhi"] == pytest.approx(5000)
    assert out.loc[2021, "hhi"] == pytest.approx(8200)
    assert out.loc[2021, "entropy"] < out.loc[2020, "entropy"]

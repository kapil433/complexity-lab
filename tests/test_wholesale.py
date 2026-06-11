import numpy as np
import pandas as pd
import pytest

from complexity_lab.analysis.nowcast import cross_correlation, nowcast_eval
from complexity_lab.data.wholesale import excel_serial_to_date, normalize_maker


def test_excel_serial_to_date():
    assert str(excel_serial_to_date(42826)) == "2017-04-01"
    assert str(excel_serial_to_date(46113)) == "2026-04-01"


@pytest.mark.parametrize(
    ("raw", "maker", "channel", "vahan"),
    [
        ("ARENA", "Maruti Suzuki", "Arena", "Maruti Suzuki"),
        ("NEXA", "Maruti Suzuki", "Nexa", "Maruti Suzuki"),
        ("Nexa", "Maruti Suzuki", "Nexa", "Maruti Suzuki"),
        ("TATA", "Tata Motors", None, "Tata Motors"),
        ("tata", "Tata Motors", None, "Tata Motors"),
        ("skoda", "Skoda", None, "Volkswagen Group"),
        ("PCA", "Citroen", None, "Stellantis"),
        ("GM", "Chevy", None, "Chevy"),
        ("UNKNOWN BRAND", "Others", None, "Others"),
    ],
)
def test_normalize_maker(raw, maker, channel, vahan):
    assert normalize_maker(raw) == (maker, channel, vahan)


def test_cross_correlation_detects_lead():
    rng = np.random.default_rng(0)
    leader = pd.Series(rng.normal(size=120)).cumsum() + 100
    follower = leader.shift(2) + rng.normal(scale=0.1, size=120)  # b leads a by 2
    xc = cross_correlation(follower, leader, max_lag=4, on_growth=False)
    assert xc["corr"].idxmax() == 2


def test_nowcast_eval_beats_baseline_when_wholesale_informative():
    rng = np.random.default_rng(1)
    n = 60
    dates = pd.date_range("2020-01-01", periods=n, freq="MS")
    season = 1 + 0.2 * np.sin(2 * np.pi * (np.arange(n) % 12) / 12)
    shock = rng.normal(1, 0.15, size=n)  # demand shocks visible in wholesale
    retail = 1000 * season * shock
    wholesale = retail * rng.normal(1.05, 0.02, size=n)  # wholesale tracks retail closely
    rw = pd.DataFrame(
        {"date": dates, "year": dates.year, "month": dates.month,
         "retail": retail, "wholesale": wholesale}
    )
    res = nowcast_eval(rw, test_months=12)
    assert res["n_oos"] == 12
    assert res["mape_nowcast"] < res["mape_baseline"]
    assert res["mape_nowcast"] < 0.10

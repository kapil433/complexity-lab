import pandas as pd

from complexity_lab.analysis.segments import classify_movers


def test_classify_movers():
    rows = []
    # early: crosses 50% in 2022; follower: 2025; locked: never, low share
    for maker, shares in {
        "Early": [0.55, 0.6, 0.65, 0.7],
        "Follower": [0.3, 0.4, 0.45, 0.55],
        "Locked": [0.15, 0.18, 0.2, 0.22],
    }.items():
        for year, s in zip(range(2022, 2026), shares, strict=True):
            rows.append({"maker": maker, "year": year, "suv_share": s, "units": 50000})
    traj = pd.DataFrame(rows)
    out = classify_movers(traj)
    assert out.loc["Early", "class"] == "early mover"
    assert out.loc["Follower", "class"] == "fast follower"
    assert out.loc["Locked", "class"] == "segment-locked"
    assert out.loc["Early", "crossed_year"] == 2022

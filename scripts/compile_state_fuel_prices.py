"""Compile state-wise annual-average fuel prices for data/reference/fuel_prices.csv.

Method
------
PPAC publishes daily RSPs only for the four metros (since 16.6.2017); full
state-capital tables appear in PPAC-sourced trackers and parliamentary
annexures as point-in-time snapshots. We therefore anchor each state's *level*
to capital-city RSP snapshots and apply the state-vs-Delhi differential to the
existing Delhi annual-average series (post-deregulation price *movements* are
near-identical across states; *levels* differ by state VAT).

Anchors (saved under data/raw/ppac/):
- Petrol/Diesel 2019-01-18  — BankBazaar city RSP table (Wayback 20190118)   -> years 2017-2019
- Petrol/Diesel 2021-03-07/08 — BankBazaar city RSP table (Wayback 202103xx) -> years 2020-2021
- Petrol/Diesel 2025-02-20  — factodata.com state-capital list               -> years 2022-2026
- CNG 2019-03 / 2021-03 / 2024-01 — goodreturns.in city CNG tables (Wayback)
  -> years 2017-2019 / 2020-2021 / 2022-2026

State capital convention: Haryana and Punjab share Chandigarh (UT VAT applies
there, NOT the states' own VAT — Punjab in-state pump prices run ~Rs 3/litre
higher); Gujarat uses Ahmedabad (Gandhinagar adjacent); Andhra uses Guntur
(adjacent to Amaravati); J&K uses Srinagar. CNG uses a representative
city-gas city where the capital has no CNG (UP: Meerut'21/Noida'24;
HR: Sonipat'21/Gurgaon'24; MP: Dewas).

Output: prints rows in fuel_prices.csv format (state_code,year,fuel,
price_avg_inr,source,quality), quality=approximate.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ppac"
FUEL_CSV = ROOT / "data" / "reference" / "fuel_prices.csv"

# Capital-city (or documented representative-city) mapping for the
# BankBazaar city tables. Comments give the convention caveats.
CITY_TO_STATE = {
    "NEW DELHI": "DL",
    "KOLKATA": "WB",
    "MUMBAI": "MH",
    "CHENNAI": "TN",
    "BANGALORE": "KA",
    "HYDERABAD": "TS",
    "JAIPUR": "RJ",
    "LUCKNOW": "UP",
    "PATNA": "BR",
    "BHOPAL": "MP",
    "RAIPUR": "CG",
    "RANCHI": "JH",
    "DEHRADUN": "UK",
    "SHIMLA": "HP",
    "SRINAGAR": "JK",   # summer capital
    "GUWAHATI": "AS",   # Dispur
    "BHUBANESHWAR": "OD",
    "THIRUVANANTHAPURAM": "KL",
    "PONDICHERRY": "PY",
    "AHMEDABAD": "GJ",  # Gandhinagar adjacent
    "GUNTUR": "AP",     # Amaravati adjacent
    "CHANDIGARH": "CH",  # also HR & PB capital (UT VAT; see module docstring)
}
SHARED_CAPITAL = {"HR": "CH", "PB": "CH"}  # price taken from Chandigarh

# Feb 2025 state-capital snapshot (factodata.com, PPAC/OMC-sourced),
# transcribed 2026-06-11. DN = mean of Dadra & Nagar Haveli and Daman & Diu.
SNAP_2025 = {  # state_code: (petrol, diesel)
    "AN": (82.46, 78.05), "AP": (108.35, 96.22), "AR": (90.95, 80.47),
    "AS": (98.19, 89.42), "BR": (105.53, 92.37), "CH": (94.30, 82.45),
    "CG": (100.45, 93.39), "DN": (92.47, 88.19), "DL": (94.77, 87.67),
    "GA": (97.30, 89.03), "GJ": (95.11, 90.78), "HR": (94.30, 82.45),
    "HP": (94.78, 87.13), "JK": (99.70, 84.88), "JH": (98.03, 92.80),
    "KA": (102.92, 88.99), "KL": (107.30, 96.18), "MP": (106.28, 91.68),
    "MH": (103.50, 90.03), "MN": (99.21, 85.26), "ML": (96.05, 87.48),
    "MZ": (99.06, 87.92), "NL": (97.71, 88.83), "OD": (101.39, 92.96),
    "PY": (96.26, 86.47), "PB": (94.30, 82.45), "RJ": (104.41, 89.93),
    "SK": (101.75, 89.00), "TN": (100.80, 92.39), "TS": (107.46, 95.70),
    "TR": (97.81, 86.81), "UP": (94.69, 87.81), "UK": (93.29, 88.13),
    "WB": (105.01, 91.82),
}

# CNG city anchors (Rs/kg) from goodreturns Wayback snapshots.
CNG_ANCHORS = {
    2019: {"DL": 44.70, "MH": 49.61, "KA": 56.95, "TS": 64.30},
    2021: {"DL": 42.70, "MH": 47.90, "KA": 50.50, "TS": 64.70,
           "UP": 56.75, "HR": 53.25, "MP": 63.00},
    2024: {"DL": 76.59, "MH": 76.00, "KA": 82.50, "TS": 93.00,
           "UP": 81.20, "HR": 82.62, "MP": 92.00},
}
CNG_FULL = ["MH", "KA", "TS"]          # anchored 2019/2021/2024 -> 2017-2026
CNG_LATE = ["UP", "HR", "MP"]          # anchored 2021/2024      -> 2020-2026

ERA_YEARS = {  # anchor label -> calendar years it covers
    "2019": range(2017, 2020),
    "2021": range(2020, 2022),
    "2025": range(2022, 2027),
}
CNG_ERA_YEARS = {2019: range(2017, 2020), 2021: range(2020, 2022), 2024: range(2022, 2027)}


def parse_bankbazaar(name: str) -> dict[str, float]:
    """City -> Rs/litre from an archived BankBazaar city table."""
    tables = pd.read_html(RAW / name)
    big = max(tables, key=lambda t: t.shape[0])
    out = {}
    for _, row in big.iloc[1:].iterrows():
        city = str(row[0]).strip().upper()
        m = re.search(r"([\d.]+)", str(row[1]))
        if m:
            out[city] = float(m.group(1))
    return out


def anchor_differentials() -> dict[str, dict[str, dict[str, float]]]:
    """{anchor: {fuel: {state_code: state - Delhi}}}"""
    files = {
        "2019": ("bb_petrol_2019.html", "bb_diesel_2019.html"),
        "2021": ("bb_petrol_2021.html", "bb_diesel_2021.html"),
    }
    diffs: dict[str, dict[str, dict[str, float]]] = {}
    for anchor, (pet_f, die_f) in files.items():
        diffs[anchor] = {}
        for fuel, fname in (("Petrol", pet_f), ("Diesel", die_f)):
            cities = parse_bankbazaar(fname)
            if "DELHI" in cities:  # 2019 tables say DELHI, 2021 say NEW DELHI
                cities["NEW DELHI"] = cities.pop("DELHI")
            delhi = cities["NEW DELHI"]
            d = {st: cities[c] - delhi for c, st in CITY_TO_STATE.items() if c in cities}
            for st, src in SHARED_CAPITAL.items():
                if src in d:
                    d[st] = d[src]
            diffs[anchor][fuel] = d
    delhi_p, delhi_d = SNAP_2025["DL"]
    diffs["2025"] = {
        "Petrol": {st: v[0] - delhi_p for st, v in SNAP_2025.items()},
        "Diesel": {st: v[1] - delhi_d for st, v in SNAP_2025.items()},
    }
    return diffs


def main() -> None:
    delhi = pd.read_csv(FUEL_CSV, comment="#")
    delhi = delhi[delhi.state_code == "DL"].set_index(["fuel", "year"]).price_avg_inr

    diffs = anchor_differentials()
    for a in ("2019", "2021"):
        for fuel in ("Petrol", "Diesel"):
            print(f"# anchor {a} {fuel}: {len(diffs[a][fuel])} states, "
                  f"sample {sorted(diffs[a][fuel].items())[:4]}")

    rows = []
    src_pd = "Capital-city RSP snapshots 2019/2021/2025 differential on Delhi series"
    for fuel in ("Petrol", "Diesel"):
        states = sorted(set().union(*[diffs[a][fuel] for a in diffs]))
        for st in states:
            if st in ("DL", "ALL"):
                continue
            for anchor, years in ERA_YEARS.items():
                if st not in diffs[anchor][fuel]:
                    continue
                for year in years:
                    price = round(delhi[(fuel, year)] + diffs[anchor][fuel][st], 1)
                    src = src_pd + (" (partial year)" if year == 2026 else "")
                    rows.append((st, year, fuel, price, src, "approximate"))

    src_cng = "City-gas CNG snapshots 2019/2021/2024 differential on Delhi series"
    for st in CNG_FULL + CNG_LATE:
        for anchor, years in CNG_ERA_YEARS.items():
            if st not in CNG_ANCHORS[anchor] or (st in CNG_LATE and anchor == 2019):
                continue
            d = CNG_ANCHORS[anchor][st] - CNG_ANCHORS[anchor]["DL"]
            for year in years:
                price = round(delhi[("CNG", year)] + d, 1)
                src = src_cng + (" (partial year)" if year == 2026 else "")
                rows.append((st, year, "CNG", price, src, "approximate"))

    out = pd.DataFrame(rows, columns=["state_code", "year", "fuel", "price_avg_inr", "source", "quality"])
    out = out.sort_values(["state_code", "fuel", "year"], key=lambda s: s.map(
        {"Petrol": 0, "Diesel": 1, "CNG": 2}).fillna(s) if s.name == "fuel" else s)
    buf = io.StringIO()
    out.to_csv(buf, index=False, header=False)
    print(buf.getvalue())
    print(f"# total rows: {len(out)}")


if __name__ == "__main__":
    main()

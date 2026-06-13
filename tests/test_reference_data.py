"""Integrity checks for committed reference datasets."""

from pathlib import Path

import pandas as pd

REFERENCE = Path(__file__).resolve().parents[1] / "data" / "reference"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(REFERENCE / name, comment="#")


def test_annual_population_contract():
    population = read("state_population_annual.csv")
    assert len(population) == 37 * 15
    assert set(population["year"]) == set(range(2012, 2027))
    assert not population.duplicated(["state_code", "year"]).any()
    reconstructed = population["urban_population_mn"] + population["rural_population_mn"]
    assert (reconstructed - population["population_mn"]).abs().max() < 0.0002
    assert set(population["quality"]) == {"estimate"}


def test_gsdp_keys_and_growth():
    gsdp = read("state_gsdp.csv")
    assert len(gsdp) == 453
    assert not gsdp.duplicated(["state_code", "fy"]).any()
    assert set(gsdp["level_quality"]) == {"official"}
    assert set(gsdp["growth_quality"]) == {"derived"}
    assert set(gsdp["quality"]) == {"official_derived"}


def test_cng_snapshot_reconciles():
    cng = read("cng_stations.csv")
    national = cng.loc[
        (cng["state_code"] == "ALL") & (cng["year"] == 2024), "stations"
    ].iloc[0]
    states = cng.loc[
        (cng["state_code"] != "ALL") & (cng["year"] == 2024), "stations"
    ].sum()
    assert states == national == 6890


def test_ev_snapshot_discloses_incomplete_allocation():
    ev = read("ev_charging.csv")
    national = ev.loc[
        (ev["state_code"] == "ALL") & (ev["year"] == 2025), "public_chargers"
    ].iloc[0]
    states = ev.loc[
        (ev["state_code"] != "ALL") & (ev["year"] == 2025), "public_chargers"
    ].sum()
    assert states < national
    assert round(100 * states / national, 2) == 77.65
    assert set(ev.loc[ev["year"] == 2025, "state_allocation_coverage_pct"]) == {77.65}


def test_unavailable_capabilities_are_gaps_not_placeholder_observations():
    gaps = read("known_data_gaps.csv")
    assert set(gaps["gap_id"]) == {
        "vehicle_finance_penetration",
        "oem_dealer_network",
    }
    assert set(gaps["status"]) == {"unavailable"}


def test_canonical_events_and_tax_keys():
    events = read("policy_events_canonical.csv")
    tax = read("vehicle_lifetime_tax.csv")
    assert len(events) == 74
    assert events["event_id"].is_unique
    assert not tax.duplicated(["state_code", "fuel"]).any()
    assert set(tax["fuel"]) == {"Petrol", "Diesel", "CNG", "Strong Hybrid", "EV"}

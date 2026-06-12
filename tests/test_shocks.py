import numpy as np

from complexity_lab.simulation.shocks import ShockConfig, ShockWindow, run_shock_sim, shock_summary


def test_conservation_identity():
    cfg = ShockConfig(n_months=48)
    df = run_shock_sim(cfg)
    initial_inv = cfg.base_demand * cfg.initial_inventory_cover
    implied_inv = initial_inv + df["production"].sum() - df["retail"].sum()
    assert np.isclose(implied_inv, df["inventory"].iloc[-1], rtol=1e-9)


def test_no_shock_run_is_stable():
    df = run_shock_sim(ShockConfig(n_months=60))
    assert df["lost_sales"].sum() < 0.01 * df["demand"].sum()
    tail = df.iloc[12:]
    assert tail["inventory_cover_months"].between(0.5, 2.0).all()


def test_supply_shock_draws_down_inventory_then_recovers():
    shock = ShockWindow(start=24, end=28, multiplier=0.3)
    cfg = ShockConfig(n_months=60, supply_shocks=[shock])
    df = run_shock_sim(cfg)
    base = run_shock_sim(ShockConfig(n_months=60))
    during = df[(df["month"] >= 24) & (df["month"] < 28)]
    before = df[df["month"] < 24]
    assert during["inventory_cover_months"].min() < before["inventory_cover_months"].min()
    s = shock_summary(df, base)
    assert s["total_lost_sales"] >= 0
    assert s["recovery_month"] is not None and s["recovery_month"] >= 28


def test_demand_shock_creates_lost_sales_only_if_supply_constrained():
    # A pure demand collapse never creates lost sales (sales = demand, inventory builds)
    shock = ShockWindow(start=24, end=27, multiplier=0.4)
    df = run_shock_sim(ShockConfig(n_months=60, demand_shocks=[shock]))
    assert df["lost_sales"].sum() < 1.0
    # inventory cover spikes during the collapse — the channel-stress signature
    assert df.loc[df["month"].between(24, 27), "inventory_cover_months"].max() > 1.4


def test_bullwhip_production_more_volatile_than_retail_under_demand_shock():
    shock = ShockWindow(start=24, end=27, multiplier=0.5)
    df = run_shock_sim(ShockConfig(n_months=60, demand_shocks=[shock]))
    base = run_shock_sim(ShockConfig(n_months=60))
    assert shock_summary(df, base)["bullwhip_ratio"] > 1.0

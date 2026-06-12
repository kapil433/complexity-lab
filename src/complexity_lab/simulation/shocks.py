"""Demand & supply shock simulation: a transparent stock-and-flow channel model.

The pipeline is factory → dealer inventory → retail. Each month:

- latent demand D_t = base × seasonality × (1+g)^t × demand_shock_t
- retail R_t = min(D_t, I_{t-1} + P_t)            (sales limited by availability)
- production P_t targets a stock cover: the OEM forecasts demand (trailing mean),
  then produces forecast + a correction toward `target_cover` months of stock,
  smoothed by an adjustment lag — all scaled by supply_shock_t and capacity.
- inventory I_t = I_{t-1} + P_t − R_t

Shocks are multiplicative windows (e.g. demand 0.5 for months 24–27 = a demand
collapse; supply 0.3 = a semiconductor-style production cut). The model is for
intuition about channel dynamics — bullwhip, restock overshoot, lost sales —
not point forecasting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_SEASONALITY = np.array(
    # Jan..Dec, loosely calibrated to Indian PV retail (festive Oct-Nov, March FY-end)
    [0.95, 0.93, 1.10, 0.90, 0.95, 0.92, 0.96, 1.00, 1.05, 1.18, 1.12, 0.94]
)


@dataclass
class ShockWindow:
    start: int          # month index (0-based)
    end: int            # exclusive
    multiplier: float   # 1.0 = no shock


@dataclass
class ShockConfig:
    n_months: int = 60
    base_demand: float = 300_000.0       # units/month (≈ national PV retail)
    monthly_growth: float = 0.004        # ≈ 5%/yr
    seasonality: np.ndarray = field(default_factory=lambda: DEFAULT_SEASONALITY.copy())
    start_month: int = 0                 # calendar month offset (0 = January)
    target_cover: float = 1.1            # desired dealer stock, in months of demand
    adjustment_lag: float = 3.0          # months over which OEMs close inventory gaps
    forecast_window: int = 3             # trailing months used as the OEM demand forecast
    capacity_mult: float = 1.6           # production ceiling vs base demand
    initial_inventory_cover: float = 1.1
    demand_shocks: list[ShockWindow] = field(default_factory=list)
    supply_shocks: list[ShockWindow] = field(default_factory=list)


def _window_multiplier(t: int, windows: list[ShockWindow]) -> float:
    m = 1.0
    for w in windows:
        if w.start <= t < w.end:
            m *= w.multiplier
    return m


def run_shock_sim(cfg: ShockConfig) -> pd.DataFrame:
    """Simulate the channel; returns monthly paths + diagnostics columns."""
    season = np.asarray(cfg.seasonality, dtype=float)
    demand_hist: list[float] = []
    inventory = cfg.base_demand * cfg.initial_inventory_cover
    capacity = cfg.base_demand * cfg.capacity_mult

    rows = []
    for t in range(cfg.n_months):
        s = season[(t + cfg.start_month) % len(season)]
        trend = (1 + cfg.monthly_growth) ** t
        d_shock = _window_multiplier(t, cfg.demand_shocks)
        s_shock = _window_multiplier(t, cfg.supply_shocks)

        demand = cfg.base_demand * trend * s * d_shock

        # OEM's demand forecast: trailing mean of realised demand (what it can see
        # through bookings/retail), falling back to current demand at t=0.
        if demand_hist:
            forecast = float(np.mean(demand_hist[-cfg.forecast_window:]))
        else:
            forecast = demand

        target_inventory = cfg.target_cover * forecast
        correction = (target_inventory - inventory) / cfg.adjustment_lag
        production = float(np.clip((forecast + correction) * s_shock, 0.0, capacity * s_shock))

        available = inventory + production
        retail = min(demand, available)
        lost_sales = demand - retail
        inventory = available - retail

        demand_hist.append(demand)
        rows.append(
            {
                "month": t,
                "demand": demand,
                "retail": retail,
                "production": production,   # ≈ wholesale dispatches
                "inventory": inventory,
                "lost_sales": lost_sales,
                "inventory_cover_months": inventory / demand if demand > 0 else np.nan,
                "ws_retail_ratio": production / retail if retail > 0 else np.nan,
                "demand_shock": d_shock,
                "supply_shock": s_shock,
            }
        )
    return pd.DataFrame(rows)


def shock_summary(result: pd.DataFrame, baseline: pd.DataFrame) -> dict:
    """Compare a shocked run against its no-shock baseline."""
    merged = result.merge(baseline, on="month", suffixes=("", "_base"))
    total_lost = float(result["lost_sales"].sum())
    retail_gap = float((merged["retail_base"] - merged["retail"]).sum())
    trough = merged.loc[merged["retail"].idxmin()]
    # recovery: first month after the trough where retail returns to ≥98% of baseline
    after = merged[merged["month"] > trough["month"]]
    rec = after[after["retail"] >= 0.98 * after["retail_base"]]
    bullwhip = float(result["production"].pct_change().var()
                     / max(result["retail"].pct_change().var(), 1e-12))
    return {
        "total_lost_sales": round(total_lost),
        "retail_vs_baseline_gap": round(retail_gap),
        "trough_month": int(trough["month"]),
        "trough_retail_vs_baseline": round(float(trough["retail"] / trough["retail_base"]), 3),
        "recovery_month": int(rec["month"].iloc[0]) if not rec.empty else None,
        "peak_inventory_cover": round(float(result["inventory_cover_months"].max()), 2),
        "min_inventory_cover": round(float(result["inventory_cover_months"].min()), 2),
        "bullwhip_ratio": round(bullwhip, 2),
    }

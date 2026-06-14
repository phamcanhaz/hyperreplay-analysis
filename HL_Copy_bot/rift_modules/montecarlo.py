"""Monte Carlo simulation — adapted from RIFT rift_engine.montecarlo.
 
Resamples daily PnL returns to estimate distribution of future outcomes.
"""
 
from __future__ import annotations
import numpy as np
 
 
def mc_simulate_daily(
    daily_pnl: list[float],
    n_simulations: int = 10000,
    horizon_days: int = 30,
) -> dict:
    """Run Monte Carlo on daily PnL series.
 
    Args:
        daily_pnl: list of daily PnL values ($)
        n_simulations: number of random paths (default 10000)
        horizon_days: how many days to simulate forward (default 30)
 
    Returns:
        dict with p10/p50/p90, prob_negative, expected_profit, etc.
    """
    arr = np.array(daily_pnl, dtype=np.float64)
    if len(arr) < 3:
        return {
            "p10": 0, "p50": 0, "p90": 0,
            "prob_negative": 0.5, "expected_profit": 0,
            "median_max_dd": 0, "num_simulations": 0,
        }
 
    n = len(arr)
    # Vectorized: generate all paths at once
    indices = np.random.randint(0, n, size=(n_simulations, horizon_days))
    paths = arr[indices]  # (n_simulations, horizon_days)
 
    # Cumulative PnL over horizon
    final = np.cumsum(paths, axis=1)[:, -1]
 
    # Max drawdown per path
    cum = np.cumsum(paths, axis=1)
    running_max = np.maximum.accumulate(cum, axis=1)
    dd = cum - running_max  # negative drawdown per step
    max_dd = np.min(dd, axis=1)
 
    return {
        "p10": float(np.percentile(final, 10)),
        "p25": float(np.percentile(final, 25)),
        "p50": float(np.percentile(final, 50)),
        "p75": float(np.percentile(final, 75)),
        "p90": float(np.percentile(final, 90)),
        "prob_negative": float(np.mean(final < 0)),
        "expected_profit": float(np.mean(final)),
        "median_max_dd": float(np.median(max_dd)),
        "num_simulations": n_simulations,
    }
 
 
def mc_quick(pnl_list: list[float]) -> dict:
    """Quick Monte Carlo with sensible defaults."""
    return mc_simulate_daily(pnl_list, n_simulations=5000, horizon_days=30)

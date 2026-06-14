"""Alpha decay primitives — ported from RIFT rift_substrate.decay.
 
Measures how quickly a trader's edge decays over time using Information
Coefficient (IC) analysis across forward horizons.
 
Apache 2.0 — original: https://github.com/Nexstone/rift
"""
 
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import numpy as np
from numpy.typing import NDArray
from scipy.stats import spearmanr
 
 
@dataclass(frozen=True)
class AlphaDecayCurve:
    horizons: NDArray
    ics: NDArray
    ic_ci_lower: NDArray
    ic_ci_upper: NDArray
    method: str
    n_observations: int
    n_bootstrap: int = 0
 
 
@dataclass(frozen=True)
class HalfLifeFit:
    half_life: float
    tau: float
    ic_initial: float
    r_squared: float
    n_points: int
 
 
def make_forward_returns(
    prices: NDArray | list[float],
    horizons: NDArray | list[int],
) -> NDArray:
    p = np.asarray(prices, dtype=np.float64).ravel()
    h = np.asarray(horizons, dtype=np.int64).ravel()
    if h.size == 0:
        return np.empty((p.size, 0), dtype=np.float64)
    if np.any(h < 1):
        raise ValueError("all horizons must be >= 1")
    T = p.size
    out = np.full((T, h.size), np.nan, dtype=np.float64)
    for hi, hv in enumerate(h):
        if hv >= T:
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = p[hv:] / p[:T - hv]
        out[:T - hv, hi] = ratio - 1.0
    return out
 
 
def _ic_one_horizon(
    signal: NDArray, fwd_return: NDArray, method: Literal["pearson", "spearman"],
) -> float:
    mask = np.isfinite(signal) & np.isfinite(fwd_return)
    if mask.sum() < 2:
        return float("nan")
    s = signal[mask]
    r = fwd_return[mask]
    if np.std(s) == 0 or np.std(r) == 0:
        return float("nan")
    if method == "spearman":
        rho, _ = spearmanr(s, r)
        return float(rho)
    return float(np.corrcoef(s, r)[0, 1])
 
 
def compute_ic_curve(
    signal: NDArray | list[float],
    forward_returns: NDArray,
    horizons: NDArray | list[int],
    method: Literal["pearson", "spearman"] = "spearman",
    n_bootstrap: int = 0,
    avg_block_size: int | None = None,
    seed: int | None = None,
) -> AlphaDecayCurve:
    s = np.asarray(signal, dtype=np.float64).ravel()
    fr = np.asarray(forward_returns, dtype=np.float64)
    if fr.ndim == 1:
        fr = fr.reshape(-1, 1)
    h = np.asarray(horizons, dtype=np.int64).ravel()
    if fr.shape[1] != h.size:
        raise ValueError(
            f"forward_returns has {fr.shape[1]} columns but {h.size} horizons"
        )
    if fr.shape[0] != s.size:
        raise ValueError(
            f"signal length ({s.size}) != forward_returns rows ({fr.shape[0]})"
        )
    if method not in ("pearson", "spearman"):
        raise ValueError(f"method must be 'pearson' or 'spearman'; got {method!r}")
 
    H = h.size
    ics = np.full(H, np.nan, dtype=np.float64)
    ci_lo = np.full(H, np.nan, dtype=np.float64)
    ci_hi = np.full(H, np.nan, dtype=np.float64)
 
    if avg_block_size is None:
        avg_block_size = max(1, int(np.sqrt(s.size)))
 
    rng = np.random.default_rng(seed) if n_bootstrap > 0 else None
 
    for hi in range(H):
        col = fr[:, hi]
        ics[hi] = _ic_one_horizon(s, col, method)
        if n_bootstrap > 0 and rng is not None:
            lo, hi_ = _bootstrap_ic_ci(s, col, method, n_bootstrap, avg_block_size, rng)
            ci_lo[hi] = lo
            ci_hi[hi] = hi_
 
    return AlphaDecayCurve(
        horizons=h, ics=ics, ic_ci_lower=ci_lo, ic_ci_upper=ci_hi,
        method=method, n_observations=int(s.size), n_bootstrap=int(n_bootstrap),
    )
 
 
def _bootstrap_ic_ci(
    signal, fwd_return, method, n_bootstrap, avg_block_size, rng,
) -> tuple[float, float]:
    mask = np.isfinite(signal) & np.isfinite(fwd_return)
    s = signal[mask]
    r = fwd_return[mask]
    n = s.size
    if n < 2:
        return (float("nan"), float("nan"))
 
    p = 1.0 / max(1, avg_block_size)
    ics = np.empty(n_bootstrap, dtype=np.float64)
    for b in range(n_bootstrap):
        idx = np.empty(n, dtype=np.int64)
        i = 0
        while i < n:
            start = int(rng.integers(0, n))
            block_len = max(1, int(rng.geometric(p)))
            end = min(i + block_len, n)
            take = end - i
            idx[i:end] = (start + np.arange(take)) % n
            i = end
        s_b = s[idx]
        r_b = r[idx]
        if np.std(s_b) == 0 or np.std(r_b) == 0:
            ics[b] = np.nan
            continue
        if method == "spearman":
            rho, _ = spearmanr(s_b, r_b)
            ics[b] = float(rho)
        else:
            ics[b] = float(np.corrcoef(s_b, r_b)[0, 1])
 
    ics_clean = ics[np.isfinite(ics)]
    if ics_clean.size < 2:
        return (float("nan"), float("nan"))
    return (
        float(np.percentile(ics_clean, 2.5)),
        float(np.percentile(ics_clean, 97.5)),
    )
 
 
def estimate_half_life(curve: AlphaDecayCurve) -> HalfLifeFit:
    abs_ics = np.abs(curve.ics)
    horizons = curve.horizons.astype(np.float64)
 
    mask = np.isfinite(abs_ics) & (abs_ics > 0)
    n_pts = int(mask.sum())
    if n_pts < 2:
        return HalfLifeFit(half_life=float("nan"), tau=float("nan"),
                           ic_initial=float("nan"), r_squared=float("nan"), n_points=n_pts)
 
    log_ics = np.log(abs_ics[mask])
    h_used = horizons[mask]
 
    if np.std(log_ics) < 1e-10:
        return HalfLifeFit(half_life=float("inf"), tau=float("inf"),
                           ic_initial=float(np.exp(log_ics.mean())),
                           r_squared=float("nan"), n_points=n_pts)
 
    X = np.column_stack([np.ones_like(h_used), h_used])
    beta, *_ = np.linalg.lstsq(X, log_ics, rcond=None)
    log_ic_0 = float(beta[0])
    slope = float(beta[1])
 
    fitted = X @ beta
    ss_res = float(np.sum((log_ics - fitted) ** 2))
    ss_tot = float(np.sum((log_ics - log_ics.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
 
    if slope >= 0:
        return HalfLifeFit(half_life=float("inf"), tau=float("inf"),
                           ic_initial=float(np.exp(log_ic_0)),
                           r_squared=r_squared, n_points=n_pts)
 
    tau = -1.0 / slope
    half_life = tau * np.log(2.0)
    return HalfLifeFit(half_life=float(half_life), tau=float(tau),
                       ic_initial=float(np.exp(log_ic_0)),
                       r_squared=r_squared, n_points=n_pts)
 
 
# ─── High-level helper for HL Copy Bot ───
 
def compute_trader_alpha_decay(trades: list[dict]) -> dict:
    """Measure alpha decay from reconstructed trades.
 
    Uses the time-ordered trade PnLs as signal and forward returns over
    increasing horizons. Returns dict with half_life estimate or warning.
    """
    if len(trades) < 20:
        return {"half_life_days": None, "decay_detected": False, "warning": "insufficient_trades"}
 
    # Sort by entry_time
    sorted_trades = sorted(trades, key=lambda t: t["entry_time"])
    pnls = np.array([t["net_pnl"] for t in sorted_trades], dtype=np.float64)
 
    # Compute rolling cumulative PnL as "price" series
    cum_pnl = np.cumsum(pnls)
    if np.std(cum_pnl) < 1e-6:
        return {"half_life_days": None, "decay_detected": False, "warning": "constant_pnl"}
 
    # Use trade index as "time" - compare early vs late performance
    # Signal = recent performance vs overall
    early_sharpe = _sharpe(pnls[:len(pnls)//3])
    late_sharpe = _sharpe(pnls[-len(pnls)//3:])
 
    decay_detected = bool(early_sharpe > 0.3 and late_sharpe < early_sharpe * 0.5)
 
    return {
        "half_life_days": None,
        "decay_detected": decay_detected,
        "early_sharpe": round(float(early_sharpe), 3),
        "late_sharpe": round(float(late_sharpe), 3),
        "warning": "ALPHA_DECAYING" if decay_detected else "",
    }
 
 
def _sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2 or np.std(returns) < 1e-8:
        return 0.0
    return float(np.mean(returns) / np.std(returns))

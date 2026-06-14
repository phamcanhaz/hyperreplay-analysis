"""HMM regime detection — ported from RIFT rift_substrate.regime.hmm.
 
Detects market regime (calm/volatile/crisis) using a 3-state Gaussian HMM
on log returns, realized volatility, and funding rates.
 
Apache 2.0 — original: https://github.com/Nexstone/rift
"""
 
from __future__ import annotations
import warnings
from typing import Sequence
import numpy as np
from numpy.typing import NDArray
 
 
def compute_hmm_features(
    closes: NDArray | Sequence[float],
    funding_rates: NDArray | Sequence[float],
    vol_window: int = 24,
) -> tuple[NDArray, int]:
    closes_arr = np.asarray(closes, dtype=np.float64)
    funding_arr = np.asarray(funding_rates, dtype=np.float64)
    n = len(closes_arr)
 
    log_returns = np.zeros(n)
    if n > 1:
        log_returns[1:] = np.log(closes_arr[1:] / closes_arr[:-1])
 
    realized_vol = np.zeros(n)
    for i in range(vol_window, n):
        realized_vol[i] = np.std(log_returns[i - vol_window + 1: i + 1])
 
    features = np.column_stack([log_returns, realized_vol, funding_arr])
    return features, vol_window
 
 
def classify_states(model) -> dict[str, int]:
    if model is None:
        return {"calm": 0, "volatile": 1, "crisis": 2}
 
    vol_variances = []
    for i in range(model.n_components):
        cov = model.covars_[i]
        vol_variances.append(float(cov[1]) if cov.ndim == 1 else float(cov[1, 1]))
    sorted_idx = list(np.argsort(vol_variances))
 
    if model.n_components == 3:
        return {"calm": sorted_idx[0], "volatile": sorted_idx[1], "crisis": sorted_idx[2]}
    elif model.n_components == 2:
        return {"calm": sorted_idx[0], "volatile": sorted_idx[1], "crisis": sorted_idx[1]}
    else:
        return {"calm": sorted_idx[0], "volatile": sorted_idx[-1], "crisis": sorted_idx[-1]}
 
 
class HMMRegimeDetector:
    def __init__(
        self,
        n_states: int = 3,
        n_restarts: int = 10,
        vol_window: int = 24,
    ):
        self.n_states = n_states
        self.n_restarts = n_restarts
        self.vol_window = vol_window
        self.model = None
        self.state_labels: dict[str, int] = {"calm": 0, "volatile": 1, "crisis": 2}
        self.trained = False
 
    def fit(
        self,
        closes: NDArray | Sequence[float],
        funding_rates: NDArray | Sequence[float],
    ) -> bool:
        from hmmlearn.hmm import GaussianHMM
 
        features, valid_from = compute_hmm_features(closes, funding_rates, self.vol_window)
        valid_features = features[valid_from:]
        if len(valid_features) < 100:
            return False
 
        best_model = None
        best_score = -np.inf
        for seed in range(self.n_restarts):
            try:
                candidate = GaussianHMM(
                    n_components=self.n_states, covariance_type="diag",
                    n_iter=200, random_state=seed, tol=1e-4,
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    candidate.fit(valid_features)
                score = candidate.score(valid_features)
                if score > best_score:
                    best_score = score
                    best_model = candidate
            except Exception:
                continue
 
        if best_model is None:
            return False
 
        self.model = best_model
        self.state_labels = classify_states(best_model)
        self.trained = True
        return True
 
    def predict_regime(
        self,
        closes: NDArray | Sequence[float],
        funding_rates: NDArray | Sequence[float],
    ) -> str | None:
        if self.model is None:
            return None
 
        features, valid_from = compute_hmm_features(closes, funding_rates, self.vol_window)
        valid_features = features[valid_from:]
        if len(valid_features) < 10:
            return None
 
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                probs = self.model.predict_proba(valid_features)
            current_probs = probs[-1]
            p_crisis = float(current_probs[self.state_labels["crisis"]])
            p_volatile = float(current_probs[self.state_labels["volatile"]])
            if p_crisis > 0.5:
                return "crisis"
            elif p_volatile > 0.4:
                return "volatile"
            else:
                return "calm"
        except Exception:
            return None

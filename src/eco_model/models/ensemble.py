"""Equal-weight and regularised performance-weight forecast combinations (DEC-005).

Performance weights, per target/horizon/track (the caller does that slicing):

1. Keep complete rows of prior errors (outcome - forecast), then the latest
   MAX_ERRORS_FOR_WEIGHTS; return None below MIN_ERRORS_FOR_WEIGHTS.
2. Sigma = sample covariance (ddof=1, centred, so constant bias is *not*
   penalised) shrunk toward its own diagonal. Shrinkage intensity is the
   Ledoit-Wolf-type analytic estimator for the "diagonal, unequal variance"
   target of Schaefer & Strimmer (2005, SAGMB 4(1), target D): with
   standardised errors x and w_kij = x_ki x_kj,
       r_ij = n/(n-1) * mean_k w_kij,
       Var(r_ij) = n/(n-1)^3 * sum_k (w_kij - mean_k w_kij)^2,
       lambda* = clip( sum_{i!=j} Var(r_ij) / sum_{i!=j} r_ij^2, 0, 1 ),
   and Sigma = (1 - lambda*) S + lambda* diag(S). If any method has zero error
   variance, or all sample correlations are zero, lambda* = 1.
3. Minimise w' Sigma w + lam * ||w - 1/M||^2 with lam = trace(Sigma)/M,
   subject to w >= 0, sum(w) = 1. On the simplex the penalty equals
   lam*||w||^2 - lam/M, so the problem is min w'(Sigma + lam I)w on the
   simplex: a convex QP solved exactly by enumerating supports (active sets)
   and solving the equality-constrained problem on each; the best feasible
   support satisfies the KKT conditions. M is capped at MAX_METHODS.
If trace(Sigma) == 0 (all errors constant), equal weights are returned.
"""

from __future__ import annotations

import itertools
import math
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from eco_model.contracts import MAX_ERRORS_FOR_WEIGHTS, MIN_ERRORS_FOR_WEIGHTS

ENSEMBLE_MEMBERS: tuple[str, ...] = ("persistence", "ar", "var3")
MAX_METHODS = 12
WEIGHT_SUM_TOL = 1e-9
_FEASIBILITY_TOL = 1e-12


def equal_weights(methods: Sequence[str]) -> dict[str, float]:
    names = list(methods)
    if not names or len(set(names)) != len(names):
        raise ValueError("methods must be non-empty and unique")
    return {m: 1.0 / len(names) for m in names}


def shrink_to_diagonal(errors: np.ndarray) -> tuple[np.ndarray, float]:
    """(shrunk covariance, intensity) for an (n, M) error matrix; see module doc."""
    x = np.asarray(errors, dtype=float)
    n = x.shape[0]
    sample = np.cov(x, rowvar=False, ddof=1)
    sd = np.sqrt(np.diag(sample))
    if np.any(sd <= 0):
        return np.diag(np.diag(sample)), 1.0
    z = (x - x.mean(axis=0)) / sd
    w = z[:, :, None] * z[:, None, :]
    r = n / (n - 1) * w.mean(axis=0)
    var_r = n / (n - 1) ** 3 * ((w - w.mean(axis=0)) ** 2).sum(axis=0)
    off = ~np.eye(x.shape[1], dtype=bool)
    denom = float((r[off] ** 2).sum())
    intensity = 1.0 if denom <= 0 else float(np.clip(var_r[off].sum() / denom, 0.0, 1.0))
    shrunk = (1.0 - intensity) * sample + intensity * np.diag(np.diag(sample))
    return shrunk, intensity


def _support_solution(q: np.ndarray, support: tuple[int, ...]) -> np.ndarray | None:
    idx = list(support)
    v = np.linalg.pinv(q[np.ix_(idx, idx)]) @ np.ones(len(idx))
    total = v.sum()
    if total <= _FEASIBILITY_TOL or np.any(v / total < -_FEASIBILITY_TOL):
        return None
    w = np.zeros(q.shape[0])
    w[idx] = np.clip(v / total, 0.0, None)
    return w / w.sum()


def penalised_simplex_weights(sigma: np.ndarray, lam: float) -> np.ndarray:
    """argmin w'Sigma w + lam*||w - 1/M||^2 over the probability simplex (exact)."""
    sigma = np.asarray(sigma, dtype=float)
    if sigma.ndim != 2 or sigma.shape[0] != sigma.shape[1] or not 1 <= sigma.shape[0] <= MAX_METHODS:
        raise ValueError(f"sigma must be square with 1..{MAX_METHODS} rows")
    if not math.isfinite(lam) or lam < 0:
        raise ValueError("lam must be finite and non-negative")
    m = sigma.shape[0]
    q = (sigma + sigma.T) / 2 + lam * np.eye(m)
    target = np.full(m, 1.0 / m)
    best, best_value = target, math.inf
    for size in range(1, m + 1):
        for support in itertools.combinations(range(m), size):
            w = _support_solution(q, support)
            if w is None:
                continue
            value = float(w @ sigma @ w + lam * np.sum((w - target) ** 2))
            if value < best_value - 1e-15:
                best, best_value = w, value
    return best


def performance_weights(past_errors: pd.DataFrame) -> dict[str, float] | None:
    """Regularised minimum-variance weights, or None with < MIN_ERRORS_FOR_WEIGHTS rows."""
    columns = list(past_errors.columns)
    if not columns or len(set(columns)) != len(columns):
        raise ValueError("past_errors needs unique, non-empty method columns")
    common = past_errors.dropna(how="any").tail(MAX_ERRORS_FOR_WEIGHTS)
    if len(common) < MIN_ERRORS_FOR_WEIGHTS:
        return None
    sigma, _ = shrink_to_diagonal(common.to_numpy(dtype=float))
    trace = float(np.trace(sigma))
    if trace <= 0:
        return equal_weights(columns)
    weights = penalised_simplex_weights(sigma, trace / len(columns))
    return {c: float(v) for c, v in zip(columns, weights)}


def combine(points: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Weighted sum of member points; keys must match and weights sum to 1."""
    if set(points) != set(weights):
        raise ValueError(f"method mismatch: {sorted(points)} vs {sorted(weights)}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative")
    if abs(sum(weights.values()) - 1.0) > WEIGHT_SUM_TOL:
        raise ValueError("weights must sum to 1")
    if not all(math.isfinite(v) for v in points.values()):
        raise ValueError("member point forecasts must be finite")
    return float(sum(points[m] * weights[m] for m in weights))

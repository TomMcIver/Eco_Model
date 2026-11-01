"""Compact reduced-form VAR on the (up to three) targets.

Method (``statsmodels.tsa.api.VAR``, equation-by-equation OLS with intercept):

* Sample: the trailing contiguous block of quarters where *every* observed
  target is present (common sample). Needs >= MIN_VAR_OBS rows and >= 2
  observed targets.
* Lag order: p in 1..max_estimable_lag(T, k) chosen by AIC, every candidate
  estimated on the same effective sample (the first p_max rows are held back
  for all p); the chosen p is refitted on the full block. The cap keeps at
  least OBS_PER_PARAM effective observations per parameter in each equation.
* Stability: all companion-matrix eigenvalue moduli must be
  < 1 - STABILITY_MARGIN. If not, p is reduced one step at a time; if no
  p >= 1 is stable (or fits), the model falls back to per-target AR
  (``AutoRegressive``) and the reason is recorded.
* Ragged edge / conditioning: the forecast path starts at the last common
  quarter. Observations a target has *after* that quarter are ignored (no
  conditioning on them), but each target's forecast at horizon h is read off
  the path h quarters after that target's *own* last observed quarter, i.e.
  path step offset + h where offset = own_last - common_last.

``last_diagnostics`` holds ``"model"`` (e.g. ``"var(p=2, n=120, k=3)"`` or
``"fallback:ar: <reason>"``) plus one entry per target.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR

from eco_model.models._common import (
    companion_moduli,
    observed_columns,
    validate_history,
    validate_horizons,
)
from eco_model.models.univariate import AutoRegressive

MAX_VAR_LAG = 4
MIN_VAR_OBS = 24
OBS_PER_PARAM = 3
STABILITY_MARGIN = 1e-6


@dataclass(frozen=True)
class VarFit:
    """y_t = intercept + sum_i coefs[i] @ y_{t-1-i} + e_t."""

    lags: int
    intercept: np.ndarray  # (k,)
    coefs: np.ndarray  # (p, k, k)
    warnings: tuple[str, ...] = ()

    @property
    def root_moduli(self) -> np.ndarray:
        return companion_moduli(self.coefs)

    @property
    def is_stable(self) -> bool:
        return bool(np.all(self.root_moduli < 1.0 - STABILITY_MARGIN))

    def forecast_path(self, data: np.ndarray, steps: int) -> np.ndarray:
        """Iterated forecasts, shape (steps, k), after the last row of data."""
        window = [row for row in np.asarray(data, dtype=float)[-self.lags :]]
        path = []
        for _ in range(steps):
            nxt = self.intercept + sum(a @ window[-1 - i] for i, a in enumerate(self.coefs))
            path.append(nxt)
            window.append(nxt)
        return np.vstack(path)


def max_estimable_lag(n_obs: int, k: int, cap: int = MAX_VAR_LAG) -> int:
    """Largest p <= cap with (n_obs - p) >= OBS_PER_PARAM * (k * p + 1); 0 if none."""
    feasible = [p for p in range(1, cap + 1) if n_obs - p >= OBS_PER_PARAM * (k * p + 1)]
    return max(feasible, default=0)


def _record(caught: list) -> tuple[str, ...]:
    return tuple(sorted({str(w.message) for w in caught}))


def select_var_lag(data: np.ndarray, max_lag: int) -> tuple[int, tuple[str, ...]]:
    """AIC-best p in 1..max_lag, all candidates estimated on a common sample."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aics = {p: float(VAR(data[max_lag - p :]).fit(p, trend="c").aic) for p in range(1, max_lag + 1)}
    return min(aics, key=lambda p: (aics[p], p)), _record(caught)


def fit_var(data: np.ndarray, lags: int) -> VarFit:
    """Fit a VAR(lags) with intercept on all rows of data (T, k)."""
    data = np.asarray(data, dtype=float)
    if lags < 1 or data.ndim != 2 or len(data) <= lags:
        raise ValueError(f"cannot fit VAR({lags}) to data of shape {data.shape}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = VAR(data).fit(lags, trend="c")
    return VarFit(lags, np.asarray(res.intercept), np.asarray(res.coefs), _record(caught))


def common_block(frame: pd.DataFrame) -> pd.DataFrame:
    """Trailing contiguous block of rows where every column is observed."""
    complete = frame.notna().all(axis=1).to_numpy()
    if not complete.any():
        return frame.iloc[0:0]
    end = int(np.flatnonzero(complete)[-1])
    start = end
    while start > 0 and complete[start - 1]:
        start -= 1
    return frame.iloc[start : end + 1]


def _stable_fit(data: np.ndarray) -> tuple[VarFit | None, str]:
    """Select p, then reduce it until the fit is stable. Returns (fit, reason)."""
    max_lag = max_estimable_lag(len(data), data.shape[1])
    if len(data) < MIN_VAR_OBS or max_lag == 0:
        return None, f"common sample has {len(data)} obs (< {MIN_VAR_OBS} or too few for 1 lag)"
    try:
        p, _ = select_var_lag(data, max_lag)
    except (ValueError, np.linalg.LinAlgError) as exc:
        return None, f"lag selection failed ({exc})"
    reasons = []
    for lags in range(p, 0, -1):
        try:
            fit = fit_var(data, lags)
        except (ValueError, np.linalg.LinAlgError) as exc:
            reasons.append(f"p={lags} fit failed ({exc})")
            continue
        if fit.is_stable:
            return fit, f"aic p={p}" + (f"; reduced after {', '.join(reasons)}" if reasons else "")
        reasons.append(f"p={lags} unstable (max root {fit.root_moduli.max():.4f})")
    return None, "; ".join(reasons)


class CompactVAR:
    """Reduced-form VAR on the targets; per-target AR fallback."""

    name = "var3"

    def __init__(self) -> None:
        self.last_diagnostics: dict[str, str] = {}

    def forecast(
        self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0
    ) -> Mapping[tuple[str, int], float]:
        validate_history(history)
        hs = validate_horizons(horizons)
        cols = observed_columns(history)
        if len(cols) < 2:
            return self._fallback(history[cols], hs, f"only {len(cols)} observed target(s)")
        block = common_block(history[cols])
        fit, reason = _stable_fit(block.to_numpy())
        if fit is None:
            return self._fallback(history[cols], hs, reason)
        return self._forecast_from_fit(history[cols], block, fit, hs, reason)

    def _forecast_from_fit(
        self, frame: pd.DataFrame, block: pd.DataFrame, fit: VarFit, hs: tuple[int, ...], reason: str
    ) -> dict[tuple[str, int], float]:
        common_last = block.index[-1]
        offsets = {c: frame[c].dropna().index[-1].ordinal - common_last.ordinal for c in frame.columns}
        path = fit.forecast_path(block.to_numpy(), max(offsets.values()) + max(hs))
        out = {
            (c, h): float(path[offsets[c] + h - 1, j]) for j, c in enumerate(frame.columns) for h in hs
        }
        note = f"; warnings: {' | '.join(fit.warnings)}" if fit.warnings else ""
        diagnostics = {"model": f"var(p={fit.lags}, n={len(block)}, k={len(frame.columns)}; {reason}){note}"}
        diagnostics |= {c: f"common_last={common_last}, offset={offsets[c]}" for c in frame.columns}
        self.last_diagnostics = diagnostics
        return out

    def _fallback(
        self, frame: pd.DataFrame, hs: tuple[int, ...], reason: str
    ) -> dict[tuple[str, int], float]:
        ar = AutoRegressive()
        out = dict(ar.forecast(frame, hs))
        self.last_diagnostics = {"model": f"fallback:ar: {reason}", **ar.last_diagnostics}
        return out

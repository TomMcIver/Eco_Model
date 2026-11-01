"""Per-target univariate autoregression (the DEC-001 univariate method).

Method: OLS AR(p) with intercept via ``statsmodels.tsa.ar_model.AutoReg``
(conditional least squares, *not* the state-space/Kalman form). The lag order
p in 1..MAX_AR_LAG is chosen by AIC, every candidate being estimated on the
same sample (the first MAX_AR_LAG observations are held back for all p); the
chosen order is then refitted on the full block. Multi-step forecasts are
iterated from the fitted recursion.

The estimation block for each target is its trailing contiguous run of
observations (leading NaNs and anything before an interior gap are dropped).
A target falls back to persistence, with the reason recorded in
``last_diagnostics[target]``, when the block has fewer than MIN_AR_OBS
observations, the fit fails, or the fitted AR polynomial is non-stationary
(any companion root modulus >= 1 - STATIONARITY_MARGIN).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg

from eco_model.models._common import (
    companion_moduli,
    observed_columns,
    trailing_contiguous,
    validate_history,
    validate_horizons,
)

MAX_AR_LAG = 4
MIN_AR_OBS = 24
STATIONARITY_MARGIN = 1e-6
_MIN_FIT_SLACK = 10  # fit_ar needs at least max_lag + this many observations


@dataclass(frozen=True)
class ArFit:
    """A fitted AR(p) with intercept: y_t = c + sum_i coefs[i] * y_{t-1-i} + e_t."""

    lags: int
    intercept: float
    coefs: tuple[float, ...]
    aic: float
    warnings: tuple[str, ...] = ()

    @property
    def root_moduli(self) -> np.ndarray:
        return companion_moduli(np.asarray(self.coefs, dtype=float).reshape(-1, 1, 1))

    @property
    def is_stationary(self) -> bool:
        return bool(np.all(self.root_moduli < 1.0 - STATIONARITY_MARGIN))

    @property
    def mean(self) -> float:
        """Implied unconditional mean (meaningful only when stationary)."""
        return self.intercept / (1.0 - sum(self.coefs))

    def forecast_path(self, y: np.ndarray, steps: int) -> np.ndarray:
        """Iterated forecasts for steps 1..steps after the last element of y."""
        window = list(np.asarray(y, dtype=float)[-self.lags :])
        path = []
        for _ in range(steps):
            nxt = self.intercept + sum(c * window[-1 - i] for i, c in enumerate(self.coefs))
            path.append(nxt)
            window.append(nxt)
        return np.asarray(path)


def _aic_for_lag(y: np.ndarray, lags: int, hold_back: int) -> float:
    return float(AutoReg(y, lags=lags, trend="c", hold_back=hold_back).fit().aic)


def fit_ar(y: np.ndarray, max_lag: int = MAX_AR_LAG) -> ArFit:
    """Select p in 1..max_lag by AIC on a common sample, then fit AR(p) on all of y."""
    y = np.asarray(y, dtype=float)
    if y.ndim != 1 or len(y) < max_lag + _MIN_FIT_SLACK or not np.all(np.isfinite(y)):
        raise ValueError(f"need >= {max_lag + _MIN_FIT_SLACK} finite observations, got {len(y)}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aics = {p: _aic_for_lag(y, p, max_lag) for p in range(1, max_lag + 1)}
        lags = min(aics, key=lambda p: (aics[p], p))
        params = AutoReg(y, lags=lags, trend="c").fit().params
    return ArFit(
        lags=lags,
        intercept=float(params[0]),
        coefs=tuple(float(v) for v in params[1:]),
        aic=aics[lags],
        warnings=tuple(sorted({str(w.message) for w in caught})),
    )


def ar_forecast_series(
    series: pd.Series, horizons: Sequence[int]
) -> tuple[dict[int, float], str]:
    """AR forecasts {h: value} from the series' own last observation, plus a diagnostic."""
    block = trailing_contiguous(series)
    last = float(block.iloc[-1])
    fallback = {h: last for h in horizons}
    if len(block) < MIN_AR_OBS:
        return fallback, f"fallback:persistence: only {len(block)} contiguous obs (< {MIN_AR_OBS})"
    try:
        fit = fit_ar(block.to_numpy())
    except (ValueError, np.linalg.LinAlgError) as exc:
        return fallback, f"fallback:persistence: fit failed ({exc})"
    note = f"; warnings: {' | '.join(fit.warnings)}" if fit.warnings else ""
    if not fit.is_stationary:
        top = float(fit.root_moduli.max())
        return fallback, f"fallback:persistence: non-stationary AR(p={fit.lags}), max root {top:.4f}{note}"
    path = fit.forecast_path(block.to_numpy(), max(horizons))
    return {h: float(path[h - 1]) for h in horizons}, f"ar(p={fit.lags}, n={len(block)}){note}"


class AutoRegressive:
    """Per-target AR(p), p by AIC in 1..4; persistence fallback per target."""

    name = "ar"

    def __init__(self) -> None:
        self.last_diagnostics: dict[str, str] = {}

    def forecast(
        self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0
    ) -> Mapping[tuple[str, int], float]:
        validate_history(history)
        hs = validate_horizons(horizons)
        out: dict[tuple[str, int], float] = {}
        diagnostics: dict[str, str] = {}
        for col in observed_columns(history):
            values, note = ar_forecast_series(history[col], hs)
            out |= {(col, h): v for h, v in values.items()}
            diagnostics[col] = note
        self.last_diagnostics = diagnostics
        return out


__all__ = ["ArFit", "AutoRegressive", "MAX_AR_LAG", "MIN_AR_OBS", "ar_forecast_series", "fit_ar"]

"""Empirical predictive quantiles from prior out-of-sample errors (DEC-005).

error = outcome - forecast, so quantile value = point + empirical quantile of
errors. Quantiles use ``numpy.quantile(method="linear")`` (Hyndman-Fan type 7).
The caller supplies only errors known at issuance for the same track, target
and horizon; every non-NaN error supplied is used (no window is applied here).
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from eco_model.contracts import INTERVAL_LEVELS, MIN_ERRORS_50_80, MIN_ERRORS_95

QUANTILE_METHOD = "linear"


def interval_levels_available(n_errors: int) -> tuple[float, ...]:
    """Central interval levels that may be reported with n_errors prior errors."""
    if n_errors < 0:
        raise ValueError("n_errors must be non-negative")
    if n_errors >= MIN_ERRORS_95:
        return tuple(INTERVAL_LEVELS)
    if n_errors >= MIN_ERRORS_50_80:
        return tuple(level for level in INTERVAL_LEVELS if level < 0.95)
    return ()


def _probs_for_levels(levels: Sequence[float]) -> list[float]:
    probs = {round((1 - lvl) / 2, 6) for lvl in levels} | {round((1 + lvl) / 2, 6) for lvl in levels}
    return sorted(probs)


def empirical_quantiles(point: float, past_errors: Sequence[float]) -> dict[float, float]:
    """{prob: point + quantile(errors, prob)} for the available central intervals, else {}."""
    if not math.isfinite(point):
        raise ValueError("point forecast must be finite")
    errors = np.asarray(past_errors, dtype=float)
    errors = errors[~np.isnan(errors)]
    probs = _probs_for_levels(interval_levels_available(len(errors)))
    if not probs:
        return {}
    values = np.quantile(errors, probs, method=QUANTILE_METHOD)
    return {p: float(point + v) for p, v in zip(probs, values)}

"""Input validation and small series helpers shared by the forecasters."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from eco_model.contracts import TARGETS


def validate_history(history: pd.DataFrame) -> None:
    """Raise if `history` does not meet the Forecaster input contract."""
    if not isinstance(history, pd.DataFrame):
        raise TypeError("history must be a pandas DataFrame")
    index = history.index
    if not isinstance(index, pd.PeriodIndex) or not index.freqstr.startswith("Q"):
        raise TypeError("history must have a quarterly PeriodIndex")
    if not index.is_monotonic_increasing or not index.is_unique:
        raise ValueError("history index must be unique and sorted ascending")
    if len(index) > 1 and (index[-1] - index[0]).n != len(index) - 1:
        raise ValueError("history index must hold consecutive quarters; reindex gaps to NaN first")
    unknown = [c for c in history.columns if c not in TARGETS]
    if unknown:
        raise ValueError(f"history has columns that are not targets: {unknown}")


def validate_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
    """Return horizons as a tuple of positive ints, or raise ValueError."""
    values = tuple(horizons)
    if not values:
        raise ValueError("horizons must not be empty")
    for h in values:
        if isinstance(h, bool) or not isinstance(h, (int, np.integer)) or h < 1:
            raise ValueError(f"horizon must be a positive integer, got {h!r}")
    return tuple(int(h) for h in values)


def observed_columns(history: pd.DataFrame) -> list[str]:
    """Columns with at least one observation, in input order."""
    return [c for c in history.columns if history[c].notna().any()]


def trailing_contiguous(series: pd.Series) -> pd.Series:
    """The run of non-NaN values ending at the series' last observation.

    Leading NaNs and anything before an interior gap are discarded, so the
    returned block has no missing quarters.
    """
    values = series.dropna()
    if values.empty:
        return values
    end = series.index.get_loc(values.index[-1])
    start = end
    while start > 0 and pd.notna(series.iloc[start - 1]):
        start -= 1
    return series.iloc[start : end + 1]


def constant_forecasts(target: str, value: float, horizons: Sequence[int]) -> dict[tuple[str, int], float]:
    return {(target, h): float(value) for h in horizons}


def companion_moduli(coefs: np.ndarray) -> np.ndarray:
    """Eigenvalue moduli of the companion matrix of lag coefficients (p, k, k)."""
    p, k, _ = coefs.shape
    companion = np.zeros((k * p, k * p))
    companion[:k, :] = np.hstack(list(coefs))
    if p > 1:
        companion[k:, :-k] = np.eye(k * (p - 1))
    return np.abs(np.linalg.eigvals(companion))

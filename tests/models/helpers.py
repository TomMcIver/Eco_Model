"""Shared builders for model tests (simulated quarterly data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from eco_model.contracts import CPI_INFLATION, GDP_GROWTH, UNEMPLOYMENT

TARGET_COLS = (GDP_GROWTH, CPI_INFLATION, UNEMPLOYMENT)

STABLE_A = np.array([[0.5, 0.1, 0.0], [0.0, 0.4, 0.1], [0.1, 0.0, 0.3]])
STABLE_C = np.array([0.5, 1.0, 1.5])


def make_history(columns: dict, start: str = "1980Q1") -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    index = pd.period_range(start=start, periods=n, freq="Q")
    return pd.DataFrame({k: np.asarray(v, dtype=float) for k, v in columns.items()}, index=index)


def simulate_ar1(n: int, intercept: float, phi: float, seed: int, sd: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.empty(n)
    y[0] = intercept / (1.0 - phi)
    for t in range(1, n):
        y[t] = intercept + phi * y[t - 1] + rng.normal(scale=sd)
    return y


def simulate_var1(n: int, intercept: np.ndarray, coef: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    k = len(intercept)
    mean = np.linalg.solve(np.eye(k) - coef, intercept)
    out = np.empty((n, k))
    out[0] = mean
    for t in range(1, n):
        out[t] = intercept + coef @ out[t - 1] + rng.normal(scale=0.5, size=k)
    return out


def stable_var_history(n: int = 300, seed: int = 1) -> pd.DataFrame:
    data = simulate_var1(n, STABLE_C, STABLE_A, seed)
    return make_history({c: data[:, j] for j, c in enumerate(TARGET_COLS)})

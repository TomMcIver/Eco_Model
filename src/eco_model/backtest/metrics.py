"""Evaluation metrics on identical origin/target pairs (VALIDATION_PLAN "Metrics").

Conventions
-----------
* error = outcome - point (positive bias = forecasts too low on average).
* ``rel_mae_vs_<baseline>`` = MAE(method) / MAE(baseline) on the same pairs;
  < 1 means the method beats the baseline, > 1 means it is worse.
* Every cell (track x segment x target x horizon x outcome kind) is restricted
  to (origin, target_period) pairs scored for EVERY method in the cell; the
  number of common pairs and the exclusions are reported.
* MAE uncertainty: moving-block bootstrap of absolute errors in origin order,
  block length ``max(h, round(n ** (1/3)))`` (h-step errors overlap by h-1
  quarters), percentile CI, fixed seed. ``ess_ar1`` is an AR(1) effective
  sample size n(1-r1)/(1+r1) of the errors - a rough dependence diagnostic.
"""

from __future__ import annotations

from typing import Callable, Mapping

import numpy as np
import pandas as pd

from eco_model.contracts import VintageTrack

BASELINES = ("persistence", "historical_mean")
OUTCOME_KINDS: Mapping[str, tuple[str, str]] = {
    "first_release": ("error_first", "outcome_first"),
    "revised": ("error_revised", "outcome_revised"),
}
POOL_FOR_TRACK = {VintageTrack.REAL_TIME.value: "first_release",
                  VintageTrack.PSEUDO_OOS.value: "revised"}
LEVEL_BOUNDS: Mapping[float, tuple[float, float]] = {
    0.5: (0.25, 0.75), 0.8: (0.10, 0.90), 0.95: (0.025, 0.975),
}
DEFAULT_N_BOOT = 1000
PAIR_KEY = ["origin", "target_period"]


def block_length(n: int, horizon: int) -> int:
    return int(min(max(n, 1), max(int(horizon), int(round(n ** (1.0 / 3.0))), 1)))


def moving_block_bootstrap(
    values, length: int, n_boot: int = DEFAULT_N_BOOT, seed: int = 0,
    stat: Callable[[np.ndarray], float] = np.mean,
) -> np.ndarray:
    """Bootstrap distribution of ``stat`` using overlapping blocks of ``length``."""
    data = np.asarray(values, dtype=float)
    n = len(data)
    if n == 0:
        return np.array([])
    length = int(min(max(length, 1), n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / length))
    starts = rng.integers(0, n - length + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(length)).reshape(n_boot, -1)[:, :n]
    return np.array([stat(data[row]) for row in idx])


def bootstrap_ci(values, length: int, n_boot: int = DEFAULT_N_BOOT, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    if len(values) < 2:
        return float("nan"), float("nan")
    draws = moving_block_bootstrap(values, length, n_boot, seed)
    return float(np.quantile(draws, alpha / 2)), float(np.quantile(draws, 1 - alpha / 2))


def effective_sample_size(errors) -> float:
    data = np.asarray(errors, dtype=float)
    n = len(data)
    if n < 3 or np.std(data) == 0:
        return float(n)
    r1 = float(np.corrcoef(data[:-1], data[1:])[0, 1])
    return float(np.clip(n * (1 - r1) / (1 + r1), 1, n))


def align_pairs(cell: pd.DataFrame, error_col: str) -> tuple[pd.DataFrame, dict]:
    """Restrict ``cell`` to pairs with a valid error for every method in the cell."""
    methods = sorted(cell["method"].unique())
    valid = cell[cell[error_col].notna()]
    keys = {m: set(map(tuple, valid.loc[valid["method"] == m, PAIR_KEY].to_numpy()))
            for m in methods}
    union = set().union(*keys.values()) if keys else set()
    common = set.intersection(*keys.values()) if keys else set()
    in_common = [tuple(k) in common for k in valid[PAIR_KEY].to_numpy()]
    info = {"n_pairs": len(common), "n_pairs_any_method": len(union),
            "n_pairs_excluded": len(union - common),
            "n_valid_by_method": {m: len(k) for m, k in keys.items()}}
    return valid[in_common], info


def point_metrics(errors: pd.Series) -> dict:
    e = errors.to_numpy(dtype=float)
    return {"mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "bias": float(np.mean(e)), "median_ae": float(np.median(np.abs(e)))}


def _quantile(quantiles, prob: float) -> float | None:
    if not isinstance(quantiles, Mapping):
        return None
    for key, value in quantiles.items():
        if abs(float(key) - prob) < 1e-9:
            return float(value)
    return None


def interval_metrics(rows: pd.DataFrame, outcome_col: str) -> dict:
    """Empirical coverage, mean width and count for each predeclared level."""
    out: dict = {}
    for level, (lo_p, hi_p) in LEVEL_BOUNDS.items():
        tag = int(round(level * 100))
        hits, widths = [], []
        for quantiles, outcome in zip(rows["quantiles"], rows[outcome_col]):
            lo, hi = _quantile(quantiles, lo_p), _quantile(quantiles, hi_p)
            if lo is None or hi is None or pd.isna(outcome):
                continue
            hits.append(lo <= outcome <= hi)
            widths.append(hi - lo)
        out[f"coverage_{tag}"] = float(np.mean(hits)) if hits else float("nan")
        out[f"width_{tag}"] = float(np.mean(widths)) if widths else float("nan")
        out[f"n_interval_{tag}"] = len(hits)
    return out


def _method_row(rows, horizon, kind, track, n_boot, seed) -> dict:
    error_col, outcome_col = OUTCOME_KINDS[kind]
    ordered = rows.sort_values("origin")
    errors = ordered[error_col]
    length = block_length(len(errors), horizon)
    lo, hi = bootstrap_ci(np.abs(errors.to_numpy()), length, n_boot, seed)
    row = {**point_metrics(errors), "mae_ci_low": lo, "mae_ci_high": hi,
           "block_length": length, "ess_ar1": effective_sample_size(errors)}
    if "quantiles" in rows and POOL_FOR_TRACK.get(track) == kind:
        row.update(interval_metrics(ordered, outcome_col))
    return row


def _cell_metrics(cell: pd.DataFrame, keys: dict, n_boot: int, seed: int) -> list[dict]:
    out = []
    for kind, (error_col, _) in OUTCOME_KINDS.items():
        aligned, info = align_pairs(cell, error_col)
        if aligned.empty:
            continue
        rows = [{**keys, "outcome": kind, "method": method, "n_pairs": info["n_pairs"],
                 "n_pairs_excluded": info["n_pairs_excluded"],
                 "n_valid_method": info["n_valid_by_method"][method],
                 **_method_row(group, keys["horizon"], kind, keys["track"], n_boot, seed)}
                for method, group in aligned.groupby("method")]
        maes = {r["method"]: r["mae"] for r in rows}
        for r in rows:
            for base in BASELINES:
                denom = maes.get(base)
                r[f"rel_mae_vs_{base}"] = r["mae"] / denom if denom else float("nan")
        out.extend(rows)
    return out


def compute_metrics(frame: pd.DataFrame, n_boot: int = DEFAULT_N_BOOT, seed: int = 0) -> pd.DataFrame:
    """Leaderboard rows per track x segment x target x horizon x outcome x method."""
    data = frame if "segment" in frame else frame.assign(segment="all")
    keys = ["track", "segment", "target", "horizon"]
    rows: list[dict] = []
    for values, cell in data.groupby(keys, sort=True):
        rows.extend(_cell_metrics(cell, dict(zip(keys, values)), n_boot, seed))
    return pd.DataFrame(rows)


def revision_sensitivity(frame: pd.DataFrame) -> pd.DataFrame:
    """MAE vs first release minus MAE vs revised outcome, on rows scored on both."""
    data = frame if "segment" in frame else frame.assign(segment="all")
    both = data[data["error_first"].notna() & data["error_revised"].notna()]
    keys = ["track", "segment", "target", "horizon", "method"]
    rows = []
    for values, g in both.groupby(keys, sort=True):
        mae_first = float(g["error_first"].abs().mean())
        mae_revised = float(g["error_revised"].abs().mean())
        rows.append({**dict(zip(keys, values)), "n": len(g), "mae_first": mae_first,
                     "mae_revised": mae_revised, "mae_first_minus_revised": mae_first - mae_revised,
                     "mean_target_revision": float((g["outcome_revised"] - g["outcome_first"]).mean())})
    return pd.DataFrame(rows)

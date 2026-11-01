"""Issuance-time ensembles and empirical intervals (DEC-005), frozen with no look-ahead.

Eligibility rule shared by weights and intervals: at origin ``o`` a past
forecast's error is usable only if (a) it was issued at an earlier origin on the
same track and (b) the outcome it is scored against was already published by
``o`` (``outcome_available_at <= o``). The error column is the track's own pool:
first-release errors for REAL_TIME, revised-outcome errors for PSEUDO_OOS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from eco_model.contracts import MAX_ERRORS_FOR_WEIGHTS, VintageTrack

ENSEMBLE_EQUAL = "ensemble_equal"
ENSEMBLE_PERF = "ensemble_perf"
PERF_UNAVAILABLE = "performance weighting unavailable"
INTERVAL_UNAVAILABLE = "interval unavailable"

QuantileFn = Callable[[float, pd.Series], Mapping[float, float]]


@dataclass(frozen=True)
class EnsembleFns:
    members: tuple[str, ...]
    equal_weights: Callable[[Sequence[str]], Mapping[str, float]]
    performance_weights: Callable[[pd.DataFrame], "Mapping[str, float] | None"]
    combine: Callable[[Mapping[str, float], Mapping[str, float]], float]


def load_default_ensemble_fns() -> EnsembleFns:
    """Lazy import of eco_model.models.ensemble (kept out of module import time)."""
    from eco_model.models import ensemble

    return EnsembleFns(
        members=tuple(ensemble.ENSEMBLE_MEMBERS),
        equal_weights=ensemble.equal_weights,
        performance_weights=ensemble.performance_weights,
        combine=ensemble.combine,
    )


def load_default_quantile_fn() -> QuantileFn:
    from eco_model.models import intervals

    return intervals.empirical_quantiles


def error_column(track: VintageTrack | str) -> str:
    """The error pool used for weights/intervals on a track."""
    return "error_first" if VintageTrack(track) is VintageTrack.REAL_TIME else "error_revised"


def _eligible(frame: pd.DataFrame, origin: pd.Timestamp, error_col: str) -> pd.Series:
    return (
        (frame["origin"] < origin)
        & (frame["outcome_available_at"] <= origin)
        & frame[error_col].notna()
    )


def eligible_past_errors(
    cell: pd.DataFrame, origin: pd.Timestamp, error_col: str, members: Sequence[str]
) -> pd.DataFrame:
    """Errors known at ``origin`` for one target/horizon: rows = prior origins asc,
    columns = members, restricted to origins where every member has an error."""
    past = cell[_eligible(cell, origin, error_col) & cell["method"].isin(members)]
    if past.empty:
        return pd.DataFrame(columns=list(members), dtype=float)
    wide = past.pivot(index="origin", columns="method", values=error_col)
    return wide.reindex(columns=list(members)).dropna().sort_index()


def _ensemble_row(template: Mapping, method: str, point: float, weights, notes: str) -> dict:
    return {**template, "method": method, "point": float(point),
            "weights": dict(weights), "notes": notes}


def _with_member_notes(notes: str, member_notes: str) -> str:
    """Carry member-level labels (e.g. assumed publication lag) onto ensemble rows."""
    return f"{notes}; {member_notes}" if member_notes else notes


def _cell_ensembles(issued: pd.DataFrame, past: pd.DataFrame, fns: EnsembleFns) -> list[dict]:
    points = dict(zip(issued["method"], issued["point"]))
    if set(points) != set(fns.members) or any(pd.isna(v) for v in points.values()):
        return []
    periods = set(issued["target_period"])
    if len(periods) != 1:
        return []
    keep = ["track", "origin", "target", "horizon", "last_observed", "target_period"]
    template = issued.iloc[0][keep].to_dict()
    member_notes = " | ".join(sorted({str(n) for n in issued["notes"] if n}))
    equal = fns.equal_weights(list(fns.members))
    recent = past.tail(MAX_ERRORS_FOR_WEIGHTS)
    perf = fns.performance_weights(recent)
    if perf is None:
        perf_weights = equal
        perf_note = f"{PERF_UNAVAILABLE} (n_errors={len(recent)}); equal weights used"
    else:
        perf_weights, perf_note = perf, f"performance weights from n_errors={len(recent)}"
    return [
        _ensemble_row(template, ENSEMBLE_EQUAL, fns.combine(points, equal), equal,
                      _with_member_notes("equal weights", member_notes)),
        _ensemble_row(template, ENSEMBLE_PERF, fns.combine(points, perf_weights), perf_weights,
                      _with_member_notes(perf_note, member_notes)),
    ]


def ensemble_rows(frame: pd.DataFrame, fns: EnsembleFns, error_col: str) -> pd.DataFrame:
    """Equal and performance-weighted ensemble rows for every origin/target/horizon."""
    rows: list[dict] = []
    members = frame[frame["method"].isin(fns.members)]
    for (_, _), cell in members.groupby(["target", "horizon"], sort=True):
        for origin, issued in cell.groupby("origin", sort=True):
            past = eligible_past_errors(cell, origin, error_col, fns.members)
            rows.extend(_cell_ensembles(issued, past, fns))
    return pd.DataFrame(rows)


def _row_interval(group: pd.DataFrame, idx, quantile_fn: QuantileFn, error_col: str):
    origin = group.at[idx, "origin"]
    past = group[_eligible(group, origin, error_col)].sort_values("origin")
    errors = pd.Series(past[error_col].to_numpy(), index=past["origin"], dtype=float)
    point = float(group.at[idx, "point"])
    usable = len(errors) > 0 and np.isfinite(point)
    return (dict(quantile_fn(point, errors)) if usable else {}), len(errors)


def add_intervals(frame: pd.DataFrame, quantile_fn: QuantileFn, error_col: str) -> pd.DataFrame:
    """Copy of ``frame`` with ``quantiles`` and ``interval_n_errors`` frozen at issuance."""
    quantiles: dict = {}
    counts: dict = {}
    for _, group in frame.groupby(["method", "target", "horizon"], sort=False):
        for idx in group.index:
            quantiles[idx], counts[idx] = _row_interval(group, idx, quantile_fn, error_col)
    notes = [
        _join_notes(n, INTERVAL_UNAVAILABLE if not quantiles[i] else "")
        for i, n in zip(frame.index, frame["notes"])
    ]
    return frame.assign(
        quantiles=pd.Series(quantiles, dtype=object).reindex(frame.index),
        interval_n_errors=pd.Series(counts).reindex(frame.index).astype(int),
        notes=notes,
    )


def _join_notes(*parts: str) -> str:
    return "; ".join(p for p in parts if isinstance(p, str) and p)

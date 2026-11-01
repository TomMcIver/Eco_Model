"""Quarterly common forecast origins and the development / evaluation split.

VALIDATION_PLAN step 2: the origin for common reference quarter ``q`` is the
latest of the three targets' release times for ``q`` plus a small epsilon, so
every target has ``q`` observed at issuance. The targets are derived from
RAW_SERIES one-to-one, so target availability = raw-series availability.

For the REAL_TIME track build the schedule *without* ``assumed_lag_days`` so
only verified release times define origins. For PSEUDO_OOS an assumed lag may
be supplied; such rows are flagged ``assumed_lag_used``.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from eco_model.backtest.availability import (
    AssumedLagDays,
    AvailableAt,
    make_resolver,
    to_utc,
)
from eco_model.contracts import RAW_SERIES

DEFAULT_EPSILON = pd.Timedelta(minutes=1)
DEVELOPMENT = "development"
EVALUATION = "evaluation"
SCHEDULE_COLUMNS = ("ref_quarter", "origin", "assumed_lag_used")


def common_origin(
    ref_quarter: pd.Period,
    available_at: AvailableAt | None,
    assumed_lag_days: AssumedLagDays | None = None,
    epsilon: pd.Timedelta = DEFAULT_EPSILON,
) -> tuple[pd.Timestamp | None, bool]:
    """(origin, assumed_lag_used) for ``ref_quarter``; origin None if any series unknown."""
    resolve = make_resolver(available_at, assumed_lag_days)
    resolved = [resolve(series_id, ref_quarter) for series_id in RAW_SERIES]
    if any(a.when is None for a in resolved):
        return None, False
    latest = max(a.when for a in resolved)
    return latest + epsilon, any(a.assumed for a in resolved)


def origin_schedule(
    start: pd.Period | str,
    end: pd.Period | str,
    available_at: AvailableAt | None,
    assumed_lag_days: AssumedLagDays | None = None,
    epsilon: pd.Timedelta = DEFAULT_EPSILON,
) -> pd.DataFrame:
    """Common origins for every reference quarter in [start, end].

    Quarters with an unknown release time for any target are omitted (listed in
    ``attrs["unavailable_quarters"]``). Rows are sorted by origin.
    """
    rows = []
    unavailable = []
    for quarter in pd.period_range(pd.Period(start, "Q"), pd.Period(end, "Q"), freq="Q"):
        origin, assumed = common_origin(quarter, available_at, assumed_lag_days, epsilon)
        if origin is None:
            unavailable.append(str(quarter))
            continue
        rows.append({"ref_quarter": quarter, "origin": origin, "assumed_lag_used": assumed})
    schedule = pd.DataFrame(rows, columns=list(SCHEDULE_COLUMNS))
    schedule = schedule.sort_values("origin", kind="stable").reset_index(drop=True)
    schedule.attrs["unavailable_quarters"] = unavailable
    return schedule


def segment_of(origin: datetime | pd.Timestamp, eval_start: datetime | pd.Timestamp) -> str:
    """Origins strictly before ``eval_start`` are development; the rest evaluation."""
    return DEVELOPMENT if to_utc(origin) < to_utc(eval_start) else EVALUATION


def split_schedule(
    schedule: pd.DataFrame, eval_start: datetime | pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split an origin schedule into (development, frozen evaluation) intervals."""
    is_dev = schedule["origin"].map(lambda o: segment_of(o, eval_start) == DEVELOPMENT)
    return schedule[is_dev].reset_index(drop=True), schedule[~is_dev].reset_index(drop=True)


def label_segments(
    frame: pd.DataFrame, eval_start: datetime | pd.Timestamp | None
) -> pd.DataFrame:
    """Return a copy of ``frame`` with a ``segment`` column (``all`` when no cut date)."""
    if eval_start is None:
        return frame.assign(segment="all")
    return frame.assign(segment=frame["origin"].map(lambda o: segment_of(o, eval_start)))

"""When was a raw reference quarter first available to a forecaster?

Two sources, in priority order (DEC-004):

1. A *verified* release time: an injected ``available_at(series_id, ref_period)``
   callable (e.g. a release calendar) or, by default, :class:`StoreAvailability`,
   which reads the first publication time of each reference quarter from the
   vintages held in the ObservationStore.
2. An *assumed* publication lag (``assumed_lag_days(series_id)``), used only
   when no verified time exists. Every use is flagged ``assumed=True`` so the
   caller can label the record; assumed lags are never used silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import pandas as pd

from eco_model.contracts import ObservationStore

AvailableAt = Callable[[str, pd.Period], "datetime | None"]
AssumedLagDays = Callable[[str], "float | int | None"]


def to_utc(value: datetime | pd.Timestamp | str) -> pd.Timestamp:
    """Normalise a timestamp to tz-aware UTC; naive values are taken as UTC."""
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


@dataclass(frozen=True)
class Availability:
    """Resolved availability time of one (series, ref quarter); ``when`` None = unknown."""

    when: pd.Timestamp | None
    assumed: bool = False


def resolve_availability(
    series_id: str,
    period: pd.Period,
    available_at: AvailableAt | None,
    assumed_lag_days: AssumedLagDays | None = None,
) -> Availability:
    """Verified release time if known, else quarter end + assumed lag, else unknown."""
    verified = available_at(series_id, period) if available_at is not None else None
    if verified is not None and not pd.isna(verified):
        return Availability(to_utc(verified), assumed=False)
    if assumed_lag_days is None:
        return Availability(None)
    lag = assumed_lag_days(series_id)
    if lag is None:
        return Availability(None)
    quarter_end = to_utc(period.end_time)
    return Availability(quarter_end + pd.Timedelta(days=float(lag)), assumed=True)


Resolver = Callable[[str, pd.Period], Availability]


def make_resolver(
    available_at: AvailableAt | None, assumed_lag_days: AssumedLagDays | None = None
) -> Resolver:
    """Bind the two availability sources into a single ``(series, period) -> Availability``."""

    def resolve(series_id: str, period: pd.Period) -> Availability:
        return resolve_availability(series_id, period, available_at, assumed_lag_days)

    return resolve


class StoreAvailability:
    """Verified first-publication time per (series, ref quarter) from store vintages.

    Scans ``release_times`` in order and records the first vintage in which each
    reference quarter has a value. Results are cached per series (read-only
    store assumed for the lifetime of this object).
    """

    def __init__(self, store: ObservationStore) -> None:
        self._store = store
        self._cache: dict[str, dict[pd.Period, pd.Timestamp]] = {}

    def first_published(self, series_id: str) -> dict[pd.Period, pd.Timestamp]:
        if series_id not in self._cache:
            self._cache[series_id] = self._scan(series_id)
        return dict(self._cache[series_id])

    def _scan(self, series_id: str) -> dict[pd.Period, pd.Timestamp]:
        seen: dict[pd.Period, pd.Timestamp] = {}
        for release in sorted(self._store.release_times(series_id)):
            vintage = self._store.as_of(series_id, release)
            for period in vintage.dropna().index:
                seen.setdefault(period, to_utc(release))
        return seen

    def __call__(self, series_id: str, period: pd.Period) -> pd.Timestamp | None:
        if series_id not in self._cache:
            self._cache[series_id] = self._scan(series_id)
        return self._cache[series_id].get(period)

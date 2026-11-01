"""Point-in-time information sets for a forecast origin (VALIDATION_PLAN step 3).

* ``REAL_TIME``: each raw series exactly as published by the origin
  (``store.as_of``).
* ``PSEUDO_OOS``: today's revised series (``store.latest``) truncated to the
  reference quarters whose release time (verified, else assumed lag) is at or
  before the origin. Values are revised data, so this track is NOT real-time.

Both tracks pass through a fail-closed leakage guard before transformation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

import pandas as pd

from eco_model.backtest.availability import (
    AssumedLagDays,
    AvailableAt,
    Resolver,
    StoreAvailability,
    make_resolver,
    to_utc,
)
from eco_model.contracts import RAW_SERIES, ObservationStore, VintageTrack
from eco_model.transforms import to_targets


class LeakageError(RuntimeError):
    """An information set contains data that was not available at its origin."""


class InsufficientDataError(ValueError):
    """A raw series has no observations available at the origin."""


@dataclass(frozen=True)
class InfoSet:
    track: VintageTrack
    origin: pd.Timestamp
    raw: Mapping[str, pd.Series]
    targets: pd.DataFrame
    assumed_lag_series: tuple[str, ...] = field(default_factory=tuple)

    @property
    def notes(self) -> str:
        if not self.assumed_lag_series:
            return ""
        return "assumed publication lag used for: " + ", ".join(self.assumed_lag_series)


def assert_no_leakage(
    raw: Mapping[str, pd.Series], origin: pd.Timestamp, resolver: Resolver | None = None
) -> None:
    """Fail closed if any reference quarter could not have been known at ``origin``.

    Always checks that a quarter has ended before the origin. When a resolver
    is given, also checks each quarter's release time is known and <= origin.
    """
    origin = to_utc(origin)
    for series_id, values in raw.items():
        for period in values.dropna().index:
            if to_utc(period.end_time) >= origin:
                raise LeakageError(
                    f"{series_id} {period} has not ended by origin {origin.isoformat()}"
                )
            if resolver is None:
                continue
            when = resolver(series_id, period).when
            if when is None or when > origin:
                shown = "unknown" if when is None else when.isoformat()
                raise LeakageError(
                    f"{series_id} {period} available at {shown}, after origin {origin.isoformat()}"
                )


def _real_time_raw(store: ObservationStore, origin: pd.Timestamp) -> dict[str, pd.Series]:
    return {s: store.as_of(s, origin.to_pydatetime()).sort_index() for s in RAW_SERIES}


def _pseudo_oos_raw(
    store: ObservationStore, origin: pd.Timestamp, resolver: Resolver
) -> tuple[dict[str, pd.Series], tuple[str, ...]]:
    raw: dict[str, pd.Series] = {}
    assumed: list[str] = []
    for series_id in RAW_SERIES:
        revised = store.latest(series_id).sort_index()
        resolved = [resolver(series_id, p) for p in revised.index]
        keep = [a.when is not None and a.when <= origin for a in resolved]
        if any(a.assumed for a, k in zip(resolved, keep) if k):
            assumed.append(series_id)
        raw[series_id] = revised[keep]
    return raw, tuple(assumed)


def _truncate(raw: Mapping[str, pd.Series], cutoff: pd.Period | None) -> dict[str, pd.Series]:
    if cutoff is None:
        return dict(raw)
    return {s: v[v.index <= cutoff] for s, v in raw.items()}


def _require_common_edge(
    raw: Mapping[str, pd.Series], cutoff: pd.Period | None, origin: pd.Timestamp
) -> None:
    """Common-origin protocol: every series must be observed through ``cutoff``.

    A failed ingest or a replaced file can leave one series a quarter short;
    scoring that ragged edge as a common-origin forecast would pool two protocols.
    """
    if cutoff is None:
        return
    short = [s for s, v in raw.items() if v.dropna().index.max() != cutoff]
    if short:
        raise InsufficientDataError(
            f"common origin {origin.isoformat()} needs {cutoff} observed for: {', '.join(short)}"
        )


def build_infoset(
    store: ObservationStore,
    track: VintageTrack,
    origin: datetime | pd.Timestamp,
    *,
    available_at: AvailableAt | None = None,
    assumed_lag_days: AssumedLagDays | None = None,
    cutoff: pd.Period | None = None,
) -> InfoSet:
    """Raw-level information set at ``origin`` for ``track``, transformed to targets.

    ``available_at`` defaults to verified store release times. For REAL_TIME it is
    only used for the leakage check when supplied explicitly. ``cutoff`` (the
    common reference quarter) truncates every series for the common-origin protocol.
    """
    origin_ts = to_utc(origin)
    if track is VintageTrack.REAL_TIME:
        raw = _real_time_raw(store, origin_ts)
        assumed: tuple[str, ...] = ()
        guard = make_resolver(available_at) if available_at is not None else None
    else:
        resolver = make_resolver(available_at or StoreAvailability(store), assumed_lag_days)
        raw, assumed = _pseudo_oos_raw(store, origin_ts, resolver)
        guard = resolver
    raw = _truncate(raw, cutoff)
    assert_no_leakage(raw, origin_ts, guard)
    empty = [s for s, v in raw.items() if v.dropna().empty]
    if empty:
        raise InsufficientDataError(f"no data at {origin_ts.isoformat()} for: {', '.join(empty)}")
    _require_common_edge(raw, cutoff, origin_ts)
    return InfoSet(track, origin_ts, raw, to_targets(raw), assumed)

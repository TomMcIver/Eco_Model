"""Compose the data store, models and backtest into named runs.

This is the only module (with ``cli``) that imports across packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from eco_model.backtest import origin_schedule, run_backtest, write_report
from eco_model.contracts import HORIZONS, RAW_SERIES, VintageTrack
from eco_model.data.statsnz_catalog import assumed_publication_lag_days
from eco_model.data.store import DuckDBObservationStore
from eco_model.models.registry import default_forecasters


class CalendarAvailability:
    """First dated Stats NZ release of each reference quarter, from the release calendar.

    Returns None for quarters released before the archived calendar starts, so
    callers either drop them (real-time track) or fall back to a labelled
    assumed lag (pseudo-out-of-sample track).
    """

    def __init__(self, store: DuckDBObservationStore) -> None:
        self._first: dict[str, dict[pd.Period, pd.Timestamp]] = {}
        self._store = store

    def _table(self, series_id: str) -> dict[pd.Period, pd.Timestamp]:
        if series_id not in self._first:
            calendar = self._store.release_calendar(series_id)
            first = calendar.groupby("ref_period")["published_at"].min()
            self._first[series_id] = dict(first.items())
        return self._first[series_id]

    def __call__(self, series_id: str, period: pd.Period) -> pd.Timestamp | None:
        return self._table(series_id).get(period)

    def coverage_start(self) -> pd.Period | None:
        """Earliest reference quarter with a dated release for every raw series."""
        starts = [min(self._table(s), default=None) for s in RAW_SERIES]
        return None if any(s is None for s in starts) else max(starts)


def _issuable(schedule: pd.DataFrame, calendar: CalendarAvailability,
              now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drop origins that could not have been issued.

    An assumed lag is only a stand-in for releases older than the archived
    calendar; inside the calendar window a missing release means "not yet
    published", and no origin may lie in the future.
    """
    coverage = calendar.coverage_start()
    in_window = schedule["ref_quarter"] >= coverage if coverage is not None else False
    assumed_in_window = in_window & schedule["assumed_lag_used"]
    future = schedule["origin"] > (now if now is not None else pd.Timestamp.now(tz="UTC"))
    kept = schedule.loc[~(assumed_in_window | future)].reset_index(drop=True)
    kept.attrs = dict(schedule.attrs)
    kept.attrs["dropped_origins"] = [
        {"ref_quarter": str(q), "reason": "assumed lag inside release-calendar window" if a else "origin in the future"}
        for q, a in zip(schedule.loc[assumed_in_window | future, "ref_quarter"],
                        assumed_in_window[assumed_in_window | future])
    ]
    return kept


@dataclass(frozen=True)
class BacktestConfig:
    track: VintageTrack
    start: str  # first common reference quarter, e.g. "1995Q1"
    end: str
    eval_start: pd.Timestamp | None
    horizons: tuple[int, ...] = HORIZONS
    seed: int = 0
    n_boot: int = 1000
    now: pd.Timestamp | None = None  # pin the wall clock for reproducible schedules


def run_track(store: DuckDBObservationStore, config: BacktestConfig, out_root: Path) -> Path:
    """Run one vintage track end to end and write its report; returns the report dir."""
    calendar = CalendarAvailability(store)
    # DEC-004: only the pseudo-OOS track may use an assumed publication lag.
    lag = assumed_publication_lag_days if config.track is VintageTrack.PSEUDO_OOS else None
    schedule = _issuable(
        origin_schedule(config.start, config.end, calendar, assumed_lag_days=lag), calendar,
        config.now,
    )
    available_at = calendar if config.track is VintageTrack.PSEUDO_OOS else None
    frame = run_backtest(
        store, config.track, schedule, default_forecasters(), config.horizons,
        available_at=available_at, seed=config.seed, assumed_lag_days=lag,
    )
    meta = {
        "origin_rule": "common origin after latest of the three target releases",
        "availability": "Stats NZ release calendar"
        + ("; assumed lag before archived calendar" if lag else "; verified only"),
        "unavailable_quarters": [str(q) for q in schedule.attrs.get("unavailable_quarters", [])],
        "dropped_origins": schedule.attrs.get("dropped_origins", []),
    }
    return write_report(frame, out_root, eval_start=config.eval_start, meta=meta,
                        n_boot=config.n_boot, seed=config.seed)

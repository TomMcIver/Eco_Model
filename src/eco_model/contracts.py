"""Shared contracts between the data, models, backtest and tax packages.

Every package depends on these types; none of them depends on another
package's internals. Change this file only with a matching ADR note.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping, Protocol, Sequence

import pandas as pd

# Canonical first-slice target identifiers (DEC-001, ticket 006).
GDP_GROWTH = "gdp_growth_qoq_pct"  # q/q % change in SA chain-volume real GDP, not annualised
CPI_INFLATION = "cpi_inflation_yoy_pct"  # y/y % change in all-groups CPI index
UNEMPLOYMENT = "unemployment_rate_sa_pct"  # SA HLFS unemployment rate, percentage points
TARGETS: tuple[str, ...] = (GDP_GROWTH, CPI_INFLATION, UNEMPLOYMENT)

# Raw source series (levels as published) from which targets are derived.
RAW_GDP_LEVEL = "gdp_real_sa_chain_volume"
RAW_CPI_INDEX = "cpi_all_groups_index"
RAW_UNEMPLOYMENT = "hlfs_unemployment_rate_sa"
RAW_SERIES: tuple[str, ...] = (RAW_GDP_LEVEL, RAW_CPI_INDEX, RAW_UNEMPLOYMENT)

HORIZONS: tuple[int, ...] = (1, 4, 8)

# DEC-005 thresholds.
MIN_ERRORS_FOR_WEIGHTS = 20
MAX_ERRORS_FOR_WEIGHTS = 40
MIN_ERRORS_50_80 = 20
MIN_ERRORS_95 = 40
INTERVAL_LEVELS: tuple[float, ...] = (0.5, 0.8, 0.95)


class ValueKind(str, Enum):
    """Preserves the observed / imputed / estimated / simulated distinction."""

    OBSERVED = "observed"
    IMPUTED = "imputed"
    ESTIMATED = "estimated"
    SIMULATED = "simulated"


class VintageTrack(str, Enum):
    """DEC-004: never pool strict real-time and pseudo-out-of-sample scores."""

    REAL_TIME = "real_time"  # every input tied to a release published by the origin
    PSEUDO_OOS = "pseudo_oos_revised"  # current revised data truncated at the origin


@dataclass(frozen=True)
class SourceSnapshot:
    """An immutable retrieved source file (DEC-003 provenance record)."""

    snapshot_id: str  # sha256 of file bytes
    source_id: str  # e.g. "statsnz:gdp:release-2026-09"
    url: str
    retrieved_at: datetime  # UTC
    published_at: datetime | None  # UTC; None when the release time is unverified
    file_path: str  # path of the unchanged raw file relative to data/raw
    sha256: str
    media_type: str
    licence: str
    notes: str = ""


@dataclass(frozen=True)
class Observation:
    """One published value of one series for one reference quarter in one vintage."""

    series_id: str
    ref_period: pd.Period  # quarterly Period, e.g. pd.Period("2024Q1", "Q")
    value: float
    published_at: datetime  # UTC publication time of the vintage this value came from
    snapshot_id: str
    kind: ValueKind = ValueKind.OBSERVED


class ObservationStore(Protocol):
    """Point-in-time read interface implemented by eco_model.data."""

    def as_of(self, series_id: str, as_of: datetime) -> pd.Series:
        """Latest value per ref_period among vintages published at or before `as_of`.

        Returns a float Series indexed by a quarterly PeriodIndex, sorted ascending.
        Must never return a value whose publication time is after `as_of`.
        """
        ...

    def first_release(self, series_id: str) -> pd.Series:
        """Earliest-published value for each ref_period."""
        ...

    def latest(self, series_id: str) -> pd.Series:
        """Most recently published value for each ref_period (revised track)."""
        ...

    def release_times(self, series_id: str) -> list[datetime]:
        """Sorted distinct publication timestamps known for the series."""
        ...


class Forecaster(Protocol):
    """A forecasting method fitted afresh at every origin.

    `history` holds the transformed targets (columns from TARGETS) on a quarterly
    PeriodIndex, containing only information available at the origin. Rows may
    have NaN where a series ends earlier (ragged edge). Implementations must not
    read anything outside `history` and must be deterministic given `seed`.
    """

    name: str

    def forecast(
        self, history: pd.DataFrame, horizons: Sequence[int], seed: int = 0
    ) -> Mapping[tuple[str, int], float]:
        """Return {(target, h): point forecast} for h quarters after each target's last observed quarter."""
        ...


@dataclass(frozen=True)
class ForecastRecord:
    """One issued point forecast (and optional interval) from one method."""

    track: VintageTrack
    origin: datetime  # issue timestamp
    method: str
    target: str
    horizon: int
    last_observed: pd.Period
    target_period: pd.Period
    point: float
    quantiles: Mapping[float, float] = field(default_factory=dict)  # prob -> value
    weights: Mapping[str, float] | None = None  # only for ensembles
    notes: str = ""

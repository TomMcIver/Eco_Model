"""Attach realised outcomes and errors (outcome - point) to forecast rows.

Two outcome definitions are kept separate (VALIDATION_PLAN "Target definitions"):

* ``outcome_first``: the first published value of the target for the target
  quarter. It is computed *within the vintage that first published that quarter*
  (e.g. GDP growth uses the levels for q and q-1 from the same release), which
  avoids mixing base years across vintages. For a level series such as the
  unemployment rate this equals ``store.first_release``.
* ``outcome_revised``: the target computed from ``store.latest`` - the latest
  vintage in the store at run time (recorded as ``revised_as_of``). It is not
  a "final" value.

``outcome_available_at`` is when the track's outcome for the target quarter
was first published (raw series release time), used to decide which past
errors are known at a later origin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import pandas as pd

from eco_model.backtest.availability import Resolver, to_utc
from eco_model.contracts import (
    CPI_INFLATION,
    GDP_GROWTH,
    RAW_CPI_INDEX,
    RAW_GDP_LEVEL,
    RAW_UNEMPLOYMENT,
    UNEMPLOYMENT,
    ObservationStore,
)
from eco_model.transforms import cpi_inflation_yoy, gdp_growth_qoq, to_targets

Transform = Callable[[pd.Series], pd.Series]


def _level(series: pd.Series) -> pd.Series:
    return series.sort_index().astype(float)


TARGET_SOURCES: Mapping[str, tuple[str, Transform]] = {
    GDP_GROWTH: (RAW_GDP_LEVEL, gdp_growth_qoq),
    CPI_INFLATION: (RAW_CPI_INDEX, cpi_inflation_yoy),
    UNEMPLOYMENT: (RAW_UNEMPLOYMENT, _level),
}

OUTCOME_COLUMNS = (
    "outcome_first",
    "outcome_revised",
    "error_first",
    "error_revised",
    "outcome_available_at",
    "outcome_availability_assumed",
)


@dataclass(frozen=True)
class OutcomeTables:
    first: pd.DataFrame  # quarterly PeriodIndex x targets
    revised: pd.DataFrame
    revised_as_of: Mapping[str, str]  # raw series -> latest release time in store (ISO)


def first_release_target(store: ObservationStore, target: str) -> pd.Series:
    """Target value for each quarter as computed in the vintage that first published it."""
    raw_id, transform = TARGET_SOURCES[target]
    first: dict[pd.Period, float] = {}
    for release in sorted(store.release_times(raw_id)):
        vintage = store.as_of(raw_id, release).dropna()
        if vintage.empty:
            continue
        values = transform(vintage).dropna()
        for period, value in values.items():
            first.setdefault(period, float(value))
    return pd.Series(first, dtype=float).sort_index()


def build_outcome_tables(store: ObservationStore) -> OutcomeTables:
    first = pd.concat(
        {target: first_release_target(store, target) for target in TARGET_SOURCES}, axis=1
    )
    revised_raw = {raw_id: store.latest(raw_id) for raw_id, _ in TARGET_SOURCES.values()}
    revised = to_targets(revised_raw)
    as_of = {
        raw_id: (to_utc(max(times)).isoformat() if (times := store.release_times(raw_id)) else "")
        for raw_id in revised_raw
    }
    return OutcomeTables(first=first, revised=revised, revised_as_of=as_of)


def _lookup(table: pd.DataFrame, target: str, period: pd.Period) -> float:
    if target not in table.columns or period not in table.index:
        return float("nan")
    return float(table.at[period, target])


def attach_outcomes(
    frame: pd.DataFrame, tables: OutcomeTables, resolver: Resolver
) -> pd.DataFrame:
    """Return a copy of ``frame`` with outcome, error and availability columns."""
    keys = frame[["target", "target_period"]].drop_duplicates().itertuples(index=False)
    cache = {}
    for target, period in keys:
        availability = resolver(TARGET_SOURCES[target][0], period)
        cache[(target, period)] = (
            _lookup(tables.first, target, period),
            _lookup(tables.revised, target, period),
            availability.when if availability.when is not None else pd.NaT,
            availability.assumed,
        )
    looked = [cache[(t, p)] for t, p in zip(frame["target"], frame["target_period"])]
    first, revised, when, assumed = (list(col) for col in zip(*looked)) if looked else ([],) * 4
    result = frame.drop(columns=[c for c in OUTCOME_COLUMNS if c in frame.columns])
    result = result.assign(
        outcome_first=pd.Series(first, index=frame.index, dtype=float),
        outcome_revised=pd.Series(revised, index=frame.index, dtype=float),
        outcome_available_at=pd.to_datetime(pd.Series(when, index=frame.index), utc=True),
        outcome_availability_assumed=pd.Series(assumed, index=frame.index, dtype=bool),
    )
    return result.assign(
        error_first=result["outcome_first"] - result["point"],
        error_revised=result["outcome_revised"] - result["point"],
    )

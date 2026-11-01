import pandas as pd
import pytest

from eco_model.backtest.availability import (
    StoreAvailability,
    resolve_availability,
    to_utc,
)
from eco_model.backtest.infoset import (
    InsufficientDataError,
    LeakageError,
    assert_no_leakage,
    build_infoset,
)
from eco_model.contracts import (
    GDP_GROWTH,
    RAW_CPI_INDEX,
    RAW_GDP_LEVEL,
    RAW_SERIES,
    RAW_UNEMPLOYMENT,
    VintageTrack,
)

from .conftest import FakeStore, ts

Q = pd.Period


class LeakyStore(FakeStore):
    """as_of ignores the timestamp and returns everything ever published."""

    def as_of(self, series_id, as_of):
        return self.latest(series_id)


def test_real_time_infoset_uses_only_published_vintages(store):
    origin = ts("2003-06-15")

    info = build_infoset(store, VintageTrack.REAL_TIME, origin)

    # GDP lag 70 days: 2003Q1 (ends 31 Mar) published 9 Jun 2003 -> included; Q2 not.
    assert info.raw[RAW_GDP_LEVEL].index.max() == Q("2003Q1", "Q")
    assert info.raw[RAW_CPI_INDEX].index.max() == Q("2003Q1", "Q")
    assert GDP_GROWTH in info.targets.columns
    assert info.notes == ""


def test_real_time_values_are_the_vintage_values_not_revised(store):
    origin = ts("2003-06-15")

    info = build_infoset(store, VintageTrack.REAL_TIME, origin)

    last = info.raw[RAW_GDP_LEVEL].index.max()
    assert info.raw[RAW_GDP_LEVEL][last] != store.latest(RAW_GDP_LEVEL)[last]


def test_leakage_guard_raises_when_store_leaks_future_quarters(store):
    leaky = LeakyStore(store.rows)

    with pytest.raises(LeakageError):
        build_infoset(leaky, VintageTrack.REAL_TIME, ts("2003-06-15"))


def test_leakage_guard_raises_when_release_after_origin():
    raw = {RAW_GDP_LEVEL: pd.Series([1.0], index=pd.PeriodIndex([Q("2003Q1", "Q")]))}

    def late(series_id, period):
        return ts("2003-07-01")

    resolver = lambda s, p: resolve_availability(s, p, late)

    with pytest.raises(LeakageError, match="after origin"):
        assert_no_leakage(raw, ts("2003-06-15"), resolver)


def test_leakage_guard_fails_closed_when_release_time_unknown():
    raw = {RAW_GDP_LEVEL: pd.Series([1.0], index=pd.PeriodIndex([Q("2003Q1", "Q")]))}
    resolver = lambda s, p: resolve_availability(s, p, lambda *_: None)

    with pytest.raises(LeakageError, match="unknown"):
        assert_no_leakage(raw, ts("2003-06-15"), resolver)


def test_real_time_with_explicit_calendar_checks_each_period(store):
    def calendar_says_late(series_id, period):
        return ts("2030-01-01")

    with pytest.raises(LeakageError):
        build_infoset(store, VintageTrack.REAL_TIME, ts("2003-06-15"),
                      available_at=calendar_says_late)


def test_pseudo_oos_truncates_revised_series_by_available_at(store):
    cutoff = {RAW_GDP_LEVEL: Q("2002Q2", "Q"), RAW_CPI_INDEX: Q("2002Q4", "Q"),
              RAW_UNEMPLOYMENT: Q("2002Q3", "Q")}

    def available_at(series_id, period):
        return ts("2003-01-01") if period <= cutoff[series_id] else ts("2004-01-01")

    info = build_infoset(store, VintageTrack.PSEUDO_OOS, ts("2003-06-15"),
                         available_at=available_at)

    for series_id in RAW_SERIES:
        assert info.raw[series_id].index.max() == cutoff[series_id]
        revised = store.latest(series_id)
        pd.testing.assert_series_equal(info.raw[series_id], revised[revised.index <= cutoff[series_id]])


def test_pseudo_oos_falls_back_to_assumed_lag_and_labels_it(store):
    def unverified_gdp(series_id, period):
        if series_id == RAW_GDP_LEVEL:
            return None
        return StoreAvailability(store)(series_id, period)

    info = build_infoset(store, VintageTrack.PSEUDO_OOS, ts("2003-06-15"),
                         available_at=unverified_gdp, assumed_lag_days=lambda s: 100)

    assert info.raw[RAW_GDP_LEVEL].index.max() == Q("2002Q4", "Q")
    assert RAW_GDP_LEVEL in info.notes
    assert "assumed publication lag" in info.notes


def test_pseudo_oos_drops_periods_with_no_availability_information(store):
    with pytest.raises(InsufficientDataError):
        build_infoset(store, VintageTrack.PSEUDO_OOS, ts("2003-06-15"),
                      available_at=lambda s, p: None)


def test_common_cutoff_truncates_all_series(store):
    info = build_infoset(store, VintageTrack.REAL_TIME, ts("2005-01-01"), cutoff=Q("2004Q2", "Q"))

    assert all(v.index.max() == Q("2004Q2", "Q") for v in info.raw.values())


def test_store_availability_returns_first_publication(store):
    availability = StoreAvailability(store)

    when = availability(RAW_CPI_INDEX, Q("2001Q1", "Q"))

    assert when == to_utc(pd.Timestamp(Q("2001Q1", "Q").end_time)) + pd.Timedelta(days=20)
    assert availability(RAW_CPI_INDEX, Q("2099Q1", "Q")) is None
    assert Q("2001Q1", "Q") in availability.first_published(RAW_CPI_INDEX)


def test_resolve_availability_unknown_without_lag():
    result = resolve_availability(RAW_GDP_LEVEL, Q("2001Q1", "Q"), None, lambda s: None)

    assert result.when is None and not result.assumed


def test_common_origin_rejects_a_series_that_lags_the_cutoff(store):
    # At 2004-05-01 GDP (70-day lag) has not yet published 2004Q1 although CPI/HLFS have.
    origin = ts("2004-05-01")

    with pytest.raises(InsufficientDataError, match="needs 2004Q1"):
        build_infoset(store, VintageTrack.REAL_TIME, origin, cutoff=Q("2004Q1", "Q"))


def test_operational_origin_without_cutoff_allows_a_ragged_edge(store):
    info = build_infoset(store, VintageTrack.REAL_TIME, ts("2004-05-01"))

    ends = {s: v.dropna().index.max() for s, v in info.raw.items()}
    assert len(set(ends.values())) > 1

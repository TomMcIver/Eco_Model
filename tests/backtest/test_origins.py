import pandas as pd

from eco_model.backtest.availability import StoreAvailability
from eco_model.backtest.origins import (
    DEFAULT_EPSILON,
    DEVELOPMENT,
    EVALUATION,
    common_origin,
    label_segments,
    origin_schedule,
    split_schedule,
)
from eco_model.contracts import RAW_CPI_INDEX, RAW_GDP_LEVEL

from .conftest import LAG_DAYS, ts

Q = pd.Period


def test_common_origin_is_latest_release_plus_epsilon(store):
    quarter = Q("2002Q1", "Q")

    origin, assumed = common_origin(quarter, StoreAvailability(store))

    gdp_release = pd.Timestamp(quarter.end_time, tz="UTC") + pd.Timedelta(days=LAG_DAYS[RAW_GDP_LEVEL])
    assert origin == gdp_release + DEFAULT_EPSILON
    assert assumed is False


def test_common_origin_none_when_any_series_unknown(store):
    availability = StoreAvailability(store)

    def missing_cpi(series_id, period):
        return None if series_id == RAW_CPI_INDEX else availability(series_id, period)

    assert common_origin(Q("2002Q1", "Q"), missing_cpi) == (None, False)


def test_schedule_flags_assumed_lag_and_lists_unavailable(store):
    availability = StoreAvailability(store)

    schedule = origin_schedule("2010Q1", "2013Q1", availability)
    assumed = origin_schedule("2011Q3", "2011Q4", lambda s, p: None, lambda s: 90)

    assert list(schedule["ref_quarter"])[-1] == Q("2011Q4", "Q")
    assert "2013Q1" in schedule.attrs["unavailable_quarters"]
    assert schedule["origin"].is_monotonic_increasing
    assert assumed["assumed_lag_used"].all()


def test_split_schedule_and_segments(store):
    schedule = origin_schedule("2001Q1", "2004Q4", StoreAvailability(store))
    cut = ts("2003-01-01")

    dev, evaluation = split_schedule(schedule, cut)
    labelled = label_segments(schedule, cut)

    assert len(dev) + len(evaluation) == len(schedule)
    assert (dev["origin"] < cut).all() and (evaluation["origin"] >= cut).all()
    assert set(labelled["segment"]) == {DEVELOPMENT, EVALUATION}
    assert "segment" not in schedule.columns
    assert set(label_segments(schedule, None)["segment"]) == {"all"}

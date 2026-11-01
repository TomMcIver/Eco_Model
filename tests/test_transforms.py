import numpy as np
import pandas as pd
import pytest

from eco_model.contracts import (
    CPI_INFLATION,
    GDP_GROWTH,
    RAW_CPI_INDEX,
    RAW_GDP_LEVEL,
    RAW_UNEMPLOYMENT,
    UNEMPLOYMENT,
)
from eco_model.transforms import cpi_inflation_yoy, gdp_growth_qoq, to_targets


def _q(start: str, values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.period_range(start, periods=len(values), freq="Q"))


def test_gdp_growth_is_quarterly_non_annualised_percent():
    level = _q("2020Q1", [100.0, 101.0, 99.99])

    growth = gdp_growth_qoq(level)

    assert np.isnan(growth.iloc[0])
    assert growth.iloc[1] == pytest.approx(1.0)
    assert growth.iloc[2] == pytest.approx(-1.0)


def test_gdp_growth_does_not_bridge_a_missing_quarter():
    level = _q("2020Q1", [100.0, 110.0, 121.0]).drop(pd.Period("2020Q2", "Q"))

    growth = gdp_growth_qoq(level)

    assert np.isnan(growth[pd.Period("2020Q3", "Q")])


def test_cpi_inflation_is_year_on_year_percent():
    index = _q("2020Q1", [100.0, 100.5, 101.0, 101.5, 103.0])

    inflation = cpi_inflation_yoy(index)

    assert inflation.iloc[:4].isna().all()
    assert inflation.iloc[4] == pytest.approx(3.0)


def test_to_targets_keeps_ragged_edge_and_unordered_inputs():
    raw = {
        RAW_GDP_LEVEL: _q("2020Q1", [100.0, 101.0, 102.0]).iloc[::-1],
        RAW_CPI_INDEX: _q("2020Q1", [100.0, 100.0, 100.0, 100.0, 102.0, 103.0]),
        RAW_UNEMPLOYMENT: _q("2020Q1", [4.0, 4.1, 4.2, 4.3, 4.4, 4.5]),
    }

    targets = to_targets(raw)

    assert list(targets.columns) == [GDP_GROWTH, CPI_INFLATION, UNEMPLOYMENT]
    assert targets.loc[pd.Period("2020Q2", "Q"), GDP_GROWTH] == pytest.approx(1.0)
    assert np.isnan(targets.loc[pd.Period("2021Q2", "Q"), GDP_GROWTH])
    assert targets.loc[pd.Period("2021Q2", "Q"), CPI_INFLATION] == pytest.approx(3.0)
    assert targets.index.min() == pd.Period("2020Q1", "Q")


def test_to_targets_index_is_sorted_when_series_cover_different_ranges():
    raw = {
        RAW_GDP_LEVEL: _q("2010Q1", [100.0, 101.0, 102.0]),
        RAW_CPI_INDEX: _q("2000Q1", [100.0 + i for i in range(48)]),
        RAW_UNEMPLOYMENT: _q("2005Q1", [4.0] * 30),
    }

    targets = to_targets(raw)

    assert targets.index.is_monotonic_increasing
    assert targets.index.is_unique


def test_zero_index_levels_are_missing_not_real_values():
    index = _q("2000Q1", [100.0, 0.0, 0.0, 0.0, 0.0, 104.0])

    inflation = cpi_inflation_yoy(index)

    assert inflation.isna().all()  # every y/y pair touches a zero (missing) level


def test_zero_level_does_not_create_minus_100_percent_growth():
    level = _q("2000Q1", [100.0, 0.0, 102.0])

    growth = gdp_growth_qoq(level)

    assert growth.isna().all()

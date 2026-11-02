"""Raw published levels -> canonical forecast targets (ticket 006)."""

from __future__ import annotations

import pandas as pd

from eco_model.contracts import (
    CPI_INFLATION,
    GDP_GROWTH,
    RAW_CPI_INDEX,
    RAW_GDP_LEVEL,
    RAW_UNEMPLOYMENT,
    UNEMPLOYMENT,
)


def _contiguous(series: pd.Series) -> pd.Series:
    """Reindex onto every quarter so shifts compare true calendar neighbours.

    Non-positive levels are treated as missing: Stats NZ files use 0 as a
    "not collected" marker in early history (e.g. CPI before 1925), and a zero
    index level would otherwise yield -100% / infinite changes.
    """
    if series.empty:
        return series.astype(float)
    series = series.where(series > 0)
    full = pd.period_range(series.index.min(), series.index.max(), freq="Q")
    return series.sort_index().reindex(full)


def gdp_growth_qoq(level: pd.Series) -> pd.Series:
    """Quarter-on-quarter % change, not annualised."""
    level = _contiguous(level)
    return (level / level.shift(1) - 1.0) * 100.0


def cpi_inflation_yoy(index: pd.Series) -> pd.Series:
    """Year-on-year % change of a quarterly index."""
    index = _contiguous(index)
    return (index / index.shift(4) - 1.0) * 100.0


def to_targets(raw: dict[str, pd.Series]) -> pd.DataFrame:
    """Build the target frame from raw level series on quarterly PeriodIndexes.

    Each series is transformed on its own index before alignment, so a gap in
    one series never shifts another's transformation.
    """
    columns = {
        GDP_GROWTH: gdp_growth_qoq(raw[RAW_GDP_LEVEL].sort_index()),
        CPI_INFLATION: cpi_inflation_yoy(raw[RAW_CPI_INDEX].sort_index()),
        UNEMPLOYMENT: raw[RAW_UNEMPLOYMENT].sort_index().astype(float),
    }
    frame = pd.concat(columns, axis=1).sort_index()
    frame = frame.dropna(how="all")
    if frame.empty:
        return frame
    # keep interior quarters where every target is missing as NaN rows, so the index stays consecutive
    return frame.reindex(pd.period_range(frame.index.min(), frame.index.max(), freq="Q"))

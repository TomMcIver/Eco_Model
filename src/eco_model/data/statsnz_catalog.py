"""Verified Stats NZ source mapping for the three first-slice raw series.

Every identifier below was checked against the official release downloads on
stats.govt.nz on 2026-10-29 (see data/SOURCES.md for the evidence trail).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from eco_model.contracts import RAW_CPI_INDEX, RAW_GDP_LEVEL, RAW_UNEMPLOYMENT

BASE_URL = "https://www.stats.govt.nz"
RELEASE_URL = BASE_URL + "/information-releases/{slug}/"
MONTHS = {1: "march", 2: "june", 3: "september", 4: "december"}
# Stats NZ information releases go out at 10:45 NZ time; the release pages carry
# "PublicationDate": "YYYY-MM-DD 10:45:00" (verified on every page parsed).
FIRST_ARCHIVED_RELEASE = pd.Period("2017Q1", freq="Q")  # earliest pages online (GDP)


@dataclass(frozen=True)
class StatsNZSeries:
    series_id: str  # contracts.RAW_* identifier
    series_ref: str  # Stats NZ Infoshare series reference in the CSV downloads
    release_prefix: str  # information-release slug prefix
    description: str
    units: str
    magnitude: str
    seasonal_adjustment: str
    group: str  # 'Group' column text verified in the download
    file_preference: tuple[str, ...]  # substrings ranking download links (first wins)
    file_exclude: tuple[str, ...]


STATSNZ_SERIES: dict[str, StatsNZSeries] = {
    RAW_GDP_LEVEL: StatsNZSeries(
        series_id=RAW_GDP_LEVEL,
        series_ref="SNEQ.SG01RSC00B01",
        release_prefix="gross-domestic-product",
        description="Gross Domestic Product - production measure, chain volume, "
        "seasonally adjusted, total (quarterly)",
        units="NZD (chain-volume, prices of the reference year); MAGNITUDE=6 so values are NZ$ millions",
        magnitude="millions",
        seasonal_adjustment="seasonally adjusted",
        group="Series, GDP(P), Chain volume, Seasonally adjusted, Total",
        file_preference=(".csv", ".zip"),
        file_exclude=("visualisation", "supplementary"),
    ),
    RAW_CPI_INDEX: StatsNZSeries(
        series_id=RAW_CPI_INDEX,
        series_ref="CPIQ.SE9A",
        release_prefix="consumers-price-index",
        description="Consumers price index, All groups for New Zealand (quarterly)",
        units="Index (base June 2017 quarter = 1000)",
        magnitude="units",
        seasonal_adjustment="not seasonally adjusted",
        group="CPI All Groups for New Zealand",
        file_preference=("index-numbers", ".zip", "corrections"),
        file_exclude=("seasonally-adjusted", "tradables", "tradeables", "infoshare", "data-vis"),
    ),
    RAW_UNEMPLOYMENT: StatsNZSeries(
        series_id=RAW_UNEMPLOYMENT,
        series_ref="HLFQ.S1F3S",
        release_prefix="labour-market-statistics",
        description="Household Labour Force Survey, unemployment rate, total both sexes, "
        "seasonally adjusted (quarterly)",
        units="Percent of labour force",
        magnitude="units",
        seasonal_adjustment="seasonally adjusted",
        group="Labour Force Status by Sex: Seasonally Adjusted",
        file_preference=(".zip",),
        file_exclude=(),
    ),
}


def release_slug(spec: StatsNZSeries, quarter: pd.Period) -> str:
    """Information-release slug for the release whose latest quarter is `quarter`."""
    return f"{spec.release_prefix}-{MONTHS[quarter.quarter]}-{quarter.year}-quarter"


def release_url(spec: StatsNZSeries, quarter: pd.Period) -> str:
    return RELEASE_URL.format(slug=release_slug(spec, quarter))


def rank_links(spec: StatsNZSeries, links: list[str]) -> list[str]:
    """Order a release's download links by preference, dropping excluded ones."""
    candidates = [
        link for link in links
        if not any(word in link.lower() for word in spec.file_exclude)
        and link.lower().endswith((".csv", ".zip"))
    ]

    def score(link: str) -> int:
        lowered = link.lower()
        hits = [i for i, word in enumerate(spec.file_preference) if word in lowered]
        return hits[0] if hits else len(spec.file_preference)

    return sorted(candidates, key=lambda link: (score(link), link))


# ESTIMATED approximate publication lags (days after reference-quarter end).
# Derived from the 2024-2026 release dates verified on the release pages
# (GDP: 2026-09-17 for Q2 = 79 days; CPI: 2026-10-22 for Q3 = 22 days;
# HLFS: 2026-08-05 for Q2 = 36 days). Use only when no dated release exists;
# the release_calendar table is the authoritative source.
_ASSUMED_LAG_DAYS = {RAW_GDP_LEVEL: 80, RAW_CPI_INDEX: 21, RAW_UNEMPLOYMENT: 37}
LAG_STATUS = "ESTIMATED"


def assumed_publication_lag_days(series_id: str) -> int:
    """ESTIMATED typical lag; prefer DuckDBObservationStore.release_calendar."""
    if series_id not in _ASSUMED_LAG_DAYS:
        raise KeyError(f"no assumed publication lag for {series_id!r}")
    return _ASSUMED_LAG_DAYS[series_id]

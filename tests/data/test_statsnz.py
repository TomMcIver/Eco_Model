"""Release ingestion end-to-end against a fake Stats NZ site built from real excerpts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from eco_model.contracts import RAW_CPI_INDEX, RAW_GDP_LEVEL, RAW_UNEMPLOYMENT
from eco_model.data.ingest import ingest_all, main, release_quarters
from eco_model.data.statsnz import ingest_release, vintage_time
from eco_model.data.statsnz_catalog import (
    BASE_URL,
    STATSNZ_SERIES,
    assumed_publication_lag_days,
    rank_links,
    release_slug,
    release_url,
)
from eco_model.data.store import DuckDBObservationStore

from .conftest import FakeResponse, FakeSession

UTC = timezone.utc
Q2 = pd.Period("2026Q2", freq="Q")
RELEASE_AT = datetime(2026, 9, 16, 22, 45, tzinfo=UTC)
GDP_LINK = ("/assets/Uploads/Gross-domestic-product/Gross-domestic-product-June-2026-quarter/"
            "Download-data/gross-domestic-product-june-2026-quarter.csv")
VIS_LINK = GDP_LINK.replace(".csv", "-visualisation.csv")


def _site(fixtures_dir, last_modified="Wed, 16 Sep 2026 22:45:17 GMT", csv_name=None):
    page = (fixtures_dir / "gdp_june_2026_release_page.html").read_bytes()
    csv = (fixtures_dir / (csv_name or "gdp_june_2026_excerpt.csv")).read_bytes()
    return FakeSession({
        release_url(STATSNZ_SERIES[RAW_GDP_LEVEL], Q2): FakeResponse(200, page, {"Content-Type": "text/html"}),
        BASE_URL + VIS_LINK: FakeResponse(200, b"Series_reference,Period\n", {}),
        BASE_URL + GDP_LINK: FakeResponse(200, csv, {"Content-Type": "application/octet-stream",
                                                     "Last-Modified": last_modified}),
    })


def test_ingest_release_loads_as_released_vintage(fixtures_dir, tmp_path):
    # Arrange
    session = _site(fixtures_dir)
    # Act
    with DuckDBObservationStore(":memory:") as store:
        result = ingest_release(store, STATSNZ_SERIES[RAW_GDP_LEVEL], Q2, tmp_path, session)
        latest = store.latest(RAW_GDP_LEVEL)
        before = store.as_of(RAW_GDP_LEVEL, RELEASE_AT - timedelta(seconds=1))
        calendar = store.release_calendar(RAW_GDP_LEVEL)
        snaps = store.snapshots()
    # Assert
    assert result.status == "ingested" and result.observations == 12
    assert result.vintage_at == RELEASE_AT and latest[Q2] == 71805.0
    assert before.empty  # fail-closed: nothing visible before 10:45 NZ release
    assert list(calendar["ref_period"]) == [Q2]
    assert {s.published_at for s in snaps} == {RELEASE_AT}
    assert BASE_URL + VIS_LINK not in session.calls  # visualisation file is excluded


def test_replaced_file_uses_later_last_modified(fixtures_dir, tmp_path):
    session = _site(fixtures_dir, last_modified="Sun, 27 Sep 2026 21:06:40 GMT")
    with DuckDBObservationStore(":memory:") as store:
        result = ingest_release(store, STATSNZ_SERIES[RAW_GDP_LEVEL], Q2, tmp_path, session)
        visible_at_release = store.as_of(RAW_GDP_LEVEL, RELEASE_AT + timedelta(days=1))
        calendar = store.release_calendar(RAW_GDP_LEVEL)
    assert result.vintage_at == datetime(2026, 9, 27, 21, 6, 40, tzinfo=UTC)
    assert visible_at_release.empty
    assert calendar["published_at"].iloc[0] == pd.Timestamp(RELEASE_AT)


def test_missing_page_reported_as_no_page(tmp_path):
    with DuckDBObservationStore(":memory:") as store:
        result = ingest_release(store, STATSNZ_SERIES[RAW_GDP_LEVEL], Q2, tmp_path, FakeSession({}))
    assert result.status == "no_page" and "404" in result.detail


def test_file_without_series_reported(fixtures_dir, tmp_path):
    session = _site(fixtures_dir, csv_name="cpi_september_2026_index_numbers_excerpt.csv")
    with DuckDBObservationStore(":memory:") as store:
        result = ingest_release(store, STATSNZ_SERIES[RAW_GDP_LEVEL], Q2, tmp_path, session)
        assert store.latest(RAW_GDP_LEVEL).empty
    assert result.status == "no_usable_file" and "not found" in result.detail


def test_file_ending_at_wrong_quarter_fails_closed(fixtures_dir, tmp_path):
    session = _site(fixtures_dir)
    q1 = pd.Period("2026Q1", freq="Q")
    session.routes[release_url(STATSNZ_SERIES[RAW_GDP_LEVEL], q1)] = session.routes[
        release_url(STATSNZ_SERIES[RAW_GDP_LEVEL], Q2)]
    with DuckDBObservationStore(":memory:") as store:
        result = ingest_release(store, STATSNZ_SERIES[RAW_GDP_LEVEL], q1, tmp_path, session)
        assert store.latest(RAW_GDP_LEVEL).empty
    assert result.status == "failed" and "!=" in result.detail


def test_vintage_time_rules():
    assert vintage_time(RELEASE_AT, None)[0] == RELEASE_AT
    assert vintage_time(RELEASE_AT, RELEASE_AT - timedelta(days=2))[0] == RELEASE_AT
    later = RELEASE_AT + timedelta(hours=2)
    assert vintage_time(RELEASE_AT, later) == (later, vintage_time(RELEASE_AT, later)[1])


def test_catalog_helpers():
    spec = STATSNZ_SERIES[RAW_CPI_INDEX]
    links = ["/a/cpi-seasonally-adjusted.csv", "/a/cpi.zip", "/a/cpi-index-numbers.csv", "/a/x.xls"]
    assert rank_links(spec, links) == ["/a/cpi-index-numbers.csv", "/a/cpi.zip"]
    assert release_slug(STATSNZ_SERIES[RAW_UNEMPLOYMENT], Q2) == "labour-market-statistics-june-2026-quarter"
    assert assumed_publication_lag_days(RAW_GDP_LEVEL) == 80
    with pytest.raises(KeyError):
        assumed_publication_lag_days("nope")


def test_ingest_all_with_fake_site(fixtures_dir, tmp_path):
    # Act
    report = ingest_all(tmp_path / "db.duckdb", tmp_path / "raw", series=[RAW_GDP_LEVEL],
                        since=Q2, until=pd.Period("2026Q3", freq="Q"),
                        session=_site(fixtures_dir), store_dir=tmp_path / "store", pause_s=0)
    # Assert
    assert [r.status for r in report.results] == ["ingested", "no_page"]
    assert report.summaries[0].last_period == "2026Q2" and report.summaries[0].vintages == 1
    assert not report.problems() and "ingested" in report.format()
    assert (tmp_path / "store" / "observations.parquet").exists()
    assert release_quarters(Q2, Q2) == [Q2]


def test_main_cli_runs_against_fake_site(fixtures_dir, tmp_path, monkeypatch):
    monkeypatch.setattr("eco_model.data.ingest.default_session", lambda: _site(fixtures_dir))
    code = main(["--db", str(tmp_path / "d.duckdb"), "--raw-dir", str(tmp_path / "raw"),
                 "--store-dir", str(tmp_path / "s"), "--since", "2026Q2", "--until", "2026Q2",
                 "--series", RAW_GDP_LEVEL])
    assert code == 0

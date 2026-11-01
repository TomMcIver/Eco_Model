"""Parsers against excerpts of the real Stats NZ downloads (tests/data/fixtures)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from eco_model.data.statsnz_parse import (
    ParseError,
    extract_series,
    parse_release_page,
    period_from_statsnz,
)

Q = lambda s: pd.Period(s, freq="Q")  # noqa: E731


def test_release_page_publication_time_is_1045_nz(fixtures_dir):
    # Arrange
    raw = (fixtures_dir / "gdp_june_2026_release_page.html").read_bytes()
    # Act
    page = parse_release_page(raw)
    # Assert: 17 Sep 2026 10:45 NZST (UTC+12) == 16 Sep 22:45 UTC
    assert page.published_local == "2026-09-17 10:45:00"
    assert page.published_at == datetime(2026, 9, 16, 22, 45, tzinfo=timezone.utc)
    assert any(link.endswith("gross-domestic-product-june-2026-quarter.csv") for link in page.links)


def test_release_page_without_date_rejected():
    with pytest.raises(ParseError):
        parse_release_page(b"<html>nothing here</html>")


def test_gdp_csv_excerpt(fixtures_dir):
    raw = (fixtures_dir / "gdp_june_2026_excerpt.csv").read_bytes()
    rows = extract_series(raw, "gdp.csv", "SNEQ.SG01RSC00B01")
    assert rows["ref_period"].iloc[-1] == Q("2026Q2")
    assert rows["value"].iloc[-1] == 71805.0
    assert len(rows) == 12
    assert set(rows["group"]) == {"Series, GDP(P), Chain volume, Seasonally adjusted, Total"}


def test_cpi_csv_excerpt(fixtures_dir):
    raw = (fixtures_dir / "cpi_september_2026_index_numbers_excerpt.csv").read_bytes()
    rows = extract_series(raw, "cpi.csv", "CPIQ.SE9A")
    assert rows.set_index("ref_period")["value"][Q("2026Q3")] == 1368.0
    assert rows["ref_period"].is_monotonic_increasing


def test_hlfs_zip_excerpt(fixtures_dir):
    raw = (fixtures_dir / "lms_june_2026_excerpt.zip").read_bytes()
    rows = extract_series(raw, "lms.zip", "HLFQ.S1F3S")
    assert rows.set_index("ref_period")["value"][Q("2026Q2")] == 5.6
    assert rows["member"].iloc[0].endswith("hlfs-jun26qtr-csv.csv")


def test_missing_series_raises(fixtures_dir):
    raw = (fixtures_dir / "gdp_june_2026_excerpt.csv").read_bytes()
    with pytest.raises(ParseError, match="not found"):
        extract_series(raw, "gdp.csv", "NOPE.X")


def test_empty_values_dropped_and_conflicts_rejected():
    ok = b"Series_reference,Period,Data_value,STATUS\nA,2020.03,1.5,F\nA,2020.06,,F\nA,2020.06,,F\n"
    rows = extract_series(ok, "a.csv", "A")
    assert list(rows["ref_period"]) == [Q("2020Q1")]
    clash = b"Series_reference,Period,Data_value,STATUS\nA,2020.03,1.5,F\nA,2020.03,1.6,F\n"
    with pytest.raises(ParseError, match="conflicting"):
        extract_series(clash, "a.csv", "A")


def test_non_infoshare_csv_ignored():
    with pytest.raises(ParseError):
        extract_series(b"foo,bar\n1,2\n", "x.csv", "A")


@pytest.mark.parametrize("code,expected", [("2026.06", "2026Q2"), ("1987.03", "1987Q1"),
                                           ("2000.12", "2000Q4")])
def test_period_codes(code, expected):
    assert period_from_statsnz(code) == Q(expected)


@pytest.mark.parametrize("code", ["2026.05", "2026", "2026Q1", "abc"])
def test_bad_period_codes(code):
    with pytest.raises(ParseError):
        period_from_statsnz(code)


def _zip(members: dict[str, bytes]) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_case_colliding_columns_and_nested_zip():
    # Arrange: 2019-era HLFS files have both "Age group" and "Age Group" columns,
    # and the June 2021 release wraps its CSVs in a zip inside the zip.
    csv = (b"STATUS,Series_reference,Period,Data_value,Group,Age group,Age Group\n"
           b"FINAL,HLFQ.S1F3S,2021.06,4.0,G,a,b\n")
    inner = _zip({"hlfs.csv": csv, "notes.txt": b"x"})
    outer = _zip({"inner.zip": inner})
    # Act
    rows = extract_series(outer, "outer.zip", "HLFQ.S1F3S")
    # Assert
    assert list(rows["value"]) == [4.0] and rows["member"].iloc[0] == "hlfs.csv"

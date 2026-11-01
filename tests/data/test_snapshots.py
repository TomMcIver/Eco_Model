"""Raw snapshot immutability, dedup and provenance."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from eco_model.data.snapshots import (
    SnapshotIntegrityError,
    extension_for,
    fetch_snapshot,
    last_modified,
    read_raw,
    register_local_file,
    sha256_hex,
    source_dir_name,
    with_published_at,
    write_raw_once,
)
from eco_model.data.timeutil import NaiveDatetimeError

from .conftest import FakeResponse, FakeSession

URL = "https://www.stats.govt.nz/assets/Uploads/x/file.csv"
HEADERS = {"Content-Type": "text/csv", "ETag": '"abc"',
           "Last-Modified": "Wed, 16 Sep 2026 22:45:17 GMT", "Set-Cookie": "secret"}


def test_fetch_writes_unchanged_bytes_under_sha_path(tmp_path):
    # Arrange
    session = FakeSession({URL: FakeResponse(200, b"a,b\n1,2\n", HEADERS)})
    # Act
    snap, content = fetch_snapshot(URL, "statsnz:gdp:2026Q2", tmp_path, session=session)
    # Assert
    digest = sha256_hex(b"a,b\n1,2\n")
    assert snap.file_path == f"statsnz_gdp/{digest}.csv"
    assert (tmp_path / snap.file_path).read_bytes() == content == b"a,b\n1,2\n"
    assert snap.sha256 == snap.snapshot_id == digest
    assert snap.retrieved_at.tzinfo is not None and snap.published_at is None
    notes = json.loads(snap.notes)["headers"]
    assert notes["ETag"] == '"abc"' and "Set-Cookie" not in notes


def test_refetch_identical_bytes_does_not_duplicate(tmp_path):
    session = FakeSession({URL: FakeResponse(200, b"same", HEADERS)})
    first, _ = fetch_snapshot(URL, "statsnz:gdp:x", tmp_path, session=session)
    second, _ = fetch_snapshot(URL, "statsnz:gdp:x", tmp_path, session=session)
    assert first.file_path == second.file_path
    assert len(list((tmp_path / "statsnz_gdp").iterdir())) == 1


def test_changed_bytes_create_new_snapshot_without_overwrite(tmp_path):
    old, _ = fetch_snapshot(URL, "statsnz:gdp:x", tmp_path,
                            session=FakeSession({URL: FakeResponse(200, b"v1", HEADERS)}))
    new, _ = fetch_snapshot(URL, "statsnz:gdp:x", tmp_path,
                            session=FakeSession({URL: FakeResponse(200, b"v2", HEADERS)}))
    assert old.snapshot_id != new.snapshot_id
    assert (tmp_path / old.file_path).read_bytes() == b"v1"
    assert (tmp_path / new.file_path).read_bytes() == b"v2"


def test_fetch_http_error_raises_and_writes_nothing(tmp_path):
    with pytest.raises(Exception):
        fetch_snapshot(URL, "statsnz:gdp:x", tmp_path, session=FakeSession({}))
    assert not any(tmp_path.iterdir())


def test_tampered_raw_file_detected(tmp_path):
    rel = write_raw_once(b"good", tmp_path, "s:d", "csv")
    (tmp_path / rel).write_bytes(b"evil")
    with pytest.raises(SnapshotIntegrityError):
        write_raw_once(b"good", tmp_path, "s:d", "csv")


def test_register_local_file_and_read_back(tmp_path):
    # Arrange
    local = tmp_path / "manual" / "download.xlsx"
    local.parent.mkdir()
    local.write_bytes(b"PK fake workbook")
    published = datetime(2026, 9, 16, 22, 45, tzinfo=timezone.utc)
    # Act
    snap = register_local_file(local, "statsnz:manual:2026Q2", tmp_path / "raw",
                               url="https://example.test/manual", published_at=published,
                               notes="browser download")
    # Assert
    assert snap.file_path.endswith(".xlsx") and snap.published_at == published
    assert read_raw(snap, tmp_path / "raw") == b"PK fake workbook"
    assert json.loads(snap.notes)["manual_registration"] is True


def test_register_rejects_naive_publication_time(tmp_path):
    local = tmp_path / "f.csv"
    local.write_bytes(b"x")
    with pytest.raises(NaiveDatetimeError):
        register_local_file(local, "s:d", tmp_path, url="u", published_at=datetime(2026, 1, 1))


def test_read_raw_detects_checksum_mismatch(tmp_path):
    local = tmp_path / "f.csv"
    local.write_bytes(b"x")
    snap = register_local_file(local, "s:d", tmp_path / "raw", url="u")
    (tmp_path / "raw" / snap.file_path).write_bytes(b"y")
    with pytest.raises(SnapshotIntegrityError):
        read_raw(snap, tmp_path / "raw")


def test_last_modified_parsed_from_notes(tmp_path):
    session = FakeSession({URL: FakeResponse(200, b"z", HEADERS)})
    snap, _ = fetch_snapshot(URL, "s:d", tmp_path, session=session)
    assert last_modified(snap) == datetime(2026, 9, 16, 22, 45, 17, tzinfo=timezone.utc)
    assert last_modified(replace(snap, notes="not json")) is None
    assert with_published_at(snap, None).published_at is None


def test_helpers():
    assert source_dir_name("statsnz:gdp-release-page:2026Q2") == "statsnz_gdp-release-page"
    assert extension_for("https://x/y/page/", "text/html; charset=utf-8") == "html"
    assert extension_for("https://x/y/file.ZIP") == "zip"

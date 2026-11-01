"""Point-in-time correctness of DuckDBObservationStore with synthetic vintages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from eco_model.contracts import Observation, ObservationStore, SourceSnapshot
from eco_model.data.store import DuckDBObservationStore, ReleaseEntry, period_text
from eco_model.data.timeutil import NaiveDatetimeError

UTC = timezone.utc
SERIES = "gdp_real_sa_chain_volume"
T1 = datetime(2024, 3, 21, 21, 45, tzinfo=UTC)  # vintage 1
T2 = datetime(2024, 6, 20, 22, 45, tzinfo=UTC)  # vintage 2 revises 2023Q4
Q = lambda s: pd.Period(s, freq="Q")  # noqa: E731


def _snapshot(sid: str, published: datetime | None) -> SourceSnapshot:
    return SourceSnapshot(sid, f"test:{sid}", f"https://example.test/{sid}", T2 + timedelta(days=1),
                          published, f"test/{sid}.csv", sid, "text/csv", "CC BY 4.0 Stats NZ")


def _obs(period: str, value: float, published: datetime, sid: str) -> Observation:
    return Observation(SERIES, Q(period), value, published, sid)


@pytest.fixture
def store() -> DuckDBObservationStore:
    db = DuckDBObservationStore(":memory:")
    db.add_snapshot(_snapshot("v1", T1))
    db.add_snapshot(_snapshot("v2", T2))
    db.add_observations([_obs("2023Q3", 100.0, T1, "v1"), _obs("2023Q4", 101.0, T1, "v1")])
    db.add_observations([
        _obs("2023Q3", 100.0, T2, "v2"), _obs("2023Q4", 101.5, T2, "v2"),
        _obs("2024Q1", 102.0, T2, "v2"),
    ])
    yield db
    db.close()


def test_store_satisfies_protocol(store):
    # Arrange / Act
    candidate: ObservationStore = store
    # Assert
    assert hasattr(candidate, "as_of") and hasattr(candidate, "release_times")


def test_as_of_before_any_release_is_empty(store):
    result = store.as_of(SERIES, T1 - timedelta(seconds=1))
    assert result.empty


def test_as_of_never_returns_values_published_later(store):
    # Act: one second before vintage 2
    result = store.as_of(SERIES, T2 - timedelta(seconds=1))
    # Assert: only vintage-1 values, no 2024Q1, unrevised 2023Q4
    assert list(result.index) == [Q("2023Q3"), Q("2023Q4")]
    assert result[Q("2023Q4")] == 101.0


def test_as_of_includes_release_at_exact_timestamp(store):
    result = store.as_of(SERIES, T2)
    assert result[Q("2023Q4")] == 101.5
    assert result.index.max() == Q("2024Q1")


def test_as_of_converts_other_timezones(store):
    nz = timezone(timedelta(hours=12))
    result = store.as_of(SERIES, (T2 - timedelta(seconds=1)).astimezone(nz))
    assert Q("2024Q1") not in result.index


def test_first_release_and_latest_differ_after_revision(store):
    first, latest = store.first_release(SERIES), store.latest(SERIES)
    assert first[Q("2023Q4")] == 101.0
    assert latest[Q("2023Q4")] == 101.5
    assert first[Q("2024Q1")] == latest[Q("2024Q1")] == 102.0
    assert latest.index.is_monotonic_increasing and latest.dtype == float


def test_release_times_sorted_and_utc(store):
    times = store.release_times(SERIES)
    assert times == [T1, T2]
    assert all(t.tzinfo is not None for t in times)


def test_naive_datetime_rejected(store):
    with pytest.raises(NaiveDatetimeError):
        store.as_of(SERIES, datetime(2024, 6, 1))


def test_naive_observation_time_rejected(store):
    with pytest.raises(NaiveDatetimeError):
        store.add_observations([_obs("2024Q2", 1.0, datetime(2024, 9, 1), "v2")])


def test_observations_require_known_snapshot(store):
    with pytest.raises(ValueError, match="unknown snapshots"):
        store.add_observations([_obs("2024Q2", 1.0, T2, "nope")])


def test_missing_value_rejected(store):
    with pytest.raises(ValueError, match="missing"):
        store.add_observations([_obs("2024Q2", float("nan"), T2, "v2")])


def test_adding_same_observations_twice_is_idempotent(store):
    added = store.add_observations([_obs("2023Q3", 100.0, T1, "v1")])
    assert added == 0


def test_snapshot_dedup_and_roundtrip(store):
    assert store.add_snapshot(_snapshot("v1", T1)) is False
    snaps = {s.snapshot_id: s for s in store.snapshots()}
    assert snaps["v1"].published_at == T1 and snaps["v1"].retrieved_at.tzinfo is not None


def test_snapshot_publication_time_filled_once_never_changed(store):
    # Arrange
    store.add_snapshot(_snapshot("v3", None))
    # Act
    store.add_snapshot(_snapshot("v3", T2))
    store.add_snapshot(_snapshot("v3", T1))
    # Assert
    assert {s.snapshot_id: s for s in store.snapshots()}["v3"].published_at == T2


def test_unknown_series_returns_empty(store):
    assert store.latest("nope").empty and store.release_times("nope") == []


def test_release_calendar_and_latest_period_released(store):
    # Arrange
    entries = [ReleaseEntry(SERIES, Q("2023Q4"), "r1", T1, "https://x/1", "test"),
               ReleaseEntry(SERIES, Q("2024Q1"), "r2", T2, "https://x/2", "test")]
    # Act
    added = store.add_release_entries(entries)
    calendar = store.release_calendar(SERIES)
    # Assert
    assert added == 2 and list(calendar["ref_period"]) == [Q("2023Q4"), Q("2024Q1")]
    assert store.latest_period_released(SERIES, T2 - timedelta(seconds=1)) == Q("2023Q4")
    assert store.latest_period_released(SERIES, T1 - timedelta(days=1)) is None


def test_period_text_rejects_non_quarterly():
    assert period_text(Q("2024Q1")) == "2024Q1"
    with pytest.raises(ValueError):
        period_text(pd.Period("2024-01", freq="M"))


def test_export_parquet_and_series_ids(store, tmp_path):
    paths = store.export_parquet(tmp_path / "store")
    frame = pd.read_parquet(tmp_path / "store" / "observations.parquet")
    assert {p.name for p in paths} == {"snapshots.parquet", "observations.parquet",
                                       "release_calendar.parquet"}
    assert len(frame) == 5 and store.series_ids() == [SERIES]


def test_file_backed_store_persists(tmp_path):
    db_path = tmp_path / "sub" / "x.duckdb"
    with DuckDBObservationStore(db_path) as db:
        db.add_snapshot(_snapshot("v1", T1))
        db.add_observations([_obs("2023Q3", 1.0, T1, "v1")])
    with DuckDBObservationStore(db_path) as db:
        assert db.latest(SERIES)[Q("2023Q3")] == 1.0


def test_replaced_file_never_overrides_newer_release(store):
    # Arrange: an older release's file (release T1) re-uploaded at T3, after the
    # newer release T2. It is only *available* from T3 (fail-closed), but the
    # newer release's value must still win once both are available.
    t3 = T2 + timedelta(minutes=1)
    store.add_snapshot(_snapshot("v1b", t3))
    store.add_observations([_obs("2023Q4", 999.0, t3, "v1b")], release_published_at=T1)
    # Act / Assert
    assert store.latest(SERIES)[Q("2023Q4")] == 101.5
    assert store.as_of(SERIES, t3)[Q("2023Q4")] == 101.5
    assert store.first_release(SERIES)[Q("2023Q4")] == 101.0
    assert t3 in store.release_times(SERIES)


def test_replaced_file_invisible_before_its_availability():
    with DuckDBObservationStore(":memory:") as db:
        t3 = T2 + timedelta(days=30)
        db.add_snapshot(_snapshot("late", t3))
        db.add_observations([_obs("2023Q4", 5.0, t3, "late")], release_published_at=T1)
        assert db.as_of(SERIES, T2).empty
        assert db.as_of(SERIES, t3)[Q("2023Q4")] == 5.0


def test_release_time_after_availability_rejected(store):
    with pytest.raises(ValueError, match="release time after"):
        store.add_observations([_obs("2024Q2", 1.0, T1, "v1")], release_published_at=T2)


def test_legacy_store_migrated(tmp_path):
    # Arrange: a store file created before release_published_at existed
    import duckdb

    path = tmp_path / "old.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE observations (series_id TEXT, ref_period TEXT, value DOUBLE,
                   published_at TIMESTAMP, snapshot_id TEXT, kind TEXT)""").fetchall()
    con.execute("INSERT INTO observations VALUES ('s','2020Q1',1.0,'2020-05-01 00:00:00','x','observed')").fetchall()
    con.close()
    # Act
    with DuckDBObservationStore(path) as db:
        result = db.latest("s")
    # Assert
    assert result[Q("2020Q1")] == 1.0

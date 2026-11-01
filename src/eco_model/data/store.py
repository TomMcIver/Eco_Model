"""DuckDB point-in-time observation store (DEC-003), implementing ObservationStore.

Timestamps are stored as naive-UTC TIMESTAMP columns and converted to
timezone-aware UTC at the boundary. Reads are fail-closed: ``as_of`` filters
on publication time, never retrieval time.

Each observation also records ``release_published_at``: the official time of
the release its file belongs to. It differs from ``published_at`` only when a
file was replaced after release (then ``published_at`` is the later,
fail-closed availability time). Among the values *available* at a point in
time, the one from the newest release wins (``latest``/``as_of``), and
``first_release`` takes the value from the earliest release held.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import pandas as pd

from eco_model.contracts import Observation, SourceSnapshot
from eco_model.data.timeutil import from_db, to_db

TABLES: tuple[str, ...] = ("snapshots", "observations", "release_calendar")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    published_at TIMESTAMP,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    licence TEXT NOT NULL,
    notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    series_id TEXT NOT NULL,
    ref_period TEXT NOT NULL,
    value DOUBLE NOT NULL,
    published_at TIMESTAMP NOT NULL,
    snapshot_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    release_published_at TIMESTAMP,
    PRIMARY KEY (series_id, ref_period, published_at, snapshot_id)
);
CREATE TABLE IF NOT EXISTS release_calendar (
    series_id TEXT NOT NULL,
    ref_period TEXT NOT NULL,
    release_id TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL,
    source_url TEXT NOT NULL,
    verification TEXT NOT NULL,
    PRIMARY KEY (series_id, ref_period)
);
"""
# Stores created before release_published_at existed: add it, default to published_at.
_MIGRATE = """
ALTER TABLE observations ADD COLUMN IF NOT EXISTS release_published_at TIMESTAMP;
UPDATE observations SET release_published_at = published_at WHERE release_published_at IS NULL;
"""
_COLUMNS = ["series_id", "ref_period", "value", "published_at", "snapshot_id", "kind",
            "release_published_at"]


@dataclass(frozen=True)
class ReleaseEntry:
    """One dated official release: the first publication of `ref_period`."""

    series_id: str
    ref_period: pd.Period
    release_id: str
    published_at: datetime  # UTC, from the official release page
    source_url: str
    verification: str  # how published_at was verified


def period_text(period: pd.Period) -> str:
    """Quarterly Period -> 'YYYYQn' text key."""
    if not isinstance(period, pd.Period) or period.freqstr[:1] != "Q":
        raise ValueError(f"ref_period must be a quarterly pd.Period, got {period!r}")
    return f"{period.year}Q{period.quarter}"


def _as_series(rows: Sequence[tuple[str, float]], series_id: str) -> pd.Series:
    index = pd.PeriodIndex([pd.Period(p, freq="Q") for p, _ in rows], freq="Q")
    series = pd.Series([float(v) for _, v in rows], index=index, name=series_id, dtype=float)
    return series.sort_index()


class DuckDBObservationStore:
    """ObservationStore backed by a DuckDB file (or ':memory:')."""

    def __init__(self, db_path: str | Path) -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(db_path))
        self._con.execute(_SCHEMA).fetchall()
        self._con.execute(_MIGRATE).fetchall()

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "DuckDBObservationStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- writes
    def add_snapshot(self, snapshot: SourceSnapshot) -> bool:
        """Insert a snapshot record; identical bytes (same sha256) are not duplicated."""
        published = None if snapshot.published_at is None else to_db(snapshot.published_at)
        before = self._count("snapshots")
        self._con.execute(
            "INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                snapshot.snapshot_id, snapshot.source_id, snapshot.url,
                to_db(snapshot.retrieved_at, "retrieved_at"), published,
                snapshot.file_path, snapshot.sha256, snapshot.media_type,
                snapshot.licence, snapshot.notes,
            ],
        ).fetchall()
        inserted = self._count("snapshots") > before
        if not inserted and published is not None:
            # A file first recorded without a verified publication time (e.g. a
            # failed parse or a mislinked page) takes the provenance of the release
            # that successfully used it; an existing publication time never changes.
            self._con.execute(
                "UPDATE snapshots SET published_at = ?, notes = ?, source_id = ?, url = ? "
                "WHERE snapshot_id = ? AND published_at IS NULL",
                [published, snapshot.notes, snapshot.source_id, snapshot.url, snapshot.snapshot_id],
            ).fetchall()
        return inserted

    def add_observations(
        self, observations: Iterable[Observation], release_published_at: datetime | None = None
    ) -> int:
        """Insert observations (idempotent); returns the number of new rows.

        `release_published_at` is the official time of the release the values
        belong to (defaults to each observation's own published_at); it must
        not be later than any observation's published_at.
        """
        release = None if release_published_at is None else to_db(release_published_at)
        rows = [self._obs_row(o, release) for o in observations]
        if not rows:
            return 0
        missing = {r[4] for r in rows} - self._snapshot_ids()
        if missing:
            raise ValueError(f"observations reference unknown snapshots: {sorted(missing)[:3]}")
        before = self._count("observations")
        frame = pd.DataFrame(rows, columns=_COLUMNS)
        self._con.register("_incoming", frame)
        try:
            self._con.execute(f"INSERT OR IGNORE INTO observations ({', '.join(_COLUMNS)}) SELECT * FROM _incoming").fetchall()
        finally:
            self._con.unregister("_incoming")
        return self._count("observations") - before

    def add_release_entries(self, entries: Iterable[ReleaseEntry]) -> int:
        before = self._count("release_calendar")
        for e in entries:
            self._con.execute(
                "INSERT OR IGNORE INTO release_calendar VALUES (?,?,?,?,?,?)",
                [e.series_id, period_text(e.ref_period), e.release_id,
                 to_db(e.published_at, "published_at"), e.source_url, e.verification],
            ).fetchall()
        return self._count("release_calendar") - before

    # ----------------------------------------------------------------- reads
    def as_of(self, series_id: str, as_of: datetime) -> pd.Series:
        cutoff = to_db(as_of, "as_of")
        return self._latest_per_period(series_id, "AND published_at <= ?", [cutoff])

    def latest(self, series_id: str) -> pd.Series:
        return self._latest_per_period(series_id, "", [])

    def first_release(self, series_id: str) -> pd.Series:
        rows = self._con.execute(
            """SELECT ref_period, value FROM observations WHERE series_id = ?
               QUALIFY row_number() OVER (PARTITION BY ref_period
                   ORDER BY release_published_at ASC, published_at ASC, snapshot_id ASC) = 1""",
            [series_id],
        ).fetchall()
        return _as_series(rows, series_id)

    def release_times(self, series_id: str) -> list[datetime]:
        rows = self._con.execute(
            "SELECT DISTINCT published_at FROM observations WHERE series_id = ? ORDER BY 1",
            [series_id],
        ).fetchall()
        return [from_db(r[0]) for r in rows]

    def release_calendar(self, series_id: str) -> pd.DataFrame:
        """Dated releases for a series: ref_period (Period), published_at (UTC), source_url."""
        frame = self._con.execute(
            """SELECT ref_period, release_id, published_at, source_url, verification
               FROM release_calendar WHERE series_id = ? ORDER BY published_at""",
            [series_id],
        ).df()
        frame["ref_period"] = [pd.Period(p, freq="Q") for p in frame["ref_period"]]
        frame["published_at"] = pd.to_datetime(frame["published_at"]).dt.tz_localize("UTC")
        return frame

    def latest_period_released(self, series_id: str, as_of: datetime) -> pd.Period | None:
        """Latest reference quarter whose dated release was published at or before `as_of`."""
        row = self._con.execute(
            "SELECT max(ref_period) FROM release_calendar WHERE series_id = ? AND published_at <= ?",
            [series_id, to_db(as_of, "as_of")],
        ).fetchall()[0]
        return None if row is None or row[0] is None else pd.Period(row[0], freq="Q")

    def snapshots(self) -> list[SourceSnapshot]:
        rows = self._con.execute("SELECT * FROM snapshots ORDER BY retrieved_at").fetchall()
        return [
            SourceSnapshot(r[0], r[1], r[2], from_db(r[3]), from_db(r[4]), *r[5:]) for r in rows
        ]

    def series_ids(self) -> list[str]:
        rows = self._con.execute("SELECT DISTINCT series_id FROM observations ORDER BY 1").fetchall()
        return [r[0] for r in rows]

    # ---------------------------------------------------------------- export
    def export_parquet(self, out_dir: str | Path) -> list[Path]:
        """Write every table to ``<out_dir>/<table>.parquet``; returns the paths."""
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        paths = []
        for table in TABLES:
            path = target / f"{table}.parquet"
            escaped = str(path.resolve()).replace("\\", "/").replace("'", "''")
            self._con.execute(f"COPY {table} TO '{escaped}' (FORMAT PARQUET)").fetchall()
            paths.append(path)
        return paths

    # --------------------------------------------------------------- helpers
    def _latest_per_period(self, series_id: str, extra: str, params: list) -> pd.Series:
        rows = self._con.execute(
            f"""SELECT ref_period, value FROM observations
                WHERE series_id = ? {extra}
                QUALIFY row_number() OVER (PARTITION BY ref_period
                    ORDER BY release_published_at DESC, published_at DESC,
                             snapshot_id DESC) = 1""",
            [series_id, *params],
        ).fetchall()
        return _as_series(rows, series_id)

    def _count(self, table: str) -> int:
        return int(self._con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0])

    def _snapshot_ids(self) -> set[str]:
        return {r[0] for r in self._con.execute("SELECT snapshot_id FROM snapshots").fetchall()}

    @staticmethod
    def _obs_row(o: Observation, release: datetime | None) -> tuple:
        if not pd.notna(o.value):
            raise ValueError(f"{o.series_id} {o.ref_period}: observation value is missing")
        published = to_db(o.published_at, "published_at")
        if release is not None and release > published:
            raise ValueError(f"{o.series_id} {o.ref_period}: release time after availability time")
        return (o.series_id, period_text(o.ref_period), float(o.value), published,
                o.snapshot_id, o.kind.value, published if release is None else release)

"""Run the real Stats NZ download and load the point-in-time store.

Usage:  python -m eco_model.data.ingest [--since 2017Q1] [--series ID ...]
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from eco_model.contracts import RAW_SERIES
from eco_model.data.snapshots import HttpSession, default_session
from eco_model.data.statsnz import ReleaseResult, ingest_release
from eco_model.data.statsnz_catalog import FIRST_ARCHIVED_RELEASE, STATSNZ_SERIES
from eco_model.data.store import DuckDBObservationStore
from eco_model.data.timeutil import utc_now

log = logging.getLogger("eco_model.data.ingest")
DEFAULT_DB = Path("data/eco_model.duckdb")
DEFAULT_RAW = Path("data/raw")
DEFAULT_STORE_DIR = Path("data/store")
DEFAULT_PAUSE_S = 0.5  # politeness delay between release fetches


@dataclass(frozen=True)
class SeriesSummary:
    series_id: str
    releases_ingested: int
    first_period: str | None
    last_period: str | None
    latest_value: float | None
    vintages: int


@dataclass(frozen=True)
class IngestReport:
    results: tuple[ReleaseResult, ...]
    summaries: tuple[SeriesSummary, ...]
    parquet_files: tuple[str, ...]

    def problems(self) -> tuple[ReleaseResult, ...]:
        return tuple(r for r in self.results if r.status in ("failed", "no_usable_file"))

    def format(self) -> str:
        lines = ["Stats NZ ingestion report", "=" * 26]
        for s in self.summaries:
            lines.append(
                f"{s.series_id}: {s.releases_ingested} releases ingested, {s.vintages} vintages, "
                f"latest vintage covers {s.first_period}..{s.last_period}, latest value {s.latest_value}"
            )
        lines.append("")
        for r in self.results:
            when = r.vintage_at.isoformat() if r.vintage_at else "-"
            file_name = (r.file_url or "").rsplit("/", 1)[-1] or "-"
            lines.append(f"  [{r.status}] {r.series_id} {r.quarter} vintage={when} "
                         f"file={file_name} obs+={r.observations} :: {r.detail[:160]}")
        lines.extend(f"parquet: {p}" for p in self.parquet_files)
        return "\n".join(lines)


def release_quarters(since: pd.Period, until: pd.Period) -> list[pd.Period]:
    return list(pd.period_range(since, until, freq="Q"))


def summarise(store: DuckDBObservationStore, series_id: str,
              results: Sequence[ReleaseResult]) -> SeriesSummary:
    latest = store.latest(series_id)
    return SeriesSummary(
        series_id=series_id,
        releases_ingested=sum(r.status == "ingested" for r in results if r.series_id == series_id),
        first_period=str(latest.index.min()) if len(latest) else None,
        last_period=str(latest.index.max()) if len(latest) else None,
        latest_value=float(latest.iloc[-1]) if len(latest) else None,
        vintages=len(store.release_times(series_id)),
    )


def ingest_all(
    db_path: str | Path = DEFAULT_DB,
    raw_dir: str | Path = DEFAULT_RAW,
    *,
    series: Sequence[str] = RAW_SERIES,
    since: pd.Period = FIRST_ARCHIVED_RELEASE,
    until: pd.Period | None = None,
    session: HttpSession | None = None,
    store_dir: str | Path | None = DEFAULT_STORE_DIR,
    pause_s: float = DEFAULT_PAUSE_S,
) -> IngestReport:
    """Ingest every archived release from `since` to `until` (default: current quarter)."""
    http = session or default_session()
    last = until or pd.Period(utc_now().strftime("%Y-%m-%d"), freq="Q")
    results: list[ReleaseResult] = []
    with DuckDBObservationStore(db_path) as store:
        for series_id in series:
            spec = STATSNZ_SERIES[series_id]
            for quarter in release_quarters(since, last):
                result = ingest_release(store, spec, quarter, Path(raw_dir), http)
                log.info("%s %s %s %s", result.status, series_id, quarter, result.detail[:120])
                results.append(result)
                time.sleep(pause_s)
        summaries = tuple(summarise(store, s, results) for s in series)
        parquet = tuple(str(p) for p in store.export_parquet(store_dir)) if store_dir else ()
    return IngestReport(tuple(results), summaries, parquet)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))
    parser.add_argument("--since", default=str(FIRST_ARCHIVED_RELEASE))
    parser.add_argument("--until", default=None)
    parser.add_argument("--series", nargs="*", default=list(RAW_SERIES))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    report = ingest_all(
        args.db, args.raw_dir, series=args.series, since=pd.Period(args.since, freq="Q"),
        until=pd.Period(args.until, freq="Q") if args.until else None, store_dir=args.store_dir,
    )
    print(report.format())  # CLI output is the deliverable here
    return 1 if report.problems() else 0


if __name__ == "__main__":
    raise SystemExit(main())

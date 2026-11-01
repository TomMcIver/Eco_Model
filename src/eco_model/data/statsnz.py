"""Stats NZ ingestion: one information release -> snapshots, observations, calendar.

Vintage policy (DEC-004):
- Every value parsed from a release file carries that file's publication time,
  including historical reference quarters re-published in it. A single current
  release therefore only supports the PSEUDO_OOS (revised-data) track; genuine
  multiple vintages come from ingesting each archived release separately.
- Publication time = the release page's official ``PublicationDate`` (10:45 NZ
  local), *unless* the file's HTTP Last-Modified is more than one hour later
  (corrected/replaced file). Then the file's bytes are only known to have
  existed from Last-Modified, so that later time is used (fail-closed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from eco_model.contracts import Observation, SourceSnapshot, ValueKind
from eco_model.data.snapshots import (
    HttpSession,
    fetch_snapshot,
    last_modified,
    with_published_at,
)
from eco_model.data.statsnz_catalog import BASE_URL, StatsNZSeries, rank_links, release_url
from eco_model.data.statsnz_parse import ParseError, extract_series, parse_release_page
from eco_model.data.store import DuckDBObservationStore, ReleaseEntry

AS_RELEASED_GRACE = timedelta(hours=1)
CALENDAR_VERIFICATION = "PublicationDate on official Stats NZ release page (NZ local -> UTC)"


@dataclass(frozen=True)
class ReleaseResult:
    series_id: str
    quarter: str  # release reference quarter, 'YYYYQn'
    status: str  # ingested | no_page | no_usable_file | failed
    detail: str
    release_url: str
    published_at: datetime | None = None  # release-page time (UTC)
    vintage_at: datetime | None = None  # time attached to the observations (UTC)
    file_url: str | None = None
    observations: int = 0
    first_period: str | None = None
    last_period: str | None = None


def vintage_time(release_at: datetime, file_modified: datetime | None) -> tuple[datetime, str]:
    """Publication time to attach to a file's values, with the reason."""
    if file_modified is None:
        return release_at, "release PublicationDate; file Last-Modified unavailable"
    if file_modified <= release_at + AS_RELEASED_GRACE:
        return release_at, f"as-released file (Last-Modified {file_modified.isoformat()})"
    return file_modified, (
        f"file replaced after release (Last-Modified {file_modified.isoformat()}); "
        "values treated as published at Last-Modified (fail-closed)"
    )


def _dataset(spec: StatsNZSeries) -> str:
    return {"gross-domestic-product": "gdp", "consumers-price-index": "cpi"}.get(
        spec.release_prefix, "lms"
    )


def _annotate(snapshot: SourceSnapshot, extra: dict) -> SourceSnapshot:
    notes = {**json.loads(snapshot.notes or "{}"), **extra}
    return SourceSnapshot(**{**snapshot.__dict__, "notes": json.dumps(notes, sort_keys=True)})


def build_observations(
    rows: pd.DataFrame, series_id: str, published_at: datetime, snapshot_id: str
) -> list[Observation]:
    return [
        Observation(series_id, period, float(value), published_at, snapshot_id, ValueKind.OBSERVED)
        for period, value in zip(rows["ref_period"], rows["value"])
    ]


def ingest_release(
    store: DuckDBObservationStore,
    spec: StatsNZSeries,
    quarter: pd.Period,
    raw_dir: Path,
    session: HttpSession,
) -> ReleaseResult:
    """Fetch, preserve and load one release of one series. Never raises for a bad release."""
    page_url = release_url(spec, quarter)
    base = {"series_id": spec.series_id, "quarter": str(quarter), "release_url": page_url}
    dataset = _dataset(spec)
    try:
        page_snap, page_bytes = fetch_snapshot(
            page_url, f"statsnz:{dataset}-release-page:{quarter}", raw_dir, session=session
        )
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        status = "no_page" if status_code == 404 else "failed"
        return ReleaseResult(**base, status=status, detail=f"{type(exc).__name__}: {exc}")
    try:
        page = parse_release_page(page_bytes)
    except ParseError as exc:
        store.add_snapshot(page_snap)
        return ReleaseResult(**base, status="failed", detail=str(exc))
    store.add_snapshot(_annotate(with_published_at(page_snap, page.published_at),
                                 {"publication_date_nz_local": page.published_local}))
    store.add_release_entries([ReleaseEntry(
        spec.series_id, quarter, f"statsnz:{dataset}:{quarter}", page.published_at,
        page_url, CALENDAR_VERIFICATION,
    )])
    return _ingest_files(store, spec, quarter, raw_dir, session, page, base)


def _ingest_files(store, spec, quarter, raw_dir, session, page, base) -> ReleaseResult:
    links = rank_links(spec, list(page.links))
    tried = []
    for link in links:
        url = BASE_URL + link
        snap = None
        try:
            snap, content = fetch_snapshot(
                url, f"statsnz:{_dataset(spec)}:{quarter}", raw_dir, session=session
            )
            rows = extract_series(content, link, spec.series_ref)
        except Exception as exc:  # noqa: BLE001 - try next candidate, keep the reason
            tried.append(f"{link.rsplit('/', 1)[-1]}: {type(exc).__name__}: {exc}")
            if snap is not None:
                store.add_snapshot(snap)
            continue
        return _load_vintage(store, spec, quarter, page, snap, rows, url, base)
    detail = "; ".join(tried) or f"no CSV/ZIP download links among {len(page.links)} links"
    return ReleaseResult(**base, status="no_usable_file", detail=detail,
                         published_at=page.published_at)


def _load_vintage(store, spec, quarter, page, snap, rows, url, base) -> ReleaseResult:
    last = rows["ref_period"].max()
    if last != quarter:
        store.add_snapshot(snap)
        return ReleaseResult(**base, status="failed", published_at=page.published_at,
                             file_url=url, detail=f"file's latest period {last} != release {quarter}")
    vintage_at, basis = vintage_time(page.published_at, last_modified(snap))
    stored = _annotate(with_published_at(snap, vintage_at), {
        "vintage_basis": basis, "series_ref": spec.series_ref,
        "release_page": base["release_url"], "members": sorted(set(rows["member"])),
    })
    store.add_snapshot(stored)
    added = store.add_observations(
        build_observations(rows, spec.series_id, vintage_at, snap.snapshot_id),
        release_published_at=page.published_at,
    )
    return ReleaseResult(
        **base, status="ingested", detail=basis, published_at=page.published_at,
        vintage_at=vintage_at, file_url=url, observations=added,
        first_period=str(rows["ref_period"].min()), last_period=str(last),
    )

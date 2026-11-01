"""Pure parsers for Stats NZ release pages and Infoshare-style CSV downloads."""

from __future__ import annotations

import html
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import IO, Iterator

import pandas as pd

from eco_model.data.timeutil import nz_local_to_utc

CHUNK_ROWS = 500_000
_PUBLICATION_RE = re.compile(r'"PublicationDate":"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')
_LINK_RE = re.compile(r'"(/assets/Uploads/[^"]+\.(?:csv|zip|xlsx|xls))"', re.IGNORECASE)
_PERIOD_RE = re.compile(r"^(\d{4})\.(\d{2})$")
_STANDARD_COLUMNS = ("series_reference", "period", "data_value", "status", "group")
_MONTH_TO_QUARTER = {"03": 1, "06": 2, "09": 3, "12": 4}


class ParseError(ValueError):
    """A file or page did not have the verified structure."""


@dataclass(frozen=True)
class ReleasePage:
    published_at: datetime  # UTC, from the page's PublicationDate (NZ local)
    published_local: str  # the raw NZ-local string, kept for provenance
    links: tuple[str, ...]  # site-relative download links


def _page_text(raw: bytes) -> str:
    return html.unescape(raw.decode("utf-8", errors="replace")).replace("\\/", "/")


def parse_release_page(raw: bytes) -> ReleasePage:
    """Extract the official publication time and download links from a release page."""
    text = _page_text(raw)
    stamps = _PUBLICATION_RE.findall(text)
    if not stamps:
        raise ParseError("release page has no PublicationDate")
    local = stamps[0]
    published = nz_local_to_utc(datetime.strptime(local, "%Y-%m-%d %H:%M:%S"))
    links = tuple(dict.fromkeys(_LINK_RE.findall(text)))
    return ReleasePage(published_at=published, published_local=local, links=links)


def period_from_statsnz(code: str) -> pd.Period:
    """'2026.06' -> Period('2026Q2'); rejects non-quarter-end months."""
    match = _PERIOD_RE.match(str(code).strip())
    if not match or match.group(2) not in _MONTH_TO_QUARTER:
        raise ParseError(f"not a quarterly Stats NZ period code: {code!r}")
    return pd.Period(year=int(match.group(1)), quarter=_MONTH_TO_QUARTER[match.group(2)], freq="Q")


def _csv_members(raw: bytes, name: str) -> Iterator[tuple[str, IO[bytes]]]:
    """Yield (member name, stream) for every CSV, descending into nested zips."""
    if not (name.lower().endswith(".zip") or raw[:2] == b"PK"):
        yield name, io.BytesIO(raw)
        return
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.namelist():
            lowered = member.lower()
            if lowered.endswith(".zip"):
                yield from _csv_members(archive.read(member), member)
            elif lowered.endswith(".csv"):
                with archive.open(member) as stream:
                    yield member, stream


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Lower-case/underscore names, keep the standard columns, first occurrence wins."""
    renamed = frame.set_axis(
        [str(c).strip().lstrip("﻿").lower().replace(" ", "_") for c in frame.columns], axis=1
    )
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    if "status_code" in renamed and "status" not in renamed:
        renamed = renamed.rename(columns={"status_code": "status"})
    present = [c for c in _STANDARD_COLUMNS if c in renamed.columns]
    return renamed[present]


def _rows_for_series(buffer: IO[bytes], series_ref: str) -> pd.DataFrame:
    """Stream one CSV, keeping only rows for `series_ref`."""
    lines = buffer.read(8192).decode("utf-8-sig", errors="replace").lower().splitlines()
    buffer.seek(0)
    header = lines[0] if lines else ""
    if "series_reference" not in header or "period" not in header:
        return pd.DataFrame()
    kept = []
    reader = pd.read_csv(buffer, dtype=str, chunksize=CHUNK_ROWS, encoding="utf-8-sig",
                         encoding_errors="replace", keep_default_na=False)
    for chunk in reader:
        chunk = _normalise_columns(chunk)
        kept.append(chunk[chunk["series_reference"].str.strip() == series_ref])
    return pd.concat(kept, ignore_index=True) if kept else pd.DataFrame()


def extract_series(raw: bytes, name: str, series_ref: str) -> pd.DataFrame:
    """Return columns ref_period (Period), value (float), status, group, member.

    Rows with an empty value (e.g. pre-history gaps) are dropped. Raises if the
    series is absent or if two members disagree about a period's value.
    """
    parts = []
    for member, buffer in _csv_members(raw, name):
        rows = _rows_for_series(buffer, series_ref)
        if not rows.empty:
            parts.append(rows.assign(member=member))
    if not parts:
        raise ParseError(f"series {series_ref} not found in {name}")
    rows = pd.concat(parts, ignore_index=True)
    out = pd.DataFrame({
        "ref_period": [period_from_statsnz(p) for p in rows["period"]],
        "raw_value": rows["data_value"].str.strip(),
        "status": rows["status"] if "status" in rows else "",
        "group": rows["group"] if "group" in rows else "",
        "member": rows["member"],
    })
    out = out[~out["raw_value"].isin(["", "NA", ".."])]
    out = out.assign(value=out["raw_value"].astype(float)).drop(columns="raw_value")
    return _dedupe_periods(out, series_ref)


def _dedupe_periods(frame: pd.DataFrame, series_ref: str) -> pd.DataFrame:
    distinct = frame.drop_duplicates(["ref_period", "value"])
    clashes = distinct[distinct.duplicated("ref_period", keep=False)]
    if not clashes.empty:
        raise ParseError(f"{series_ref}: conflicting values across files for "
                         f"{sorted(set(clashes['ref_period'].astype(str)))[:3]}")
    return distinct.sort_values("ref_period").reset_index(drop=True)

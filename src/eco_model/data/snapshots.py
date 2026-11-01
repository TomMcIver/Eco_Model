"""Immutable raw-file snapshots (DEC-003 provenance).

Raw bytes are written once, unchanged, to ``<raw_dir>/<source>/<sha256>.<ext>``.
Identical bytes map to the same file (no duplicate); changed bytes get a new
sha256 and therefore a new file. Nothing here ever overwrites an existing file.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from dataclasses import replace
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from eco_model.contracts import SourceSnapshot
from eco_model.data.timeutil import UTC, require_utc, utc_now

STATS_NZ_LICENCE = "CC BY 4.0 Stats NZ"
USER_AGENT = "eco-model/0.1 (NZ economic research; point-in-time data capture)"
DEFAULT_TIMEOUT_S = 120
# Response headers worth keeping as provenance; cookies are deliberately excluded.
KEPT_HEADERS = ("ETag", "Last-Modified", "Content-Type", "Content-Length", "Date")


class HttpResponse(Protocol):
    status_code: int
    content: bytes
    headers: Mapping[str, str]

    def raise_for_status(self) -> None: ...


class HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> HttpResponse: ...


class SnapshotIntegrityError(RuntimeError):
    """An existing raw file does not match the sha256 it is named after."""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def source_dir_name(source_id: str) -> str:
    """'statsnz:gdp:release-2026Q2' -> 'statsnz_gdp' (provider + dataset folder)."""
    parts = [p for p in source_id.split(":") if p][:2] or ["unknown"]
    return re.sub(r"[^A-Za-z0-9_-]+", "-", "_".join(parts))


def extension_for(url_or_name: str, media_type: str = "") -> str:
    suffix = PurePosixPath(urlparse(url_or_name).path).suffix.lower().lstrip(".")
    if suffix and re.fullmatch(r"[a-z0-9]{1,8}", suffix):
        return suffix
    guessed = mimetypes.guess_extension(media_type.split(";")[0].strip()) or ".bin"
    return guessed.lstrip(".")


def write_raw_once(content: bytes, raw_dir: Path, source_id: str, ext: str) -> str:
    """Write bytes to their content-addressed path; return path relative to raw_dir."""
    digest = sha256_hex(content)
    rel = PurePosixPath(source_dir_name(source_id)) / f"{digest}.{ext}"
    target = Path(raw_dir) / rel
    if target.exists():
        if sha256_hex(target.read_bytes()) != digest:
            raise SnapshotIntegrityError(f"{target} exists but its bytes do not match")
        return str(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".partial")
    tmp.write_bytes(content)
    tmp.replace(target)
    return str(rel)


def header_notes(headers: Mapping[str, str], extra: Mapping[str, Any] | None = None) -> str:
    kept = {k: headers[k] for k in KEPT_HEADERS if k in headers}
    return json.dumps({"headers": kept, **(extra or {})}, sort_keys=True)


def last_modified(snapshot: SourceSnapshot) -> datetime | None:
    """Parse the Last-Modified response header recorded in a snapshot's notes."""
    try:
        value = json.loads(snapshot.notes or "{}").get("headers", {}).get("Last-Modified")
    except json.JSONDecodeError:
        return None
    if not value:
        return None
    return parsedate_to_datetime(value).astimezone(UTC)


def default_session() -> HttpSession:
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def fetch_snapshot(
    url: str,
    source_id: str,
    raw_dir: Path,
    *,
    published_at: datetime | None = None,
    licence: str = STATS_NZ_LICENCE,
    session: HttpSession | None = None,
    retrieved_at: datetime | None = None,
) -> tuple[SourceSnapshot, bytes]:
    """Download `url`, store its bytes unchanged and return (snapshot, bytes)."""
    http = session or default_session()
    response = http.get(url, timeout=DEFAULT_TIMEOUT_S)
    response.raise_for_status()
    content = response.content
    media_type = response.headers.get("Content-Type", "application/octet-stream")
    rel = write_raw_once(content, Path(raw_dir), source_id, extension_for(url, media_type))
    snapshot = SourceSnapshot(
        snapshot_id=sha256_hex(content),
        source_id=source_id,
        url=url,
        retrieved_at=require_utc(retrieved_at or utc_now(), "retrieved_at"),
        published_at=None if published_at is None else require_utc(published_at, "published_at"),
        file_path=rel,
        sha256=sha256_hex(content),
        media_type=media_type,
        licence=licence,
        notes=header_notes(response.headers),
    )
    return snapshot, content


def register_local_file(
    path: Path,
    source_id: str,
    raw_dir: Path,
    *,
    url: str,
    published_at: datetime | None = None,
    licence: str = STATS_NZ_LICENCE,
    notes: str = "",
    retrieved_at: datetime | None = None,
) -> SourceSnapshot:
    """Register a manually downloaded file (e.g. behind an API key or browser).

    `url` should be where the file was obtained; `retrieved_at` defaults to the
    file's modification time, which is the best available retrieval evidence.
    """
    source = Path(path)
    content = source.read_bytes()
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    rel = write_raw_once(content, Path(raw_dir), source_id, extension_for(source.name, media_type))
    when = retrieved_at or datetime.fromtimestamp(source.stat().st_mtime, UTC)
    extra = {"manual_registration": True, "original_name": source.name, "note": notes}
    return SourceSnapshot(
        snapshot_id=sha256_hex(content),
        source_id=source_id,
        url=url,
        retrieved_at=require_utc(when, "retrieved_at"),
        published_at=None if published_at is None else require_utc(published_at, "published_at"),
        file_path=rel,
        sha256=sha256_hex(content),
        media_type=media_type,
        licence=licence,
        notes=json.dumps(extra, sort_keys=True),
    )


def with_published_at(snapshot: SourceSnapshot, published_at: datetime | None) -> SourceSnapshot:
    """Return a copy carrying a (verified) publication time."""
    value = None if published_at is None else require_utc(published_at, "published_at")
    return replace(snapshot, published_at=value)


def read_raw(snapshot: SourceSnapshot, raw_dir: Path) -> bytes:
    """Read a snapshot's bytes back, verifying the checksum."""
    content = (Path(raw_dir) / snapshot.file_path).read_bytes()
    if sha256_hex(content) != snapshot.sha256:
        raise SnapshotIntegrityError(f"checksum mismatch for {snapshot.file_path}")
    return content

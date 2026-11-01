"""Timezone helpers: every timestamp in the data layer is timezone-aware UTC."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
NZ_TZ = ZoneInfo("Pacific/Auckland")


class NaiveDatetimeError(ValueError):
    """Raised when a naive (timezone-less) datetime crosses a data-layer boundary."""


def require_utc(value: datetime, name: str = "datetime") -> datetime:
    """Return `value` converted to UTC; reject naive datetimes with a clear error."""
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveDatetimeError(
            f"{name}={value!r} is naive; pass a timezone-aware datetime (UTC preferred)"
        )
    return value.astimezone(UTC)


def to_db(value: datetime, name: str = "datetime") -> datetime:
    """UTC-aware datetime -> naive UTC datetime for DuckDB TIMESTAMP columns."""
    return require_utc(value, name).replace(tzinfo=None)


def from_db(value: datetime | None) -> datetime | None:
    """Naive UTC datetime read from DuckDB -> UTC-aware datetime."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC)


def nz_local_to_utc(local: datetime) -> datetime:
    """Interpret a naive NZ wall-clock time (Pacific/Auckland, DST-aware) as UTC."""
    if local.tzinfo is not None:
        raise ValueError("nz_local_to_utc expects a naive NZ wall-clock datetime")
    return local.replace(tzinfo=NZ_TZ).astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)

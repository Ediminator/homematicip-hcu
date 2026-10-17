"""Minimal stub of homeassistant.util.dt for the test harness."""
from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc
DEFAULT_TIME_ZONE = UTC


def utcnow() -> datetime:
    """Return the current time in UTC (timezone-aware)."""
    return datetime.now(UTC)


def now(time_zone=None) -> datetime:
    """Return the current time in the given (or default) time zone."""
    return datetime.now(time_zone or DEFAULT_TIME_ZONE)


def parse_datetime(dt_str: str) -> datetime | None:
    """Parse an ISO 8601 string, returning None when it is not valid."""
    try:
        return datetime.fromisoformat(dt_str)
    except (TypeError, ValueError):
        return None

"""Nepal Standard Time (Asia/Kathmandu, UTC+05:45) helpers."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

try:
    NEPAL_TZ = ZoneInfo('Asia/Kathmandu')
except Exception:
    NEPAL_TZ = timezone(timedelta(hours=5, minutes=45), name='NPT')


def now_nepal() -> datetime:
    return datetime.now(NEPAL_TZ)


def now_nepal_naive() -> datetime:
    return now_nepal().replace(tzinfo=None)


def to_nepal(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=NEPAL_TZ)
    return dt.astimezone(NEPAL_TZ)


def format_nepal(dt: datetime | None, fmt: str = '%Y-%m-%d %H:%M') -> str:
    if dt is None:
        return ''
    n = to_nepal(dt)
    return n.strftime(fmt) if n else ''


def format_nepal_local(dt: datetime | None, fmt: str = '%d %b %Y · %I:%M %p') -> str:
    if dt is None:
        return ''
    if dt.tzinfo is not None:
        dt = dt.astimezone(NEPAL_TZ).replace(tzinfo=None)
    return dt.strftime(fmt)

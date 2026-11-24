"""Local time and working-day arithmetic.

A copy of synapsidian's synapsidianlib.dates, which this plugin can't import.
"""

from __future__ import annotations

import datetime as dt


def parse_moment(raw: str | None) -> dt.datetime | None:
    """ISO timestamp ('Z', offset or naive local) -> aware local datetime; None when unparseable."""
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.astimezone()).astimezone()


def now_local(raw: str | None = None) -> dt.datetime:
    return parse_moment(raw) or dt.datetime.now().astimezone()


def workdays_between(start: dt.datetime, end: dt.datetime) -> int:
    """Whole working days (Mon-Fri) from `start` to `end`; weekends don't age anything."""
    days, cursor = 0, start.astimezone(end.tzinfo).date()
    while cursor < end.date():
        cursor += dt.timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days

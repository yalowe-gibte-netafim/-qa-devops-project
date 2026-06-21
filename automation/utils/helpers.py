"""General-purpose helper utilities."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def parse_hms_duration(duration_str: str) -> timedelta:
    """Parse 'HH:MM' or 'HH:MM:SS' into a timedelta.  Returns zero on failure."""
    try:
        parts = duration_str.split(":")
        if len(parts) == 2:
            return timedelta(hours=int(parts[0]), minutes=int(parts[1]))
        if len(parts) == 3:
            return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]))
    except Exception:
        pass
    return timedelta(0)


def parse_hms_time(time_str: str, base_date: Optional[datetime] = None) -> Optional[datetime]:
    """Parse 'HH:MM', 'HH:MM:SS', or full 'YYYY-MM-DD HH:MM:SS' into a datetime.

    Why: centralises all time-string parsing so each consumer does not duplicate the logic.
    """
    try:
        if isinstance(time_str, str) and "-" in time_str and ":" in time_str:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

        ref = base_date or datetime.now()
        parts = time_str.split(":")
        if len(parts) == 2:
            parsed = datetime.strptime(time_str, "%H:%M")
        elif len(parts) == 3:
            parsed = datetime.strptime(time_str, "%H:%M:%S")
        else:
            return None
        return datetime.combine(ref.date(), parsed.time())
    except (ValueError, AttributeError):
        return None

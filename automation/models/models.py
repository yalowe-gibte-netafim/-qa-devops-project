"""Domain models shared across all layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogEvent:
    """Represents a single parsed event from a FLEX CLI log file."""
    time: str                        # full datetime string "YYYY-MM-DD HH:MM:SS"
    original_time: str               # raw HH:MM:SS from log
    full_time: datetime              # parsed datetime object
    type: str                        # 'valve' | 'wm'
    id: int                          # device number
    action: str                      # lowercase action string, e.g. 'open', 'close'
    count: int = 0                   # pulse count (wm events)
    wm_snapshot: dict[int, int] = field(default_factory=dict)  # {wm_id: cumulative_count}

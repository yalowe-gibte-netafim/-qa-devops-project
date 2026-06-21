"""Timing / wait utilities shared across the framework."""

from __future__ import annotations

import time
import threading
from typing import Callable


def wait_for_event(event: threading.Event, timeout_s: float = 5.0) -> bool:
    """Block until *event* is set or *timeout_s* elapses.  Returns True if set."""
    return event.wait(timeout=timeout_s)


def sleep_between_commands(delay_s: float) -> None:
    """Pause between sequenced hardware commands (e.g. init sequence)."""
    time.sleep(delay_s)

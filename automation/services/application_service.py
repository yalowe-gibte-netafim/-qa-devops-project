"""Application-level orchestration service."""

from __future__ import annotations


class ApplicationService:
    """Coordinates high-level application lifecycle actions."""

    def __init__(self) -> None:
        self._started = False

    def start(self) -> None:
        """Mark application lifecycle as started."""
        self._started = True

    def stop(self) -> None:
        """Mark application lifecycle as stopped."""
        self._started = False

    @property
    def is_started(self) -> bool:
        """Lifecycle state flag."""
        return self._started

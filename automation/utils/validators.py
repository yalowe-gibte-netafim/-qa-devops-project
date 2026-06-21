"""Input validators used at system boundaries (UI, serial, config)."""

from __future__ import annotations


def is_valid_time_string(value: str) -> bool:
    """Return True for 'HH:MM' or 'HH:MM:SS' format strings."""
    parts = value.split(":")
    if len(parts) not in (2, 3):
        return False
    try:
        return all(0 <= int(p) <= 59 for p in parts)
    except ValueError:
        return False


def is_positive_int(value: str) -> bool:
    """Return True if *value* is a string representing a positive integer."""
    try:
        return int(value) > 0
    except (ValueError, TypeError):
        return False


def is_positive_float(value: str) -> bool:
    """Return True if *value* is a string representing a positive float."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False

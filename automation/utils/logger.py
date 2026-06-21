"""UI + file logger.

Wraps a tkinter ScrolledText widget and an optional file path so callers
never need to know which widget or file to write to.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional

import tkinter as tk


# Compiled once for performance
_TIMESTAMP_RE = re.compile(r'^\d+:\d+:\d+ - ')


class UILogger:
    """Writes timestamped messages to a tkinter ScrolledText and an optional file.

    Why: decouples callers from both the widget reference and the file handle.
    """

    MAX_WIDGET_LINES = 1000
    TRIM_TO_LINE     = 50

    def __init__(
        self,
        widget: tk.Text,
        log_file_path: Optional[str] = None,
        track_date_changes: bool = False,
    ) -> None:
        self._widget = widget
        self._log_file_path = log_file_path
        self._track_date_changes = track_date_changes
        self._current_log_day = datetime.now().day

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, text: str, newline: bool = True) -> None:
        """Append *text* to the widget and optionally to the log file."""
        text = _TIMESTAMP_RE.sub("", text)

        self._maybe_insert_date_change()

        timestamp = time.strftime("[%H:%M:%S] ")
        final_text = f"{timestamp}{text}" if text.strip() else text

        self._write_to_widget(final_text, newline)
        self._write_to_file(final_text, newline)

    def set_file(self, path: str) -> None:
        """Switch the backing log file (e.g. after reconnect)."""
        self._log_file_path = path

    # ── Internals ─────────────────────────────────────────────────────────────

    def _maybe_insert_date_change(self) -> None:
        """Insert a date-change banner when the calendar day rolls over."""
        if not self._track_date_changes:
            return
        now = datetime.now()
        if now.day != self._current_log_day:
            self._current_log_day = now.day
            banner = f"--- Date Changed: {now.ctime()} ---"
            self._write_to_widget(banner, newline=True)
            self._write_to_file(banner, newline=True)

    def _write_to_widget(self, text: str, newline: bool) -> None:
        try:
            self._widget.config(state="normal")
            self._widget.insert(tk.END, text + ("\n" if newline else ""))
            # Prevent unbounded growth
            if float(self._widget.index("end")) > self.MAX_WIDGET_LINES:
                self._widget.delete("1.0", f"{self.TRIM_TO_LINE}.0")
            self._widget.see(tk.END)
            self._widget.config(state="disabled")
        except Exception:
            pass  # widget may be destroyed during shutdown

    def _write_to_file(self, text: str, newline: bool) -> None:
        if not self._log_file_path:
            return
        try:
            with open(self._log_file_path, "a", encoding="utf-8") as f:
                f.write(text + ("\n" if newline else ""))
        except Exception:
            pass

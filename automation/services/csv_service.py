"""CSV auto-save service for WM pulse data.

Handles file creation, midnight rollover, and writing two-row transitions
so an Excel Scatter chart renders a square wave.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from tkinter import messagebox
from typing import Optional


class CsvService:
    """Writes WM pulse state transitions to a daily CSV file.

    Why: isolates all file-I/O from the WM pulse tracking logic so each can
    be tested and maintained independently.
    """

    CSV_HEADER = ["Time", "WM1", "WM2", "WM3", "WM4", "WM5"]
    MAX_CONSECUTIVE_ERRORS = 5

    def __init__(self, logs_dir: str) -> None:
        self._logs_dir = logs_dir
        self._file: Optional[object] = None   # open file handle
        self._writer: Optional[csv.writer] = None
        self._current_date: Optional[datetime.date] = None
        self._path: Optional[str] = None
        self._error_count: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def write_row(
        self,
        timestamp: datetime,
        changed_wm_id: int,
        new_state: int,
        wm_pulse_states: dict[int, int],
    ) -> None:
        """Append a before/after row pair for a single pulse-state transition.

        Writing TWO rows at the same timestamp creates a perfect vertical edge
        in an Excel Scatter-with-Lines chart → square-wave appearance.
        """
        # Midnight rollover
        if self._current_date and timestamp.date() != self._current_date:
            self.close()

        # Lazy open
        if self._writer is None:
            self._open()
        if self._writer is None:
            return

        t_str = timestamp.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm
        try:
            # Row 1: state BEFORE transition (changed WM has the opposite value)
            old_states = [
                wm_pulse_states[i] if i != changed_wm_id else (1 - new_state)
                for i in range(1, 6)
            ]
            self._writer.writerow([t_str] + old_states)

            # Row 2: state AFTER transition
            new_states = [wm_pulse_states[i] for i in range(1, 6)]
            self._writer.writerow([t_str] + new_states)

            self._file.flush()
            self._error_count = 0
        except Exception as exc:
            self._error_count += 1
            print(f"[CsvService] Write error: {exc}")
            if self._error_count == 1:
                messagebox.showwarning(
                    "WM CSV Write Error",
                    f"Cannot write to CSV file.\n\nReason: {exc}\n\n"
                    "Is the file open in Excel?\n"
                    "Close it in Excel and click Reset Graph to restart recording.",
                )
            if self._error_count >= self.MAX_CONSECUTIVE_ERRORS:
                print("[CsvService] Too many errors – stopping CSV recording.")
                self.close()

    def close(self) -> None:
        """Flush and close the current CSV file if open."""
        if self._file:
            try:
                self._file.flush()
                self._file.close()
            except Exception:
                pass
        self._file = None
        self._writer = None

    # ── Internals ─────────────────────────────────────────────────────────────

    def _open(self) -> None:
        """Open (or append to) today's CSV file."""
        self.close()
        today = datetime.now().date()
        fname = f"wm_pulses_{today.strftime('%Y-%m-%d')}.csv"
        os.makedirs(self._logs_dir, exist_ok=True)
        path = os.path.join(self._logs_dir, fname)
        try:
            self._file = open(path, "a", newline="", encoding="utf-8")
            self._writer = csv.writer(self._file)
            self._current_date = today
            self._path = path
            self._error_count = 0
            # Write header only for new/empty files
            if self._file.tell() == 0:
                self._writer.writerow(self.CSV_HEADER)
                self._file.flush()
        except Exception as exc:
            self._file = self._writer = None
            messagebox.showwarning(
                "WM CSV Error",
                f"Cannot create CSV file:\n{path}\n\nReason: {exc}\n\n"
                "Pulse data will NOT be saved.",
            )
            print(f"[CsvService] Cannot open {path}: {exc}")

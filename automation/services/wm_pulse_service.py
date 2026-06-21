"""WM pulse tracking service.

Schedules simulated pulse toggling via tkinter's after() mechanism,
feeds data to the CSV service, and notifies listeners when data changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

import tkinter as tk

from automation.config.settings import (
    WM_COUNT,
    WM_GRAPH_WINDOW_SECONDS,
    WM_GRAPH_POST_STOP_SECONDS,
    WM_GRAPH_REFRESH_MS,
)
from automation.services.csv_service import CsvService


class WmPulseService:
    """Manages pulse generation, state tracking, and graph data for WMs 1–5.

    Why: separates the timing / data-accumulation responsibility from both
    the serial-read logic (which triggers start/stop) and the graph widget
    (which only reads data snapshots).
    """

    def __init__(
        self,
        root: tk.Tk,
        csv_service: CsvService,
        on_data_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        self._root = root
        self._csv = csv_service
        self._on_data_changed: Callable[[], None] = on_data_changed or (lambda: None)

        # Per-WM state
        self.pulse_data:  dict[int, list[tuple[datetime, int]]] = {i: [] for i in range(1, WM_COUNT + 1)}
        self.pulse_state: dict[int, int]  = {i: 0 for i in range(1, WM_COUNT + 1)}
        self.active:      dict[int, bool] = {i: False for i in range(1, WM_COUNT + 1)}
        self._after_ids:  dict[int, Optional[str]] = {i: None for i in range(1, WM_COUNT + 1)}
        self._rate_vars:  dict[int, tk.StringVar] = {}   # injected from UI

        # Graph refresh
        self._graph_refresh_id: Optional[str] = None
        self._all_stopped_time: Optional[datetime] = None

        # Rate-change debounce
        self._rate_debounce_ids: dict[int, Optional[str]] = {i: None for i in range(1, WM_COUNT + 1)}

    # ── Rate StringVar registration ───────────────────────────────────────────

    def register_rate_var(self, wm_id: int, var: tk.StringVar) -> None:
        """Register the UI rate StringVar for *wm_id* so the service can read it."""
        self._rate_vars[wm_id] = var
        var.trace_add("write", lambda *_, w=wm_id: self._on_rate_change(w))

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self, wm_id: int) -> None:
        """Begin pulse toggling for *wm_id*."""
        if not (1 <= wm_id <= WM_COUNT):
            return
        # Treat repeated start as a live cycle update request.
        if self.active[wm_id]:
            self._apply_rate_change(wm_id)
            self._ensure_graph_refresh()
            return
        self.active[wm_id] = True
        self._schedule_toggle(wm_id)
        self._ensure_graph_refresh()

    def stop(self, wm_id: int) -> None:
        """Halt pulse toggling for *wm_id* and record a final LOW state."""
        if not (1 <= wm_id <= WM_COUNT):
            return
        pending_rate = self._rate_debounce_ids.get(wm_id)
        if pending_rate is not None:
            self._root.after_cancel(pending_rate)
            self._rate_debounce_ids[wm_id] = None
        self.active[wm_id] = False
        if self._after_ids[wm_id] is not None:
            self._root.after_cancel(self._after_ids[wm_id])
            self._after_ids[wm_id] = None
        self.pulse_state[wm_id] = 0
        now = datetime.now()
        self.pulse_data[wm_id].append((now, 0))
        self._csv.write_row(now, wm_id, 0, self.pulse_state)
        self._on_data_changed()

    def reset(self) -> None:
        """Stop all WMs and clear all accumulated data."""
        for wm_id in range(1, WM_COUNT + 1):
            self.active[wm_id] = False
            if self._after_ids[wm_id] is not None:
                self._root.after_cancel(self._after_ids[wm_id])
                self._after_ids[wm_id] = None
        if self._graph_refresh_id is not None:
            self._root.after_cancel(self._graph_refresh_id)
            self._graph_refresh_id = None
        self.pulse_data  = {i: [] for i in range(1, WM_COUNT + 1)}
        self.pulse_state = {i: 0 for i in range(1, WM_COUNT + 1)}
        self._csv.close()
        self._on_data_changed()

    # ── Rate-change handling ──────────────────────────────────────────────────

    def _on_rate_change(self, wm_id: int) -> None:
        """Debounce rate-entry keystrokes; apply after 500 ms silence."""
        pending = self._rate_debounce_ids.get(wm_id)
        if pending:
            self._root.after_cancel(pending)
        # Keep the graph responsive while user edits a cycle value.
        self._on_data_changed()
        self._rate_debounce_ids[wm_id] = self._root.after(
            500, self._apply_rate_change, wm_id
        )

    def _apply_rate_change(self, wm_id: int) -> None:
        """Re-anchor the toggle timer when the rate changes while running."""
        self._rate_debounce_ids[wm_id] = None
        if not self.active[wm_id]:
            return
        try:
            val = float(self._rate_vars[wm_id].get().strip())
            if val <= 0:
                return
        except (ValueError, AttributeError):
            return
        # Cancel pending toggle and re-schedule immediately at the new rate
        if self._after_ids[wm_id] is not None:
            self._root.after_cancel(self._after_ids[wm_id])
            self._after_ids[wm_id] = None
        self._schedule_toggle(wm_id)
        self._ensure_graph_refresh()
        self._on_data_changed()

    # ── Pulse toggle scheduling ───────────────────────────────────────────────

    def _schedule_toggle(self, wm_id: int) -> None:
        if not self.active[wm_id]:
            return
        try:
            rate = float(self._rate_vars[wm_id].get().strip())
            if rate <= 0:
                rate = 1000.0
        except (ValueError, AttributeError):
            rate = 1000.0
        half_period_ms = max(50, int(rate / 2))
        self.pulse_state[wm_id] ^= 1
        now = datetime.now()
        self.pulse_data[wm_id].append((now, self.pulse_state[wm_id]))
        self._csv.write_row(now, wm_id, self.pulse_state[wm_id], self.pulse_state)
        # Trim data older than the rolling window
        cutoff = now - timedelta(seconds=WM_GRAPH_WINDOW_SECONDS)
        self.pulse_data[wm_id] = [
            (t, v) for t, v in self.pulse_data[wm_id] if t >= cutoff
        ]
        self._after_ids[wm_id] = self._root.after(
            half_period_ms, self._schedule_toggle, wm_id
        )
        # Push immediate repaint signal on every edge update.
        self._on_data_changed()

    # ── Graph refresh loop ────────────────────────────────────────────────────

    def _ensure_graph_refresh(self) -> None:
        if self._graph_refresh_id is None:
            self._graph_refresh()

    def _graph_refresh(self) -> None:
        self._graph_refresh_id = None
        self._on_data_changed()
        if any(self.active.values()):
            self._all_stopped_time = None
            self._graph_refresh_id = self._root.after(WM_GRAPH_REFRESH_MS, self._graph_refresh)
        else:
            if self._all_stopped_time is None:
                self._all_stopped_time = datetime.now()
            elapsed = (datetime.now() - self._all_stopped_time).total_seconds()
            if elapsed < WM_GRAPH_POST_STOP_SECONDS:
                self._graph_refresh_id = self._root.after(WM_GRAPH_REFRESH_MS, self._graph_refresh)

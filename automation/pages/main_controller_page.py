"""Main Controller tab (Tab 1).

Responsibilities:
  - Serial port 1 connection UI
  - Quick-command buttons (system init, get time, set time, set DAC)
  - Terminal output display
  - Pinout mapping table
  - WM Pulse Monitor graph
"""

from __future__ import annotations

import re
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

from automation.config.settings import (
    BAUD_RATES, LINE_ENDINGS, DEFAULT_BAUD_INDEX, DEFAULT_LINE_END_INDEX,
    PINOUT_DATA, WM_COUNT, WM_COLORS, WM_OFFSETS,
)
from automation.pages.base_page import BasePage
from automation.utils.logger import UILogger

if TYPE_CHECKING:
    from automation.main import FlexTesterApp


class MainControllerPage(BasePage):
    """Tab 1 — Main Controller."""

    def build(self) -> None:
        main_pane = tk.PanedWindow(self.parent, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame  = ttk.Frame(main_pane)
        right_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame,  minsize=600)
        main_pane.add(right_frame, minsize=300)

        self._build_connection_frame(left_frame)
        self._build_commands_frame(left_frame)
        self._build_terminal_frame(left_frame)
        self._build_pinout_frame(right_frame)
        self._build_wm_graph_frame(right_frame)

    # ── Connection settings ───────────────────────────────────────────────────

    def _build_connection_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Connection Settings")
        frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(frame, text="Port:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(frame, width=10)
        self.port_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Baud:").pack(side=tk.LEFT)
        self.baud_combo = ttk.Combobox(frame, width=8, values=BAUD_RATES)
        self.baud_combo.current(DEFAULT_BAUD_INDEX)
        self.baud_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Line End:").pack(side=tk.LEFT)
        self.line_end_combo = ttk.Combobox(frame, width=8, values=LINE_ENDINGS)
        self.line_end_combo.current(DEFAULT_LINE_END_INDEX)
        self.line_end_combo.pack(side=tk.LEFT, padx=5)

        self.btn_connect = ttk.Button(frame, text="Connect", command=self.app.toggle_connection_1)
        self.btn_connect.pack(side=tk.LEFT, padx=10)

        ttk.Button(frame, text="Refresh Ports", command=self.app.refresh_ports).pack(side=tk.LEFT)

    # ── Quick commands ────────────────────────────────────────────────────────

    def _build_commands_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Commands")
        frame.pack(fill=tk.X, padx=5, pady=5)

        r1 = ttk.Frame(frame)
        r1.pack(fill=tk.X, pady=2)
        for label, cmd in [("System Init", "system init"), ("Get Time", "get time"),
                           ("Get Status", "get status"), ("Help", "help")]:
            ttk.Button(r1, text=label, command=lambda c=cmd: self.app.send_command_1(c)).pack(side=tk.LEFT, padx=5)

        r2 = ttk.Frame(frame)
        r2.pack(fill=tk.X, pady=2)
        ttk.Button(r2, text="Set Time", command=self._cmd_set_time).pack(side=tk.LEFT, padx=5)
        self.entry_time = ttk.Entry(r2, width=10)
        self.entry_time.insert(0, "12:00")
        self.entry_time.pack(side=tk.LEFT, padx=5)
        ttk.Label(r2, text="(HH:MM)").pack(side=tk.LEFT)

        r4 = ttk.Frame(frame)
        r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text="DAC (mV):").pack(side=tk.LEFT, padx=5)
        self.entry_dac = ttk.Entry(r4, width=8)
        self.entry_dac.insert(0, "1500")
        self.entry_dac.pack(side=tk.LEFT)
        ttk.Button(r4, text="Set DAC", command=self._cmd_set_dac).pack(side=tk.LEFT, padx=5)

    def _cmd_set_time(self) -> None:
        self.app.send_command_1(f"set time {self.entry_time.get()}")

    def _cmd_set_dac(self) -> None:
        self.app.send_command_1(f"set dac {self.entry_dac.get()}")

    # ── Terminal output ───────────────────────────────────────────────────────

    def _build_terminal_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Terminal Output")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_area = scrolledtext.ScrolledText(
            frame, state="disabled", height=15,
            bg="white", fg="black", font=("Consolas", 10),
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Clear Output",
                   command=lambda: self._clear_terminal(self.text_area)).pack(anchor=tk.E, pady=2)

    @staticmethod
    def _clear_terminal(widget: tk.Text) -> None:
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.config(state="disabled")

    # ── Pinout mapping ────────────────────────────────────────────────────────

    def _build_pinout_frame(self, parent: ttk.Frame) -> None:
        frame   = ttk.LabelFrame(parent, text="Pinout Mapping")
        frame.pack(fill=tk.X, padx=5, pady=5)
        columns = ("Function", "Pin", "Description")
        tree    = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for col, width in zip(columns, (80, 60, 120)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        for item in PINOUT_DATA:
            tree.insert("", tk.END, values=item)

    # ── WM Pulse Monitor ──────────────────────────────────────────────────────

    def _build_wm_graph_frame(self, parent: ttk.Frame) -> None:
        outer = ttk.LabelFrame(parent, text="WM Pulse Monitor")
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cb_frame = ttk.Frame(outer)
        cb_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(cb_frame, text="Show",     font=("", 8, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(cb_frame, text="Cycle ms", font=("", 8, "bold")).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(cb_frame, text="Start",    font=("", 8, "bold")).grid(row=0, column=2, sticky="w", padx=1)
        ttk.Label(cb_frame, text="Stop",     font=("", 8, "bold")).grid(row=0, column=3, sticky="w", padx=1)
        ttk.Label(cb_frame, text="Trigger",  font=("", 8, "bold")).grid(row=0, column=4, sticky="w", padx=1)

        self.wm_show_vars: dict[int, tk.BooleanVar] = {}
        self.wm_rate_vars: dict[int, tk.StringVar]  = {}

        wm_svc = self.app.wm_pulse_service
        for i in range(1, WM_COUNT + 1):
            show_var = tk.BooleanVar(value=True)
            rate_var = tk.StringVar(value="1000")
            self.wm_show_vars[i] = show_var
            self.wm_rate_vars[i] = rate_var
            wm_svc.register_rate_var(i, rate_var)

            ttk.Checkbutton(cb_frame, text=f"WM {i}", variable=show_var,
                            command=self.redraw_graph).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(cb_frame, textvariable=rate_var, width=5).grid(row=i, column=1, padx=2, pady=2)
            ttk.Button(cb_frame, text="▶", width=2,
                       command=lambda wid=i: self._cmd_wm_start(wid)).grid(row=i, column=2, padx=1)
            ttk.Button(cb_frame, text="■", width=2,
                       command=lambda wid=i: self._cmd_wm_stop(wid)).grid(row=i, column=3, padx=1)
            ttk.Button(cb_frame, text="T", width=2,
                       command=lambda wid=i: self.app.send_command_1(
                           f"trigger wm {wid} {self.wm_rate_vars[wid].get()}"
                       )).grid(row=i, column=4, padx=1)

        ttk.Button(cb_frame, text="Reset Graph",
                   command=self._cmd_reset_graph).grid(row=6, column=0, columnspan=5, pady=8, sticky="ew")

        fig_frame = ttk.Frame(outer)
        fig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._wm_fig = Figure(figsize=(4, 3), dpi=80)
        self._wm_fig.set_tight_layout(True)
        self._wm_ax  = self._wm_fig.add_subplot(111)
        self._wm_ax.set_ylabel("Pulses")
        self._wm_ax.set_xlabel("Time")
        self._wm_ax.set_title("WM Cumulative Pulses")
        self._wm_canvas = FigureCanvasTkAgg(self._wm_fig, master=fig_frame)
        self._wm_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ── WM control commands ───────────────────────────────────────────────────

    def _cmd_wm_start(self, wm_id: int) -> None:
        self.app.send_command_1(f"start wm {wm_id} {self.wm_rate_vars[wm_id].get()}")
        self.app.wm_pulse_service.start(wm_id)

    def _cmd_wm_stop(self, wm_id: int) -> None:
        self.app.send_command_1(f"stop wm {wm_id}")
        self.app.wm_pulse_service.stop(wm_id)

    def _cmd_reset_graph(self) -> None:
        self.app.wm_pulse_service.reset()

    # ── Graph rendering ───────────────────────────────────────────────────────

    def redraw_graph(self) -> None:
        """Redraw the WM pulse graph from current service data."""
        if not hasattr(self, "_wm_ax"):
            return
        self._wm_ax.clear()
        self._wm_ax.set_xlabel("Time")
        self._wm_ax.set_title("WM Pulse Signal (Real-time)")
        ytick_pos: list[float] = []
        ytick_lbl: list[str]   = []
        has_data = False
        pulse_data = self.app.wm_pulse_service.pulse_data

        for wm_id in range(1, WM_COUNT + 1):
            offset = WM_OFFSETS[wm_id]
            ytick_pos.append(offset + 0.5)
            ytick_lbl.append(f"WM {wm_id}")
            if not self.wm_show_vars[wm_id].get():
                continue
            self._wm_ax.axhline(y=offset, color=WM_COLORS[wm_id],
                                linewidth=0.5, linestyle="--", alpha=0.4)
            data = pulse_data[wm_id]
            if data:
                times = [t for t, _ in data]
                vals  = [v + offset for _, v in data]
                self._wm_ax.step(times, vals, where="post",
                                 color=WM_COLORS[wm_id], linewidth=1.5)
                has_data = True

        self._wm_ax.set_yticks(ytick_pos)
        self._wm_ax.set_yticklabels(ytick_lbl, fontsize=8)
        self._wm_ax.set_ylim(-0.2, 7.2)

        if has_data or any(len(pulse_data[i]) > 0 for i in range(1, WM_COUNT + 1)):
            now     = datetime.now()
            x_start = now - timedelta(seconds=120)
            x_end   = now + timedelta(seconds=10)
            self._wm_ax.set_xlim(mdates.date2num(x_start), mdates.date2num(x_end))
            self._wm_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            self._wm_fig.autofmt_xdate()

        self._wm_canvas.draw_idle()

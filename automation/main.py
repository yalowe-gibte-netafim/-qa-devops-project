"""Entry point for the FLEX Tester automation framework.

Run from the project root:
    python -m automation.main

or:
    python automation/main.py
"""

from __future__ import annotations

import os
import re
import sys
import time
import threading

# Allow running as a script from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, messagebox

from automation.config.settings import (
    APP_TITLE, APP_GEOMETRY, LOGS_DIR_NAME, LINE_ENDING_MAP,
)
from automation.services.serial_service import SerialService
from automation.services.wm_pulse_service import WmPulseService
from automation.services.csv_service import CsvService
from automation.flows.init_flow import InitFlow
from automation.flows.analysis_flow import AnalysisFlow
from automation.pages.main_controller_page import MainControllerPage
from automation.pages.flex_cli_page import FlexCliPage
from automation.pages.log_analyzer_page import LogAnalyzerPage
from automation.utils.logger import UILogger
from automation.exceptions.custom_exceptions import SerialConnectionError

# Patterns for detecting valve/wm events in port-1 serial data
_VALVE_OPEN_RE  = re.compile(r"valve (\d+) open")
_VALVE_CLOSE_RE = re.compile(r"valve (\d+) close")
_WM_START_RE    = re.compile(r"wm (\d+) started working")
_WM_STOP_RE     = re.compile(r"wm (\d+) stopped working")


class FlexTesterApp:
    """Root application class — wires all services, flows, and pages together.

    Why: keeps the tkinter root, service instantiation, and cross-cutting
    wiring in one place so individual pages and services stay focused.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(APP_GEOMETRY)

        # ── Filesystem ─────────────────────────────────────────────────────
        self._logs_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), LOGS_DIR_NAME
        )
        os.makedirs(self._logs_dir, exist_ok=True)

        timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S")
        self._terminal_log_path = os.path.join(
            self._logs_dir, f"terminal_log_{timestamp_str}.txt"
        )
        try:
            with open(self._terminal_log_path, "w") as f:
                f.write(f"--- Log Started: {time.ctime()} ---\n")
        except Exception as exc:
            print(f"Error creating log file: {exc}")

        # ── Services ───────────────────────────────────────────────────────
        self._csv_service = CsvService(self._logs_dir)
        self.wm_pulse_service = WmPulseService(
            root=root,
            csv_service=self._csv_service,
            on_data_changed=self._on_wm_data_changed,
        )
        self._serial_1 = SerialService(on_line_received=self._on_port1_line)
        self._serial_2 = SerialService(on_line_received=self._on_port2_line)

        # ── Loggers (created after pages are built) ────────────────────────
        self._logger_1: UILogger | None = None
        self._logger_2: UILogger | None = None

        # ── Flows ──────────────────────────────────────────────────────────
        self.analysis_flow = AnalysisFlow(
            logs_dir=self._logs_dir,
            on_line=self._analysis_printer,
        )
        self._init_flow = InitFlow(send_fn=self.send_command_2)

        # ── CLI log (port 2) ───────────────────────────────────────────────
        self._cli_log_path: str | None = None

        # ── Build UI ───────────────────────────────────────────────────────
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        style.configure("TLabel",  padding=6)

        self._notebook = ttk.Notebook(root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tab1 = ttk.Frame(self._notebook)
        tab2 = ttk.Frame(self._notebook)
        tab4 = ttk.Frame(self._notebook)
        self._notebook.add(tab1, text="Main Controller")
        self._notebook.add(tab2, text="FLEX CLI")
        self._notebook.add(tab4, text="Log Analyzer")

        self._page1 = MainControllerPage(tab1, self)
        self._page1.build()

        self._page2 = FlexCliPage(tab2, self)
        self._page2.build()

        self._page4 = LogAnalyzerPage(tab4, self)
        self._page4.build()

        # ── Wire loggers now that widgets exist ────────────────────────────
        self._logger_1 = UILogger(
            widget=self._page1.text_area,
            log_file_path=self._terminal_log_path,
            track_date_changes=True,
        )
        self._logger_2 = UILogger(
            widget=self._page2.text_area_2,
            log_file_path=None,  # set when CLI connects
        )

        # Initial port population
        self.refresh_ports()

    # ── Port management ───────────────────────────────────────────────────────

    def refresh_ports(self) -> None:
        """Repopulate both port combo-boxes with available COM ports."""
        ports = SerialService.list_ports()
        for combo in (self._page1.port_combo, self._page2.port_combo_2):
            combo["values"] = ports
            if ports and not combo.get():
                combo.current(0)

    # ── Port 1 (Main Controller) ──────────────────────────────────────────────

    def toggle_connection_1(self) -> None:
        if not self._serial_1.is_connected:
            port = self._page1.port_combo.get()
            if self._serial_2.is_connected and self._serial_2.port_name == port:
                messagebox.showerror("Connection Error", f"{port} is already in use by FLEX CLI.")
                return
            try:
                baud = int(self._page1.baud_combo.get())
                self._serial_1.connect(port, baud)
                self._page1.btn_connect.config(text="Disconnect")
                self._logger_1.log(f"Connected to {port}")
            except Exception as exc:
                messagebox.showerror("Connection Error", str(exc))
        else:
            self._serial_1.disconnect()
            self._page1.btn_connect.config(text="Connect")
            self._logger_1.log("Disconnected")

    def send_command_1(self, cmd: str) -> None:
        """Send *cmd* on port 1 using the selected line ending."""
        if not self._serial_1.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a COM port first.")
            return
        line_end = LINE_ENDING_MAP.get(self._page1.line_end_combo.get(), "\n")
        try:
            self._serial_1.send(cmd, line_end)
            self._logger_1.log(f"> {cmd}\n")
        except SerialConnectionError as exc:
            self._logger_1.log(f"Error sending: {exc}\n")

    def _on_port1_line(self, line: str) -> None:
        """Callback fired by SerialService on each received line (background thread)."""
        # Detect valve/wm events and control WM pulse service
        if m := _VALVE_OPEN_RE.search(line):
            wm_id = int(m.group(1))
            if 1 <= wm_id <= 5:
                self.root.after(0, self.wm_pulse_service.start, wm_id)
        elif m := _VALVE_CLOSE_RE.search(line):
            wm_id = int(m.group(1))
            if 1 <= wm_id <= 5:
                self.root.after(0, self.wm_pulse_service.stop, wm_id)
        elif m := _WM_START_RE.search(line):
            wm_id = int(m.group(1))
            if 1 <= wm_id <= 5:
                self.root.after(0, self.wm_pulse_service.start, wm_id)
        elif m := _WM_STOP_RE.search(line):
            wm_id = int(m.group(1))
            if 1 <= wm_id <= 5:
                self.root.after(0, self.wm_pulse_service.stop, wm_id)
        # Log every line to the UI (must use after() — tkinter is not thread-safe)
        self.root.after(0, self._logger_1.log, line, True)

    # ── Port 2 (FLEX CLI) ─────────────────────────────────────────────────────

    def toggle_connection_2(self) -> None:
        if not self._serial_2.is_connected:
            port = self._page2.port_combo_2.get()
            if self._serial_1.is_connected and self._serial_1.port_name == port:
                messagebox.showerror("Connection Error", f"{port} is already in use by Main Controller.")
                return
            try:
                baud = int(self._page2.baud_combo_2.get())
                self._serial_2.connect(port, baud)
                self._page2.btn_connect_2.config(text="Disconnect")

                cli_ts = time.strftime("%Y-%m-%d_%H-%M-%S")
                self._cli_log_path = os.path.join(
                    self._logs_dir, f"FLEX CLI LOGS {cli_ts}.txt"
                )
                try:
                    with open(self._cli_log_path, "w") as f:
                        f.write(f"--- FLEX CLI Log Started: {time.ctime()} ---\n")
                        f.write(f"--- Port: {port} | Baud: {baud} ---\n")
                except Exception as exc:
                    print(f"Error creating CLI log file: {exc}")
                    self._cli_log_path = None

                self._logger_2.set_file(self._cli_log_path)
                self._logger_2.log(f"Connected to {port}")
            except Exception as exc:
                messagebox.showerror("Connection Error", str(exc))
        else:
            self._serial_2.disconnect()
            self._page2.btn_connect_2.config(text="Connect")
            self._logger_2.log("Disconnected")

    def send_command_2(self, cmd: str, force_lf: bool = False) -> None:
        """Send *cmd* on port 2."""
        if not self._serial_2.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a COM port first.")
            return
        line_end = "\n" if force_lf else LINE_ENDING_MAP.get(self._page2.line_end_combo_2.get(), "\n")
        try:
            self._serial_2.send(cmd, line_end)
            self._logger_2.log(f"> {cmd}\n")
        except SerialConnectionError as exc:
            self._logger_2.log(f"Error sending: {exc}\n")

    def _on_port2_line(self, line: str) -> None:
        """Callback fired by SerialService for port 2 (background thread)."""
        self.root.after(0, self._logger_2.log, line, True)

    # ── Init flow ─────────────────────────────────────────────────────────────

    def run_full_init(self) -> None:
        """Trigger the system initialisation sequence on port 2."""
        self._init_flow.run_async()

    # ── WM data changed callback ──────────────────────────────────────────────

    def _on_wm_data_changed(self) -> None:
        """Redraw the graph whenever WM pulse data changes."""
        self.root.after(0, self._page1.redraw_graph)

    # ── Analysis printer (Log Analyzer tab) ──────────────────────────────────

    def _analysis_printer(self, msg: str) -> None:
        """Write analysis output to the results widget (thread-safe via after())."""
        self.root.after(0, self._write_analysis_line, msg)

    def _write_analysis_line(self, msg: str) -> None:
        try:
            self._page4.analysis_text.config(state="normal")
            self._page4.analysis_text.insert(tk.END, msg + "\n")
            self._page4.analysis_text.see(tk.END)
            self._page4.analysis_text.config(state="disabled")
        except Exception:
            pass

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def on_close(self) -> None:
        """Graceful shutdown: close CSV, disconnect serial ports, destroy window."""
        self._csv_service.close()
        if self._serial_1.is_connected:
            self._serial_1.disconnect()
        if self._serial_2.is_connected:
            self._serial_2.disconnect()
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = FlexTesterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

"""Log Analyzer tab (Tab 4).

Responsibilities:
  - Load external log file
  - Load JSON config file
  - Trigger analysis flow
  - Display analysis results
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from typing import TYPE_CHECKING

from automation.pages.base_page import BasePage

if TYPE_CHECKING:
    from automation.main import FlexTesterApp


class LogAnalyzerPage(BasePage):
    """Tab 4 — Log Analyzer."""

    def build(self) -> None:
        self._loaded_log_content: str = ""
        self._config_file_path: str   = "test_config.json"

        self._build_controls_frame()
        self._build_results_frame()

        # Auto-select a config if one exists in the project root
        if os.path.exists(self._config_file_path):
            self._lbl_config.config(text=f"Loaded: {os.path.basename(self._config_file_path)}")

    # ── Controls ──────────────────────────────────────────────────────────────

    def _build_controls_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Controls")
        frame.pack(fill=tk.X, padx=10, pady=10)

        r1 = ttk.Frame(frame)
        r1.pack(fill=tk.X, pady=2)
        ttk.Button(r1, text="Load Log File",      command=self._load_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(r1, text="Load Config (JSON)", command=self._load_config).pack(side=tk.LEFT, padx=5)
        self._lbl_config = ttk.Label(r1, text="No Config Loaded")
        self._lbl_config.pack(side=tk.LEFT, padx=5)

        r2 = ttk.Frame(frame)
        r2.pack(fill=tk.X, pady=5)
        ttk.Button(r2, text="Run Test Scenario", command=self._run_analysis).pack(side=tk.LEFT, padx=5)

    # ── Results area ──────────────────────────────────────────────────────────

    def _build_results_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Analysis Results")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.analysis_text = scrolledtext.ScrolledText(
            frame, state="disabled", height=20,
            bg="#f0f0f0", font=("Consolas", 10),
        )
        self.analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ── File loading ──────────────────────────────────────────────────────────

    def _load_log(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                self._loaded_log_content = f.read()
            messagebox.showinfo("Success", f"Loaded {len(self._loaded_log_content)} bytes.")
            self.analysis_text.config(state="normal")
            self.analysis_text.delete("1.0", tk.END)
            self.analysis_text.insert(tk.END, f"Loaded log: {path}\n")
            self.analysis_text.config(state="disabled")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load file: {exc}")

    def _load_config(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if path:
            self._config_file_path = path
            self._lbl_config.config(text=f"Loaded: {os.path.basename(path)}")

    # ── Analysis trigger ──────────────────────────────────────────────────────

    def _run_analysis(self) -> None:
        if not self._loaded_log_content:
            messagebox.showwarning("Warning", "Please load a log file first.")
            return
        if not self._config_file_path:
            messagebox.showwarning("Warning", "Please load a JSON configuration file first.")
            return

        self.analysis_text.config(state="normal")
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert(tk.END, f"--- Running Test Scenario --- {time.ctime()} ---\n")
        self.analysis_text.config(state="disabled")

        # Run in a background thread so the UI stays responsive
        import threading
        threading.Thread(
            target=self.app.analysis_flow.run,
            args=(self._loaded_log_content, self._config_file_path),
            daemon=True,
        ).start()

"""FLEX CLI tab (Tab 2).

Responsibilities:
  - Serial port 2 connection UI
  - System initialisation trigger
  - CLI command builder (category + action + args)
  - Free-text send entry
  - Terminal output display
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING

from automation.config.settings import (
    BAUD_RATES, LINE_ENDINGS, DEFAULT_BAUD_INDEX, DEFAULT_LINE_END_INDEX,
    CLI_COMMANDS,
)
from automation.pages.base_page import BasePage

if TYPE_CHECKING:
    from automation.main import FlexTesterApp


class FlexCliPage(BasePage):
    """Tab 2 — FLEX CLI."""

    def build(self) -> None:
        self._build_connection_frame()
        self._build_init_frame()
        self._build_command_builder_frame()
        self._build_send_frame()
        self._build_terminal_frame()

    # ── Connection settings ───────────────────────────────────────────────────

    def _build_connection_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Secondary Connection Settings")
        frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(frame, text="Port:").pack(side=tk.LEFT)
        self.port_combo_2 = ttk.Combobox(frame, width=10)
        self.port_combo_2.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Baud:").pack(side=tk.LEFT)
        self.baud_combo_2 = ttk.Combobox(frame, width=8, values=BAUD_RATES)
        self.baud_combo_2.current(DEFAULT_BAUD_INDEX)
        self.baud_combo_2.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Line End:").pack(side=tk.LEFT)
        self.line_end_combo_2 = ttk.Combobox(frame, width=8, values=LINE_ENDINGS)
        self.line_end_combo_2.current(DEFAULT_LINE_END_INDEX)
        self.line_end_combo_2.pack(side=tk.LEFT, padx=5)

        self.btn_connect_2 = ttk.Button(frame, text="Connect", command=self.app.toggle_connection_2)
        self.btn_connect_2.pack(side=tk.LEFT, padx=10)

        ttk.Button(frame, text="Refresh Ports", command=self.app.refresh_ports).pack(side=tk.LEFT)

    # ── System initialisation ─────────────────────────────────────────────────

    def _build_init_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="System Initialization")
        frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(frame, text="Run Config Settings",
                   command=self.app.run_full_init).pack(side=tk.LEFT, padx=5)

    # ── Command builder ───────────────────────────────────────────────────────

    def _build_command_builder_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Command Builder")
        frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame, text="Category:").pack(side=tk.LEFT, padx=5)
        self.cmd_cat_combo = ttk.Combobox(frame, width=10, state="readonly",
                                          values=list(CLI_COMMANDS.keys()))
        self.cmd_cat_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Action:").pack(side=tk.LEFT, padx=5)
        self.cmd_act_combo = ttk.Combobox(frame, width=10, state="readonly")
        self.cmd_act_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Args:").pack(side=tk.LEFT, padx=5)
        self.cmd_args_entry = ttk.Entry(frame, width=20)
        self.cmd_args_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(frame, text="Send", command=self._send_builder_command).pack(side=tk.LEFT, padx=10)

        self.cmd_cat_combo.bind("<<ComboboxSelected>>", self._update_action_combo)
        if CLI_COMMANDS:
            self.cmd_cat_combo.current(0)
            self._update_action_combo(None)

    def _update_action_combo(self, _event) -> None:
        cat     = self.cmd_cat_combo.get()
        actions = CLI_COMMANDS.get(cat, [])
        self.cmd_act_combo["values"] = actions
        if actions:
            self.cmd_act_combo.current(0)
        else:
            self.cmd_act_combo.set("")

    def _send_builder_command(self) -> None:
        cat  = self.cmd_cat_combo.get()
        act  = self.cmd_act_combo.get()
        args = self.cmd_args_entry.get()
        cmd  = f"{cat} {act}" + (f" {args}" if args else "")
        self.app.send_command_2(cmd)

    # ── Free-text send ────────────────────────────────────────────────────────

    def _build_send_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Send Data")
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.entry_send_2 = ttk.Entry(frame)
        self.entry_send_2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.entry_send_2.bind("<Return>", lambda _: self._on_send_entry())
        ttk.Button(frame, text="Send", command=self._on_send_entry).pack(side=tk.LEFT, padx=5)

    def _on_send_entry(self) -> None:
        cmd = self.entry_send_2.get()
        self.app.send_command_2(cmd)
        self.entry_send_2.delete(0, tk.END)

    # ── Terminal output ───────────────────────────────────────────────────────

    def _build_terminal_frame(self) -> None:
        frame = ttk.LabelFrame(self.parent, text="Terminal Output")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text_area_2 = scrolledtext.ScrolledText(
            frame, state="disabled", height=15,
            bg="white", fg="black", font=("Consolas", 10),
        )
        self.text_area_2.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="Clear Output",
                   command=self._clear_terminal).pack(anchor=tk.E, pady=2)

    def _clear_terminal(self) -> None:
        self.text_area_2.config(state="normal")
        self.text_area_2.delete("1.0", tk.END)
        self.text_area_2.config(state="disabled")

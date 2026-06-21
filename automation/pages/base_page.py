"""Base page class shared by all tab pages."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.main import FlexTesterApp


class BasePage:
    """Common interface for every notebook tab.

    Why: provides a consistent constructor contract so main.py can create
    all pages the same way and call build() on each one.
    """

    def __init__(self, parent: ttk.Frame, app: "FlexTesterApp") -> None:
        self.parent = parent
        self.app    = app

    def build(self) -> None:
        """Construct all widgets inside self.parent.  Must be overridden."""
        raise NotImplementedError

"""System initialisation flow.

Sends the fixed init command sequence to port 2 with a delay between each
command, then returns.  Runs in a daemon thread so the UI stays responsive.
"""

from __future__ import annotations

import time
import threading
from typing import Callable

from automation.config.settings import INIT_COMMANDS, INIT_COMMAND_DELAY_S


class InitFlow:
    """Executes the system initialisation command sequence.

    Why: separates the 'what to send and in what order' policy from both
    the UI (which triggers it) and the serial service (which does the I/O).
    """

    def __init__(self, send_fn: Callable[[str], None]) -> None:
        """
        Args:
            send_fn: callable that accepts a command string and sends it to
                     the secondary serial port (port 2 / FLEX CLI).
        """
        self._send = send_fn

    def run_async(self) -> None:
        """Start the init sequence in a background daemon thread."""
        threading.Thread(target=self._execute, daemon=True).start()

    def _execute(self) -> None:
        for cmd in INIT_COMMANDS:
            self._send(cmd)
            time.sleep(INIT_COMMAND_DELAY_S)

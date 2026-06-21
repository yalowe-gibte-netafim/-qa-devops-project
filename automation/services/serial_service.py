"""Serial port service.

Handles connect, disconnect, background read loop, and send for a single
serial port.  All UI interaction is delegated to callbacks so this class
has no tkinter dependency.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import serial
import serial.tools.list_ports

from automation.exceptions.custom_exceptions import SerialConnectionError


class SerialService:
    """Manages one serial port connection.

    Why: isolates all pyserial usage so the rest of the app never touches
    serial.Serial directly, making it easy to mock in tests.
    """

    def __init__(
        self,
        on_line_received: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._port: Optional[serial.Serial] = None
        self._is_connected: bool = False
        self._read_thread: Optional[threading.Thread] = None
        self._stop_read: bool = False
        self._buffer: str = ""
        # Callback fired (from background thread) for every complete line received
        self._on_line_received: Callable[[str], None] = on_line_received or (lambda _: None)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def port_name(self) -> Optional[str]:
        return self._port.port if self._port else None

    # ── Connection management ─────────────────────────────────────────────────

    def connect(self, port: str, baud: int) -> None:
        """Open *port* at *baud* and start the background read thread."""
        self._port = serial.Serial(port, baud, timeout=1, dsrdtr=False, rtscts=False)
        self._port.dtr = False
        self._port.rts = False
        self._is_connected = True
        self._stop_read = False
        self._buffer = ""
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def disconnect(self) -> None:
        """Stop the read thread and close the port."""
        self._stop_read = True
        if self._port:
            self._port.close()
        self._is_connected = False

    # ── Sending ───────────────────────────────────────────────────────────────

    def send(self, cmd: str, line_end: str = "\n") -> None:
        """Send *cmd* followed by *line_end* to the open port."""
        if not self._is_connected or not self._port:
            raise SerialConnectionError("Not connected to a serial port")
        self._port.write((cmd + line_end).encode("utf-8"))

    # ── Port enumeration (static utility) ────────────────────────────────────

    @staticmethod
    def list_ports() -> list[str]:
        """Return a sorted list of available COM port device names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    # ── Background read loop ─────────────────────────────────────────────────

    def _read_loop(self) -> None:
        """Background thread: reads bytes, assembles lines, fires callback."""
        while not self._stop_read and self._port and self._port.is_open:
            try:
                if self._port.in_waiting > 0:
                    raw = self._port.read(self._port.in_waiting)
                    self._buffer += raw.decode("utf-8", errors="ignore")
                    while "\n" in self._buffer:
                        line, self._buffer = self._buffer.split("\n", 1)
                        line = line.rstrip("\r")
                        if line:
                            self._on_line_received(line)
                time.sleep(0.01)
            except Exception as exc:
                self._on_line_received(f"\nError reading: {exc}\n")
                break

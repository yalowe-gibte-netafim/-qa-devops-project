"""Automation facade service.

Provides a single entry point for automation operations while delegating to
specialized services under the hood.
"""

from __future__ import annotations

from automation.services.serial_service import SerialService
from automation.services.analysis_service import AnalysisService


class AutomationService:
    """Facade over lower-level automation services."""

    def __init__(self, serial_service: SerialService) -> None:
        self._serial_service = serial_service

    def send(self, command: str, line_end: str = "\n") -> None:
        """Send a command through the bound serial service."""
        self._serial_service.send(command, line_end)

    @staticmethod
    def create_analysis(log_content: str, config_path: str, printer):
        """Factory method for analysis engine creation."""
        return AnalysisService(log_content, config_path, printer)

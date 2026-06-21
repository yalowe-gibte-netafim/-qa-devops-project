"""Custom exception hierarchy for the FLEX Tester automation framework."""


class FlexTesterError(Exception):
    """Base exception for all FLEX Tester errors."""


class SerialConnectionError(FlexTesterError):
    """Raised when a serial port operation fails."""


class LogParseError(FlexTesterError):
    """Raised when the log file cannot be parsed."""


class ConfigLoadError(FlexTesterError):
    """Raised when the test JSON config cannot be loaded or is malformed."""


class AnalysisError(FlexTesterError):
    """Raised during test scenario analysis when a fatal error occurs."""

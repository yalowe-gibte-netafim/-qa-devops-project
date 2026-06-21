"""Business flow for report-related orchestration."""

from __future__ import annotations

from automation.flows.analysis_flow import AnalysisFlow


class ReportsFlow:
    """Facade over AnalysisFlow for report generation use-cases."""

    def __init__(self, analysis_flow: AnalysisFlow) -> None:
        self._analysis_flow = analysis_flow

    def run(self, log_content: str, config_path: str) -> None:
        """Run report analysis and persist report output."""
        self._analysis_flow.run(log_content, config_path)

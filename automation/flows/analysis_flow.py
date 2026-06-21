"""Analysis flow — orchestrates loading, parsing, running, and saving a report.

This layer sits between the UI (Log Analyzer page) and the AnalysisService,
so neither the page nor the service needs to know about file I/O or report
saving.
"""

from __future__ import annotations

import os
import time
import re
from datetime import datetime
from typing import Callable, Optional

from automation.services.analysis_service import AnalysisService


# Matches [HH:MM:SS] timestamps already embedded in log lines
_TS_RE = re.compile(r'\[(\d{2}:\d{2}:\d{2})\]')


class AnalysisFlow:
    """Runs a full log-analysis cycle and saves the report to disk.

    Why: keeps all the 'run → collect → save' orchestration out of the UI
    page so the page only has to wire callbacks and display text.
    """

    def __init__(
        self,
        logs_dir: str,
        on_line: Callable[[str], None],
    ) -> None:
        """
        Args:
            logs_dir:   directory where analysis_report_*.txt files are written.
            on_line:    callback invoked for every output line (used by the UI
                        to append text to the results widget).
        """
        self._logs_dir = logs_dir
        self._on_line  = on_line

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, log_content: str, config_path: str) -> None:
        """Parse *log_content*, run all configured scenarios, and save a report."""
        report_lines: list[str] = []

        def _printer(msg: str) -> None:
            """Prefix PASS/FAIL lines with a timestamp and collect for the report."""
            stripped = msg.strip()
            is_pass_fail = stripped.startswith("[PASS]") or stripped.startswith("[FAIL]")
            is_wm_line   = "WM" in stripped and "delta" in stripped
            if is_pass_fail and not is_wm_line:
                ts_match = _TS_RE.search(msg)
                ts = ts_match.group(1) if ts_match else datetime.now().strftime("%H:%M:%S")
                prefixed = f"[{ts}] {msg}"
            else:
                prefixed = msg
            self._on_line(prefixed)
            report_lines.append(prefixed)

        try:
            engine = AnalysisService(log_content, config_path, _printer)
            if engine.load_config():
                engine.parse_log()
                engine.run_test()
        except Exception as exc:
            _printer(f"\nCRITICAL ERROR: {exc}")

        self._save_report(report_lines, config_path)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _save_report(self, lines: list[str], config_path: str) -> None:
        try:
            os.makedirs(self._logs_dir, exist_ok=True)
            timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            report_path = os.path.join(self._logs_dir, f"analysis_report_{timestamp}.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"--- Analysis Report --- {time.ctime()} ---\n")
                f.write(f"Config file: {config_path}\n")
                f.write("=" * 60 + "\n\n")
                for line in lines:
                    f.write(line + "\n")
            self._on_line(f"\n[REPORT] Saved to: {report_path}")
        except Exception as exc:
            self._on_line(f"\n[REPORT] Failed to save report: {exc}")

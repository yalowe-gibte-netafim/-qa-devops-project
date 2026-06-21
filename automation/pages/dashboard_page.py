"""Dashboard page object that aggregates operational tabs."""

from __future__ import annotations

from automation.pages.base_page import BasePage


class DashboardPage(BasePage):
    """Represents the post-launch operational dashboard area."""

    def build(self) -> None:
        """No-op; concrete dashboard tabs are built by dedicated page classes."""
        return

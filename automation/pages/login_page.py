"""Login page object placeholder.

Current FLEX desktop app has no authentication screen. This class preserves
enterprise page-layer structure and keeps extension points explicit.
"""

from __future__ import annotations

from automation.pages.base_page import BasePage


class LoginPage(BasePage):
    """Page object for login interactions (currently no-op)."""

    def build(self) -> None:
        """No-op for current UI."""
        return

    def login(self, username: str, password: str) -> bool:
        """Execute login action.

        Returns True because login is not part of current app behavior.
        """
        _ = (username, password)
        return True

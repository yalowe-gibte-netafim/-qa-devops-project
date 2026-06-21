"""Business flow placeholder for login-related orchestration.

Desktop FLEX tester currently has no login step; this flow exists to keep
enterprise layering consistent and ready for future expansion.
"""

from __future__ import annotations


class LoginFlow:
    """Coordinates login-related actions across page/service layers."""

    def run(self) -> bool:
        """Execute the login flow.

        Returns:
            bool: Always True for current app (no login business step).
        """
        return True

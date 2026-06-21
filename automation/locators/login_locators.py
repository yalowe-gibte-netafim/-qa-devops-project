"""Locators/constants for login-related UI elements.

For tkinter desktop automation these are logical keys, not Selenium CSS/XPath.
"""

from __future__ import annotations


class LoginLocators:
    """Logical locator keys for future login UI mapping."""

    USERNAME_ENTRY = "login.username.entry"
    PASSWORD_ENTRY = "login.password.entry"
    SUBMIT_BUTTON  = "login.submit.button"

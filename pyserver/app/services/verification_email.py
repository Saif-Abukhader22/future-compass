from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


class _MiniUser:
    """Lightweight adapter to satisfy shared.emails.email.Email expectations.

    Only the attributes used by the verification template are provided.
    """

    def __init__(self, email: str, first_name: str = ""):
        self.email = email
        self.first_name = first_name


def _normalize_email(addr: str) -> str:
    try:
        import socket
        from email_validator import validate_email, EmailNotValidError
        socket.setdefaulttimeout(5)
        try:
            v = validate_email(str(addr), check_deliverability=True)
        except socket.timeout:
            v = validate_email(str(addr), check_deliverability=False)
        return v.normalized
    except Exception:
        return str(addr).strip()



def _print_verification(to_email: str, code: str) -> None:
    """Print only the code to the console for development/testing."""
    try:
        # Print the raw code only (no email or labels)
        print(code)
    except Exception:
        # Avoid crashing flows if console is unavailable
        pass
def send_verification_email(to_email: str, code: str, name: Optional[str] = None):
    """Send verification email using ONLY the shared email module."""
    normalized = _normalize_email(to_email)
    first_name = (name or "").strip()

    # Always print code for dev visibility
    _print_verification(normalized, code)

    # Use shared.emails.email.Email exclusively
    from shared.emails.email import Email  # type: ignore
    ok = bool(Email(_MiniUser(email=normalized, first_name=first_name)).send_registration_email(code))
    if ok:
        logger.info(f"verification_email: sent via shared.emails to {normalized}")
        return
    # If shared email fails (returns False), raise to surface the issue
    raise RuntimeError("Shared email provider failed to send verification email")


def send_password_reset_email_shared(to_email: str, token_or_code: str, name: Optional[str] = None):
    """Send password reset email using ONLY the shared email module.

    Note: The shared template expects a code. If you pass a full token or link,
    it will be displayed as-is in the email body.
    """
    normalized = _normalize_email(to_email)
    first_name = (name or "").strip()

    # Print for dev visibility
    _print_verification(normalized, token_or_code)

    from shared.emails.email import Email  # type: ignore
    ok = bool(Email(_MiniUser(email=normalized, first_name=first_name)).send_password_reset_email(token_or_code))
    if ok:
        logger.info(f"password_reset_email: sent via shared.emails to {normalized}")
        return
    raise RuntimeError("Shared email provider failed to send password reset email")

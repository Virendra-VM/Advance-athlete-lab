"""Minimal pluggable email transport.

Default provider is ``console``, which logs the message instead of sending it so
local development never needs mail credentials.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.config import (
    EMAIL_FROM,
    EMAIL_PROVIDER,
    RESEND_API_KEY,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


def transport_is_live() -> bool:
    """True when a real mail transport is configured."""
    if EMAIL_PROVIDER == "resend":
        return bool(RESEND_API_KEY)
    if EMAIL_PROVIDER == "smtp":
        return bool(SMTP_HOST)
    return False


def _send_resend(to: str, subject: str, html: str, text: str) -> bool:
    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html, "text": text},
            timeout=15,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Resend delivery failed: %s", exc)
        return False


def _send_smtp(to: str, subject: str, html: str, text: str) -> bool:
    message = EmailMessage()
    message["From"] = EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("SMTP delivery failed: %s", exc)
        return False


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Return True when the message was handed to a live transport."""
    if EMAIL_PROVIDER == "resend" and RESEND_API_KEY:
        return _send_resend(to, subject, html, text)
    if EMAIL_PROVIDER == "smtp" and SMTP_HOST:
        return _send_smtp(to, subject, html, text)

    logger.info("[email:console] to=%s subject=%s\n%s", to, subject, text)
    return False

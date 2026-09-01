"""Soft email verification.

Verification is encouraged but never blocks onboarding or app access. Tokens are
stored hashed and expire; the plaintext token only exists in the email (or the
API response when no mail transport is configured, so local dev still works).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import (
    APP_BASE_URL,
    EMAIL_VERIFY_RESEND_COOLDOWN_S,
    EMAIL_VERIFY_TTL_HOURS,
)
from app.models import User
from app.services.mailer import send_email, transport_is_live


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_link(token: str) -> str:
    return f"{APP_BASE_URL}/verify-email?token={token}"


def cooldown_remaining(user: User) -> int:
    if user.email_verify_sent_at is None:
        return 0
    elapsed = (_utcnow() - user.email_verify_sent_at).total_seconds()
    remaining = EMAIL_VERIFY_RESEND_COOLDOWN_S - elapsed
    return max(0, int(remaining))


def issue_token(db: Session, user: User) -> str:
    """Mint a fresh token, persist its hash, and return the plaintext."""
    token = f"{user.id}.{secrets.token_urlsafe(32)}"
    user.email_verify_token_hash = hash_token(token)
    user.email_verify_sent_at = _utcnow()
    db.add(user)
    return token


def deliver_verification_email(email: str, name: str, token: str) -> bool:
    link = verify_link(token)
    greeting = f"Hi {name}," if name else "Hi,"
    text = (
        f"{greeting}\n\n"
        "Confirm your email so we can send training summaries and account alerts:\n"
        f"{link}\n\n"
        f"This link expires in {EMAIL_VERIFY_TTL_HOURS} hours. "
        "You can keep using Advance Athlete Lab either way.\n"
    )
    html = (
        f"<p>{greeting}</p>"
        "<p>Confirm your email so we can send training summaries and account alerts.</p>"
        f'<p><a href="{link}">Verify my email</a></p>'
        f"<p style=\"color:#666;font-size:12px\">This link expires in {EMAIL_VERIFY_TTL_HOURS} hours. "
        "You can keep using Advance Athlete Lab either way.</p>"
    )
    return send_email(email, "Verify your email · Advance Athlete Lab", html, text)


def request_verification(db: Session, user: User) -> dict:
    """Issue + send a verification email. Never raises for delivery failures."""
    if user.email_verified_at is not None:
        return {"sent": False, "already_verified": True, "dev_verify_token": None}

    token = issue_token(db, user)
    db.commit()
    db.refresh(user)

    delivered = deliver_verification_email(user.email, "", token)
    return {
        "sent": delivered,
        "already_verified": False,
        # Surfaced only when there is no live transport, so dev can click through.
        "dev_verify_token": None if transport_is_live() else token,
    }


def confirm_verification(db: Session, token: str) -> User | None:
    raw = (token or "").strip()
    if "." not in raw:
        return None
    user_part, _, _ = raw.partition(".")
    if not user_part.isdigit():
        return None

    user = db.query(User).filter(User.id == int(user_part)).first()
    if user is None:
        return None
    if user.email_verified_at is not None:
        return user
    if not user.email_verify_token_hash:
        return None
    if not secrets.compare_digest(user.email_verify_token_hash, hash_token(raw)):
        return None
    if user.email_verify_sent_at is not None:
        expires_at = user.email_verify_sent_at + timedelta(hours=EMAIL_VERIFY_TTL_HOURS)
        if _utcnow() > expires_at:
            return None

    user.email_verified_at = _utcnow()
    user.email_verify_token_hash = None
    db.commit()
    db.refresh(user)
    return user

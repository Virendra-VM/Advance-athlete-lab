"""Phase E — human review queue for coach reply quality."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CoachMessage, CoachReviewFlag

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
STATUS_DISMISSED = "dismissed"

REASON_USER = "user_report"
REASON_AUTO = "auto_quality"


def flag_message_for_review(
    db: Session,
    profile_id: int,
    message_id: int,
    *,
    reason: str = REASON_USER,
    category: str | None = None,
    notes: str | None = None,
    quality_score: float | None = None,
) -> CoachReviewFlag:
    message = (
        db.query(CoachMessage)
        .filter(
            CoachMessage.id == message_id,
            CoachMessage.athlete_profile_id == profile_id,
            CoachMessage.role == "assistant",
        )
        .first()
    )
    if message is None:
        raise LookupError("Coach message not found.")

    existing = (
        db.query(CoachReviewFlag)
        .filter(
            CoachReviewFlag.message_id == message_id,
            CoachReviewFlag.status == STATUS_OPEN,
        )
        .first()
    )
    if existing is not None:
        return existing

    row = CoachReviewFlag(
        athlete_profile_id=profile_id,
        message_id=message_id,
        reason=reason,
        category=category,
        notes=(notes or "")[:4000] or None,
        quality_score=quality_score,
        status=STATUS_OPEN,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_review_flags(
    db: Session,
    profile_id: int,
    *,
    status: str = STATUS_OPEN,
    limit: int = 50,
) -> list[dict]:
    rows = (
        db.query(CoachReviewFlag, CoachMessage)
        .join(CoachMessage, CoachReviewFlag.message_id == CoachMessage.id)
        .filter(
            CoachReviewFlag.athlete_profile_id == profile_id,
            CoachReviewFlag.status == status,
        )
        .order_by(CoachReviewFlag.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": flag.id,
            "message_id": flag.message_id,
            "reason": flag.reason,
            "category": flag.category,
            "notes": flag.notes,
            "quality_score": flag.quality_score,
            "status": flag.status,
            "created_at": flag.created_at.isoformat() if flag.created_at else None,
            "message_preview": (message.content or "")[:280],
        }
        for flag, message in rows
    ]


def resolve_review_flag(
    db: Session,
    profile_id: int,
    flag_id: int,
    *,
    status: str = STATUS_RESOLVED,
) -> CoachReviewFlag:
    if status not in {STATUS_RESOLVED, STATUS_DISMISSED}:
        raise ValueError("status must be resolved or dismissed")
    row = (
        db.query(CoachReviewFlag)
        .filter(
            CoachReviewFlag.id == flag_id,
            CoachReviewFlag.athlete_profile_id == profile_id,
        )
        .first()
    )
    if row is None:
        raise LookupError("Review flag not found.")
    row.status = status
    row.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def maybe_auto_flag_reply(
    db: Session,
    profile_id: int,
    message_id: int,
    reply_text: str,
    *,
    skill: str | None,
    quality_score: float,
) -> CoachReviewFlag | None:
    if quality_score >= 0.45:
        return None
    return flag_message_for_review(
        db,
        profile_id,
        message_id,
        reason=REASON_AUTO,
        category=skill,
        notes="Auto-flagged by Phase E mechanical quality scorer.",
        quality_score=quality_score,
    )

"""Athlete Profile v2 helpers: relations, completeness, and write helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.auth_schemas import (
    AthleteProfileResponse,
    ConsentRead,
    InjuryRead,
    SportRead,
)
from app.models import AthleteConsent, AthleteInjury, AthleteProfile, AthleteSport

# Weighted so the AI-critical fields drive the score users see.
COMPLETENESS_FIELDS: list[tuple[str, int]] = [
    ("name", 5),
    ("sex", 5),
    ("date_of_birth", 5),
    ("height_cm", 8),
    ("weight", 8),
    ("primary_goal", 10),
    ("fitness_level", 8),
    ("days_per_week", 8),
    ("workout_duration_minutes", 8),
    ("preferred_workout_time", 4),
    ("equipment", 6),
    ("training_history_months", 5),
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def dump_json_column(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (list, dict)) and not value:
        return None
    return json.dumps(value)


def load_json_column(value):
    if value is None or isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [part.strip() for part in text.split(",") if part.strip()]


def age_from_dob(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years if 5 <= years <= 120 else None


def get_profile_sports(db: Session, athlete_profile_id: int) -> list[AthleteSport]:
    return (
        db.query(AthleteSport)
        .filter(AthleteSport.athlete_profile_id == athlete_profile_id)
        .order_by(AthleteSport.priority.asc(), AthleteSport.id.asc())
        .all()
    )


def get_profile_injuries(db: Session, athlete_profile_id: int) -> list[AthleteInjury]:
    return (
        db.query(AthleteInjury)
        .filter(AthleteInjury.athlete_profile_id == athlete_profile_id)
        .order_by(AthleteInjury.status.asc(), AthleteInjury.id.asc())
        .all()
    )


def get_profile_consent(db: Session, athlete_profile_id: int) -> AthleteConsent | None:
    return (
        db.query(AthleteConsent)
        .filter(AthleteConsent.athlete_profile_id == athlete_profile_id)
        .first()
    )


def compute_profile_completeness(profile: AthleteProfile, sports_count: int) -> int:
    total_weight = sum(weight for _, weight in COMPLETENESS_FIELDS) + 10  # +10 for sports
    earned = 0
    for field, weight in COMPLETENESS_FIELDS:
        value = getattr(profile, field, None)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        earned += weight
    if sports_count > 0:
        earned += 10
    return max(0, min(100, round((earned / total_weight) * 100)))


def replace_sports(db: Session, profile: AthleteProfile, sports: list) -> None:
    """Replace the athlete's sport rows and mirror them onto the profile columns."""
    db.query(AthleteSport).filter(
        AthleteSport.athlete_profile_id == profile.id
    ).delete(synchronize_session=False)

    seen: set[str] = set()
    primary: list[str] = []
    secondary: list[str] = []
    for entry in sports or []:
        sport = (entry.sport or "").strip()
        if not sport:
            continue
        key = sport.lower()
        if key in seen:
            continue
        seen.add(key)
        db.add(
            AthleteSport(
                athlete_profile_id=profile.id,
                sport=sport,
                priority=entry.priority,
                experience_level=(entry.experience_level or None),
                weekly_preference_days=entry.weekly_preference_days,
            )
        )
        if entry.priority == "secondary":
            secondary.append(sport)
        else:
            primary.append(sport)

    profile.primary_sports = dump_json_column(primary)
    profile.secondary_sports = dump_json_column(secondary)


def replace_injuries(db: Session, profile: AthleteProfile, injuries: list) -> None:
    db.query(AthleteInjury).filter(
        AthleteInjury.athlete_profile_id == profile.id
    ).delete(synchronize_session=False)

    summary_parts: list[str] = []
    for entry in injuries or []:
        region = (entry.body_region or "").strip()
        if not region:
            continue
        db.add(
            AthleteInjury(
                athlete_profile_id=profile.id,
                body_region=region,
                condition=(entry.condition or None),
                status=entry.status,
                severity=(entry.severity or None),
                onset_date=entry.onset_date,
                notes=(entry.notes or None),
            )
        )
        label = region if not entry.condition else f"{region} ({entry.condition})"
        if entry.status == "active":
            label = f"{label} - active"
        summary_parts.append(label)

    if summary_parts:
        existing = (profile.injuries_limitations or "").strip()
        structured = "; ".join(summary_parts)
        # Keep any free-text detail the athlete typed alongside the chips.
        profile.injuries_limitations = (
            structured if not existing or existing in structured else f"{structured}; {existing}"
        )


def upsert_consent(db: Session, profile: AthleteProfile, consents) -> None:
    if consents is None:
        return
    record = get_profile_consent(db, profile.id)
    if record is None:
        record = AthleteConsent(athlete_profile_id=profile.id)
        db.add(record)
    record.ai_coaching = bool(consents.ai_coaching)
    record.health_data = bool(consents.health_data)
    record.research = bool(consents.research)
    if record.ai_coaching or record.health_data or record.research:
        record.accepted_at = utcnow()


def serialize_profile(db: Session, profile: AthleteProfile) -> AthleteProfileResponse:
    sports = get_profile_sports(db, profile.id)
    injuries = get_profile_injuries(db, profile.id)
    consent = get_profile_consent(db, profile.id)

    response = AthleteProfileResponse.model_validate(profile)
    response.sports = [SportRead.model_validate(row) for row in sports]
    response.injuries = [InjuryRead.model_validate(row) for row in injuries]
    if consent is not None:
        response.consents = ConsentRead.model_validate(consent)
    response.profile_completeness = compute_profile_completeness(profile, len(sports))
    return response

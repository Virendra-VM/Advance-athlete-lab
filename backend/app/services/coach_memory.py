"""Phase C — coach memory and proactive prompts.

Stable memory: goals, injuries, preferences (synced from profile + chat).
Episodic memory: missed sessions, travel, bike fit — expires after ~21 days.
Proactive memory: activity debrief nudges after sync.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Activity, AthleteProfile, CoachMemory
from app.services.coach_advisory import MISSED_OR_ROUGH_RE, _travel_destination
from app.services.coach_skills import (
    SKILL_SUPPORT_CHAT,
    SKILL_VALIDATE_PLAN,
)

MEMORY_STABLE = "stable"
MEMORY_EPISODIC = "episodic"
MEMORY_PROACTIVE = "proactive"

STATUS_ACTIVE = "active"
STATUS_DISMISSED = "dismissed"
STATUS_CONSUMED = "consumed"

EPISODIC_TTL_DAYS = 21
PROACTIVE_TTL_DAYS = 7


@dataclass(frozen=True)
class MemoryCandidate:
    memory_type: str
    category: str
    summary: str
    content: str
    source: str
    dedupe_key: str
    activity_id: int | None = None
    expires_at: datetime | None = None


def _episodic_expiry(clock: dict | None = None) -> datetime:
    today = (clock or {}).get("today")
    if isinstance(today, date):
        base = datetime.combine(today, datetime.min.time())
    else:
        base = datetime.utcnow()
    return base + timedelta(days=EPISODIC_TTL_DAYS)


def sync_stable_memories(db: Session, profile: AthleteProfile) -> int:
    """Upsert long-lived facts from the athlete profile."""
    candidates: list[MemoryCandidate] = []
    if profile.primary_goal or profile.goal_event_name:
        bits = [profile.primary_goal, profile.goal_event_name]
        if profile.goal_event_date:
            bits.append(f"Target date: {profile.goal_event_date.isoformat()}")
        if profile.goal_metric:
            bits.append(profile.goal_metric)
        content = " ".join(str(bit).strip() for bit in bits if bit)
        candidates.append(
            MemoryCandidate(
                MEMORY_STABLE,
                "goal",
                "Training goal",
                content,
                "profile",
                "stable:goal",
            )
        )
    if profile.injuries_limitations:
        candidates.append(
            MemoryCandidate(
                MEMORY_STABLE,
                "injury",
                "Injury / limitation notes",
                profile.injuries_limitations.strip(),
                "profile",
                "stable:injuries",
            )
        )
    prefs: list[str] = []
    if profile.exercises_hate:
        prefs.append(f"Dislikes: {profile.exercises_hate.strip()}")
    if profile.exercises_love:
        prefs.append(f"Likes: {profile.exercises_love.strip()}")
    if profile.preferred_workout_time:
        prefs.append(f"Preferred time: {profile.preferred_workout_time.strip()}")
    if prefs:
        candidates.append(
            MemoryCandidate(
                MEMORY_STABLE,
                "preference",
                "Training preferences",
                " ".join(prefs),
                "profile",
                "stable:preferences",
            )
        )
    if profile.planning_notes:
        candidates.append(
            MemoryCandidate(
                MEMORY_STABLE,
                "planning",
                "Planning notes",
                profile.planning_notes.strip()[:600],
                "profile",
                "stable:planning_notes",
            )
        )
    count = 0
    for candidate in candidates:
        if upsert_memory(db, profile.id, candidate):
            count += 1
    return count


def extract_episodic_from_chat(
    message: str,
    *,
    skill: str,
    clock: dict | None = None,
) -> list[MemoryCandidate]:
    """Deterministic episodic capture from athlete messages."""
    text = (message or "").strip()
    if not text:
        return []
    lower = text.lower()
    expires = _episodic_expiry(clock)
    today = (clock or {}).get("today")
    day_key = today.isoformat() if isinstance(today, date) else datetime.utcnow().date().isoformat()
    out: list[MemoryCandidate] = []

    if skill in {SKILL_VALIDATE_PLAN, SKILL_SUPPORT_CHAT} or MISSED_OR_ROUGH_RE.search(text):
        if "bike fit" in lower:
            out.append(
                MemoryCandidate(
                    MEMORY_EPISODIC,
                    "life_event",
                    "Bike fit day — sessions rescheduled",
                    "Athlete missed planned sessions for a bike fit — treat as equipment investment, not failure.",
                    "chat",
                    f"episodic:bike_fit:{day_key}",
                    expires_at=expires,
                )
            )
        elif MISSED_OR_ROUGH_RE.search(text):
            out.append(
                MemoryCandidate(
                    MEMORY_EPISODIC,
                    "missed_session",
                    "Recent missed sessions",
                    text[:400],
                    "chat",
                    f"episodic:missed:{day_key}",
                    expires_at=expires,
                )
            )

    travel_dest = _travel_destination(text)
    if travel_dest or ("travel" in lower and "train" in lower):
        dest = travel_dest or "upcoming travel"
        out.append(
            MemoryCandidate(
                MEMORY_EPISODIC,
                "travel",
                f"Travel — {dest}",
                f"Athlete mentioned travel to {dest}. Protect freshness and logistics in planning.",
                "chat",
                f"episodic:travel:{dest.lower().replace(' ', '_')}",
                expires_at=expires,
            )
        )

    if re.search(r"\b(hate|avoid|never)\b.*\b(threshold|interval|long run|morning)", lower):
        out.append(
            MemoryCandidate(
                MEMORY_EPISODIC,
                "preference",
                "Stated training preference",
                text[:300],
                "chat",
                f"episodic:preference:{day_key}",
                expires_at=expires,
            )
        )

    return out


def upsert_memory(db: Session, profile_id: int, candidate: MemoryCandidate) -> bool:
    row = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.dedupe_key == candidate.dedupe_key,
        )
        .first()
    )
    if row is None:
        db.add(
            CoachMemory(
                athlete_profile_id=profile_id,
                memory_type=candidate.memory_type,
                category=candidate.category,
                summary=candidate.summary,
                content=candidate.content,
                source=candidate.source,
                dedupe_key=candidate.dedupe_key,
                activity_id=candidate.activity_id,
                status=STATUS_ACTIVE,
                expires_at=candidate.expires_at,
            )
        )
        db.commit()
        return True

    row.summary = candidate.summary
    row.content = candidate.content
    row.source = candidate.source
    row.expires_at = candidate.expires_at
    if row.status == STATUS_DISMISSED and candidate.memory_type == MEMORY_PROACTIVE:
        return False
    if row.status != STATUS_CONSUMED:
        row.status = STATUS_ACTIVE
    db.commit()
    return True


def capture_chat_memories(
    db: Session,
    profile: AthleteProfile,
    message: str,
    *,
    skill: str,
    clock: dict | None = None,
) -> list[str]:
    """Persist episodic memories after an athlete message."""
    sync_stable_memories(db, profile)
    keys: list[str] = []
    for candidate in extract_episodic_from_chat(message, skill=skill, clock=clock):
        if upsert_memory(db, profile.id, candidate):
            keys.append(candidate.dedupe_key)
    return keys


def load_active_memories(db: Session, profile_id: int) -> list[CoachMemory]:
    now = datetime.utcnow()
    rows = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.status == STATUS_ACTIVE,
            CoachMemory.memory_type.in_([MEMORY_STABLE, MEMORY_EPISODIC]),
        )
        .order_by(CoachMemory.updated_at.desc())
        .limit(24)
        .all()
    )
    active: list[CoachMemory] = []
    for row in rows:
        if row.expires_at and row.expires_at < now:
            row.status = STATUS_DISMISSED
            continue
        active.append(row)
    db.commit()
    return active


def format_memory_prompt_block(memories: list[CoachMemory]) -> str:
    if not memories:
        return ""
    stable = [row for row in memories if row.memory_type == MEMORY_STABLE]
    episodic = [row for row in memories if row.memory_type == MEMORY_EPISODIC]
    lines = [
        "COACH MEMORY (cross-session — reference naturally; do not recite as a bullet list)",
    ]
    if stable:
        lines.append("Stable facts:")
        for row in stable[:8]:
            lines.append(f"- {row.summary}: {row.content[:220]}")
    if episodic:
        lines.append("Recent context:")
        for row in episodic[:6]:
            lines.append(f"- {row.summary}: {row.content[:220]}")
    lines.append(
        "Weave memory into empathy and advice. Never open with a memory dump or dashboard syntax."
    )
    return "\n".join(lines)


def build_memory_bundle(db: Session, profile: AthleteProfile) -> dict:
    sync_stable_memories(db, profile)
    memories = load_active_memories(db, profile.id)
    return {
        "memories": memories,
        "prompt_block": format_memory_prompt_block(memories),
        "count": len(memories),
    }


def create_activity_debrief_prompt(
    db: Session,
    profile_id: int,
    activity: Activity,
) -> CoachMemory | None:
    """Queue a proactive debrief chip after a new activity sync."""
    if activity.id is None:
        return None
    sport = activity.sport_type or activity.name or "workout"
    name = activity.name or sport
    when = "today's session"
    if activity.activity_date:
        when = activity.activity_date.strftime("%A")
    suggested = f"How was {when}'s {sport.lower()} — {name}? Give me a quick debrief."
    candidate = MemoryCandidate(
        MEMORY_PROACTIVE,
        "activity_debrief",
        f"Debrief: {name[:80]}",
        suggested,
        "activity_sync",
        f"proactive:debrief:{activity.id}",
        activity_id=activity.id,
        expires_at=datetime.utcnow() + timedelta(days=PROACTIVE_TTL_DAYS),
    )
    existing = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.dedupe_key == candidate.dedupe_key,
        )
        .first()
    )
    if existing and existing.status in {STATUS_DISMISSED, STATUS_CONSUMED}:
        return None
    upsert_memory(db, profile_id, candidate)
    return (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.dedupe_key == candidate.dedupe_key,
        )
        .first()
    )


def list_proactive_prompts(db: Session, profile_id: int) -> list[dict]:
    now = datetime.utcnow()
    rows = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.memory_type == MEMORY_PROACTIVE,
            CoachMemory.status == STATUS_ACTIVE,
        )
        .order_by(CoachMemory.created_at.desc())
        .limit(5)
        .all()
    )
    prompts: list[dict] = []
    for row in rows:
        if row.expires_at and row.expires_at < now:
            row.status = STATUS_DISMISSED
            continue
        prompts.append(proactive_prompt_dict(row))
    db.commit()
    return prompts


def proactive_prompt_dict(row: CoachMemory) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "summary": row.summary,
        "message": row.content,
        "activity_id": row.activity_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def dismiss_proactive_prompt(db: Session, profile_id: int, memory_id: int) -> bool:
    row = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.id == memory_id,
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.memory_type == MEMORY_PROACTIVE,
        )
        .first()
    )
    if row is None:
        return False
    row.status = STATUS_DISMISSED
    db.commit()
    return True


def consume_proactive_for_activity(
    db: Session,
    profile_id: int,
    activity_id: int | None,
) -> None:
    if not activity_id:
        return
    rows = (
        db.query(CoachMemory)
        .filter(
            CoachMemory.athlete_profile_id == profile_id,
            CoachMemory.memory_type == MEMORY_PROACTIVE,
            CoachMemory.activity_id == activity_id,
            CoachMemory.status == STATUS_ACTIVE,
        )
        .all()
    )
    for row in rows:
        row.status = STATUS_CONSUMED
    if rows:
        db.commit()


def memory_snapshot(memories: list[CoachMemory]) -> list[dict]:
    return [
        {
            "type": row.memory_type,
            "category": row.category,
            "summary": row.summary,
            "content": row.content[:280],
        }
        for row in memories
    ]

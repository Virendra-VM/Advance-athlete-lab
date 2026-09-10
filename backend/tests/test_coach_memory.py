"""Phase C — coach memory and proactive prompt tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Activity, AthleteProfile, CoachMemory
from app.services.coach_memory import (
    MEMORY_EPISODIC,
    MEMORY_PROACTIVE,
    MEMORY_STABLE,
    STATUS_ACTIVE,
    STATUS_CONSUMED,
    STATUS_DISMISSED,
    build_memory_bundle,
    capture_chat_memories,
    consume_proactive_for_activity,
    create_activity_debrief_prompt,
    dismiss_proactive_prompt,
    extract_episodic_from_chat,
    format_memory_prompt_block,
    list_proactive_prompts,
    sync_stable_memories,
)
from app.services.coach_skills import SKILL_SUPPORT_CHAT, SKILL_VALIDATE_PLAN


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _profile(db) -> AthleteProfile:
    profile = AthleteProfile(
        name="Memory Test",
        age=32,
        weight=70.0,
        primary_goal="Half marathon under 1:50",
        injuries_limitations="Lower back — avoid heavy deadlifts",
        exercises_hate="Burpees",
        planning_notes="Travel to Kolhapur in September",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_sync_stable_memories_from_profile(db_session):
    profile = _profile(db_session)
    count = sync_stable_memories(db_session, profile)
    assert count >= 3
    rows = (
        db_session.query(CoachMemory)
        .filter(CoachMemory.athlete_profile_id == profile.id)
        .all()
    )
    categories = {row.category for row in rows}
    assert "goal" in categories
    assert "injury" in categories
    assert "planning" in categories


def test_extract_episodic_bike_fit_and_travel():
    message = (
        "Missed workouts for bike fit. Traveling by train to Kolhapur Sunday — "
        "should I use this plan?"
    )
    clock = {"today": date(2026, 9, 4)}
    candidates = extract_episodic_from_chat(
        message,
        skill=SKILL_VALIDATE_PLAN,
        clock=clock,
    )
    keys = {item.dedupe_key for item in candidates}
    assert any("bike_fit" in key for key in keys)
    assert any("travel" in key for key in keys)


def test_capture_chat_memories_persists_episodic(db_session):
    profile = _profile(db_session)
    clock = {"today": date(2026, 9, 4)}
    keys = capture_chat_memories(
        db_session,
        profile,
        "I missed two sessions — rough day with bike fit",
        skill=SKILL_SUPPORT_CHAT,
        clock=clock,
    )
    assert keys
    bundle = build_memory_bundle(db_session, profile)
    assert bundle["count"] >= 1
    assert "COACH MEMORY" in bundle["prompt_block"]


def test_format_memory_prompt_block():
    row = CoachMemory(
        athlete_profile_id=1,
        memory_type=MEMORY_STABLE,
        category="goal",
        summary="Training goal",
        content="Half marathon under 1:50",
        source="profile",
        dedupe_key="stable:goal",
        status=STATUS_ACTIVE,
    )
    block = format_memory_prompt_block([row])
    assert "COACH MEMORY" in block
    assert "Half marathon" in block


def test_create_activity_debrief_prompt(db_session):
    profile = _profile(db_session)
    activity = Activity(
        athlete_profile_id=profile.id,
        provider="strava",
        external_activity_id="999",
        strava_activity_id=999,
        name="Morning Endurance Ride",
        activity_date=datetime.utcnow(),
        distance_m=42000,
        moving_time_s=5400,
        sport_type="Ride",
        source_fit_file="strava_api:999",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)

    row = create_activity_debrief_prompt(db_session, profile.id, activity)
    assert row is not None
    prompts = list_proactive_prompts(db_session, profile.id)
    assert len(prompts) == 1
    assert prompts[0]["activity_id"] == activity.id
    assert "debrief" in prompts[0]["message"].lower()


def test_dismiss_proactive_prompt(db_session):
    profile = _profile(db_session)
    activity = Activity(
        athlete_profile_id=profile.id,
        provider="strava",
        external_activity_id="1000",
        strava_activity_id=1000,
        name="Easy Run",
        activity_date=datetime.utcnow(),
        distance_m=8000,
        moving_time_s=2400,
        sport_type="Run",
        source_fit_file="strava_api:1000",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    create_activity_debrief_prompt(db_session, profile.id, activity)
    prompts = list_proactive_prompts(db_session, profile.id)
    prompt_id = prompts[0]["id"]

    assert dismiss_proactive_prompt(db_session, profile.id, prompt_id) is True
    assert list_proactive_prompts(db_session, profile.id) == []


def test_consume_proactive_on_debrief(db_session):
    profile = _profile(db_session)
    activity = Activity(
        athlete_profile_id=profile.id,
        provider="strava",
        external_activity_id="1001",
        strava_activity_id=1001,
        name="Tempo Run",
        activity_date=datetime.utcnow(),
        distance_m=10000,
        moving_time_s=3000,
        sport_type="Run",
        source_fit_file="strava_api:1001",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    create_activity_debrief_prompt(db_session, profile.id, activity)
    consume_proactive_for_activity(db_session, profile.id, activity.id)
    row = (
        db_session.query(CoachMemory)
        .filter(CoachMemory.activity_id == activity.id)
        .first()
    )
    assert row.status == STATUS_CONSUMED
    assert list_proactive_prompts(db_session, profile.id) == []


def test_expired_episodic_not_loaded(db_session):
    profile = _profile(db_session)
    db_session.add(
        CoachMemory(
            athlete_profile_id=profile.id,
            memory_type=MEMORY_EPISODIC,
            category="missed_session",
            summary="Old miss",
            content="Expired",
            source="chat",
            dedupe_key="episodic:old",
            status=STATUS_ACTIVE,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
    )
    db_session.commit()
    bundle = build_memory_bundle(db_session, profile)
    assert "Expired" not in bundle["prompt_block"]
    row = db_session.query(CoachMemory).filter(CoachMemory.dedupe_key == "episodic:old").first()
    assert row.status == STATUS_DISMISSED

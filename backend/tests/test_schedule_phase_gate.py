"""Discussion stays read-only. An explicit confirm writes the calendar."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AthleteProfile, PlannedWorkout
from app.services.coach_ai import coach_chat
from app.services.coach_intent import (
    CLINICAL_VETO,
    EXECUTION_CONFIRMATION,
    SCHEDULE_UPDATE,
    extract_target_date,
    route_athlete_query,
    schedule_patch_authorized,
)


TODAY = date(2026, 9, 22)  # Tuesday


def test_questions_stay_in_discussion():
    samples = [
        "Can I swap Thursday's run for a ride?",
        "How should I adjust this week?",
        "Should I still train today if my HRV is low?",
        "Plan my week around my lower back",
    ]
    for message in samples:
        assert schedule_patch_authorized(message) is False, message
        routed = route_athlete_query(
            message, runtime_intent=SCHEDULE_UPDATE, confidence=0.8, today=TODAY
        )
        assert routed is not None
        assert routed.requires_database_patch is False
        assert routed.target_date is None


def test_explicit_and_imperative_requests_execute():
    assert schedule_patch_authorized("Update my week") is True
    assert schedule_patch_authorized("Yes, update my week") is True
    assert schedule_patch_authorized("Do it") is True
    assert schedule_patch_authorized("Move my long run to Sunday") is True
    assert schedule_patch_authorized("skip today") is True

    sunday = route_athlete_query(
        "Move my long run to Sunday",
        runtime_intent=SCHEDULE_UPDATE,
        confidence=0.92,
        today=TODAY,
    )
    assert sunday.requires_database_patch is True
    assert sunday.target_date == "2026-09-27"
    assert sunday.intent_category == "SCHEDULE_MUTATION"

    today_move = route_athlete_query(
        "skip today",
        runtime_intent="DAY_ADJUST",
        confidence=1.2,
        today=TODAY,
    )
    assert today_move.confidence_score == 1.0
    assert today_move.requires_database_patch is True
    assert today_move.target_date == "2026-09-22"


def test_clinical_lens_never_becomes_a_schedule_patch():
    routed = route_athlete_query(
        "Update my week. I have sharp pain in my Achilles.",
        runtime_intent=CLINICAL_VETO,
        confidence=0.96,
        today=TODAY,
    )
    assert routed.intent_category == "CLINICAL_VETO"
    assert routed.requires_database_patch is False


def test_impossible_date_is_dropped():
    assert extract_target_date("Move it to 2026-02-31", TODAY) is None


def test_iso_date_is_kept():
    routed = route_athlete_query(
        "Update my calendar on 2026-10-04",
        runtime_intent=SCHEDULE_UPDATE,
        today=TODAY,
    )
    assert routed.requires_database_patch is True
    assert routed.target_date == "2026-10-04"


@pytest.fixture()
def db_session(monkeypatch):
    monkeypatch.setattr("app.services.coach_ai.provider_chain", lambda: [])
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _profile(db) -> AthleteProfile:
    profile = AthleteProfile(name="Phase Gate", age=31, weight=70.0, onboarding_completed=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_swap_question_does_not_write_the_calendar(db_session):
    profile = _profile(db_session)
    result = coach_chat(db_session, profile, "Can I swap Thursday's run for a ride?")
    assert db_session.query(PlannedWorkout).count() == 0
    assert result["plan"] is None
    assert result["coach_intent"]["requires_database_patch"] is False
    assert result["coach_intent"]["intent_category"] == "SCHEDULE_MUTATION"
    assert EXECUTION_CONFIRMATION not in (result["reply"]["reply"] or "")


def test_update_my_week_patches_and_confirms_briefly(db_session):
    profile = _profile(db_session)
    result = coach_chat(db_session, profile, "Update my week")
    assert db_session.query(PlannedWorkout).count() > 0
    assert result["plan"] is not None
    assert result["coach_intent"]["requires_database_patch"] is True
    assert result["reply"]["reply"] == EXECUTION_CONFIRMATION
    assert "TODAY'S CALL" not in result["reply"]["reply"]
    assert "| Day |" not in result["reply"]["reply"]


def test_clinical_pain_still_overrides_an_update_request(db_session):
    profile = _profile(db_session)
    result = coach_chat(
        db_session,
        profile,
        "Update my week. I have sharp pain in my tendon when running",
    )
    assert result["reply"]["intent"] == "CLINICAL_VETO"
    assert result["coach_intent"]["intent_category"] == "CLINICAL_VETO"
    assert result["coach_intent"]["requires_database_patch"] is False
    assert result["reply"]["reply"] != EXECUTION_CONFIRMATION

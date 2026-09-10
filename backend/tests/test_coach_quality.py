"""Phase E — golden bank, quality scoring, and review queue tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AthleteProfile, CoachMessage, CoachReviewFlag
from app.services.coach_reply_eval import (
    score_phase_e_reply,
    score_ui_hygiene,
)
from app.services.coach_review import (
    REASON_AUTO,
    REASON_USER,
    flag_message_for_review,
    list_review_flags,
    maybe_auto_flag_reply,
    resolve_review_flag,
)
from app.services.coach_quality_eval import run_routing_regression
from scripts.ai_eval.coach_golden_bank import GOLDEN_ROUTING_CASES
from scripts.ai_eval.run_coach_quality_eval import run_phase_e_eval


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
    profile = AthleteProfile(name="Quality Test", age=30, weight=70.0)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_golden_bank_has_200_plus_cases():
    assert len(GOLDEN_ROUTING_CASES) >= 200


def test_routing_regression_passes():
    report = run_routing_regression(GOLDEN_ROUTING_CASES)
    assert report["regression_pass"] is True
    assert report["pass_rate"] >= 0.98


def test_score_ui_hygiene_detects_leaks():
    clean = "Keep today easy — conversational pace all day."
    dirty = 'SKILL: review_session\n{"reply": "leak"}'
    assert score_ui_hygiene(clean)[0] >= 0.99
    assert score_ui_hygiene(dirty)[0] < 0.5


def test_score_phase_e_support_chat_bans_schedule_headers():
    bad = "🟢 PRIMED / ACCUMULATE — push through.\n🗓️ REVISED WEEK\n| Mon | rest |"
    scored = score_phase_e_reply(bad, skill="support_chat")
    assert scored["dimensions"]["skill_adherence"]["score"] == 0.0
    assert scored["total"] < 0.75


def test_phase_e_eval_harness_end_to_end():
    report = run_phase_e_eval(dry_run=False)
    assert report["phase"] == "E"
    assert report["routing"]["total"] >= 200
    assert report["summary"]["deploy_gate_pass"] is True


def test_flag_and_resolve_review_queue(db_session):
    profile = _profile(db_session)
    message = CoachMessage(
        athlete_profile_id=profile.id,
        role="assistant",
        content="Try again tomorrow — easy day.",
        created_at=datetime.utcnow(),
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    flag = flag_message_for_review(
        db_session,
        profile.id,
        message.id,
        reason=REASON_USER,
        notes="Tone felt off",
    )
    assert flag.status == "open"

    open_rows = list_review_flags(db_session, profile.id, status="open")
    assert len(open_rows) == 1
    assert open_rows[0]["message_id"] == message.id

    resolve_review_flag(db_session, profile.id, flag.id, status="resolved")
    assert db_session.query(CoachReviewFlag).filter_by(id=flag.id).one().status == "resolved"


def test_maybe_auto_flag_only_on_low_score(db_session):
    profile = _profile(db_session)
    message = CoachMessage(
        athlete_profile_id=profile.id,
        role="assistant",
        content="Good reply",
        created_at=datetime.utcnow(),
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    assert maybe_auto_flag_reply(
        db_session,
        profile.id,
        message.id,
        "Good reply",
        skill="general_chat",
        quality_score=0.8,
    ) is None

    flagged = maybe_auto_flag_reply(
        db_session,
        profile.id,
        message.id,
        "SKILL: rebuild_week",
        skill="general_chat",
        quality_score=0.2,
    )
    assert flagged is not None
    assert flagged.reason == REASON_AUTO

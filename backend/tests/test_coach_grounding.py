"""Grounding guardrails — no memory bleed into plan advice replies."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AthleteProfile, CoachMemory
from app.services.coach_advisory import (
    advisory_prompt_block,
    grounding_guardrail_block,
    template_plan_advice,
)
from app.services.coach_memory import (
    MEMORY_EPISODIC,
    MEMORY_STABLE,
    build_memory_bundle,
    filter_memories_for_message,
    format_memory_prompt_block,
)
from app.services.coach_reply_eval import score_message_grounding
from scripts.ai_eval.coach_golden_bank import GROUNDING_EVAL_CASES, WEEKEND_BASE_WEEK_MESSAGE


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


CLEAN_WEEKEND_MESSAGE = WEEKEND_BASE_WEEK_MESSAGE

BAD_REPLY = (
    "Hey — first off, take a deep breath. Yesterday's bike fit was smart insurance. "
    "Sunday long easy run on the train-travel day works without the bike. "
    "You'll arrive in Kolhapur fresh. Pros and cons below. Coach's Rule: easy Friday. "
    "The Bottom Line: ACWR 0.95 before rest week."
)


def test_grounding_eval_case_count():
    assert len(GROUNDING_EVAL_CASES) >= 1


def test_bad_reply_fails_grounding_score():
    case = GROUNDING_EVAL_CASES[0]
    score, detail = score_message_grounding(
        BAD_REPLY,
        forbidden_patterns=case.forbidden_patterns,
        required_patterns=case.required_patterns,
    )
    assert score == 0.0
    assert "forbidden_mentions" in detail


def test_grounding_guardrail_bans_travel_when_not_in_message():
    block = grounding_guardrail_block(CLEAN_WEEKEND_MESSAGE)
    assert "bike fit" in block.lower()
    assert "kolhapur" in block.lower()
    assert "Do NOT mention" in block


def test_advisory_prompt_includes_grounding_for_message():
    block = advisory_prompt_block(CLEAN_WEEKEND_MESSAGE)
    assert "CURRENT-TURN GROUNDING" in block
    assert "Do NOT mention bike fit" in block or "bike fit" in block.lower()


def test_memory_filter_drops_irrelevant_episodic(db_session):
    profile = AthleteProfile(name="Grounding", age=30, weight=70.0)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    db_session.add_all(
        [
            CoachMemory(
                athlete_profile_id=profile.id,
                memory_type=MEMORY_EPISODIC,
                category="life_event",
                summary="Bike fit",
                content="Athlete missed sessions for bike fit.",
                source="chat",
                dedupe_key="episodic:bike_fit:test",
                expires_at=datetime.utcnow() + timedelta(days=7),
            ),
            CoachMemory(
                athlete_profile_id=profile.id,
                memory_type=MEMORY_EPISODIC,
                category="travel",
                summary="Travel — Kolhapur",
                content="Athlete mentioned travel to Kolhapur.",
                source="chat",
                dedupe_key="episodic:travel:kolhapur",
                expires_at=datetime.utcnow() + timedelta(days=7),
            ),
        ]
    )
    db_session.commit()
    rows = db_session.query(CoachMemory).all()
    filtered = filter_memories_for_message(rows, CLEAN_WEEKEND_MESSAGE)
    assert filtered == []

    block = format_memory_prompt_block(rows, message=CLEAN_WEEKEND_MESSAGE)
    assert "athlete missed sessions for bike fit" not in block.lower()
    assert "travel to kolhapur" not in block.lower()
    assert "no cross-session facts apply" in block.lower()


def test_memory_bundle_scopes_prompt_to_message(db_session):
    profile = AthleteProfile(
        name="Grounding",
        age=30,
        weight=70.0,
        planning_notes="Travel to Kolhapur in September — keep runs flexible.",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    bundle = build_memory_bundle(db_session, profile, message=CLEAN_WEEKEND_MESSAGE)
    block = bundle["prompt_block"].lower()
    assert "kolhapur" not in block


def test_template_plan_advice_clean_weekend_no_travel_bleed():
    reply = template_plan_advice(
        CLEAN_WEEKEND_MESSAGE,
        {"load": {"minutes_acwr": 0.95}},
        context={
            "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
            "coros": {"latest_health": {"hrv": 63}},
        },
    )
    text = reply["reply"].lower()
    assert "bike fit" not in text
    assert "kolhapur" not in text
    assert "on the train" not in text
    assert "coach's rule:" in text.lower()
    assert "the bottom line:" in text.lower()

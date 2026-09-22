"""Step 4: three-step voice, rolling facts, and fail-closed BFR pressure."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AthleteProfile
from app.services.ai_coach import schedule_system_prompt, schedule_task, support_chat_system_prompt
from app.services.coach_ai import coach_chat
from app.services.coach_conversation import (
    BFR_REFUSAL,
    TAPER_TANTRUM_REPLY,
    bfr_pressure_reply,
    is_taper_tantrum,
    physiological_fact,
    rolling_state_summary,
    taper_tantrum_reply,
)
from app.services.coach_memory import extract_episodic_from_chat
from app.services.coach_skills import SKILL_SUPPORT_CHAT


def test_schedule_prompt_bans_badges_and_requires_the_three_steps():
    system = schedule_system_prompt("full_report")
    task = schedule_task("full_report")
    lowered = system.lower()
    assert "empathy" in lowered
    assert "direction" in lowered
    assert "practical analogy" in lowered
    assert "coiling the spring" in lowered
    assert "take a deep breath" in lowered
    assert "you've got the right instincts" in lowered
    assert "never output a status badge" in lowered
    assert "copy the status line exactly" not in lowered
    assert "copy the precomputed" not in task.lower()
    support = support_chat_system_prompt().lower()
    assert "take a deep breath" in support
    assert "you've got the right instincts" in support


def test_taper_tantrum_reply_has_empathy_direction_and_analogy_without_a_badge():
    message = "I'm three days out from my race, feeling sluggish, and these phantom pains are freaking me out."
    reply = taper_tantrum_reply(message)
    assert reply == TAPER_TANTRUM_REPLY
    assert is_taper_tantrum(message) is True
    lowered = reply.lower()
    assert "sluggish" in lowered
    assert "zone 1" in lowered
    assert "coiling the spring" in lowered
    assert "🟢" not in reply
    assert "TODAY'S CALL" not in reply
    assert "take a deep breath" not in lowered
    assert "right instincts" not in lowered


def test_bfr_without_aop_refuses_a_static_pressure():
    reply = bfr_pressure_reply("What pressure should I set my BFR cuffs to?", None)
    assert reply == BFR_REFUSAL
    assert not re.search(r"\d+\s*mmHg", reply)
    assert "40-80%" in reply
    assert "physical therapist" in reply.lower()
    assert bfr_pressure_reply("How does BFR affect threshold recovery?", None) is None


def test_bfr_with_aop_uses_forty_to_eighty_percent_of_that_baseline():
    reply = bfr_pressure_reply("What mmHg should my BFR cuffs be?", 200)
    assert reply is not None
    assert "80" in reply and "160" in reply
    assert "200" in reply
    assert "150 mmHg" not in reply


def test_rolling_state_keeps_the_fact_and_drops_the_panic():
    history = [
        {
            "role": "user",
            "content": "I'm panicking. My hamstring is 3/10 stiff and I feel so anxious.",
        },
        {"role": "assistant", "content": "Take a deep breath, are you still anxious?"},
        {"role": "user", "content": "Feeling better. The anxiety is gone."},
    ]
    summary = rolling_state_summary(history)
    assert "3/10" in summary
    assert "hamstring" in summary
    assert "panic" not in summary.lower()
    assert "anxious" not in summary.lower()
    assert "deep breath" not in summary.lower()
    fact = physiological_fact("I missed my threshold session and I feel guilty")
    assert fact == "User missed a key session"
    assert "guilty" not in fact.lower()


def test_missed_session_memory_stores_a_fact_not_the_raw_panic():
    candidates = extract_episodic_from_chat(
        "I missed my threshold session and I am panicking about it",
        skill=SKILL_SUPPORT_CHAT,
        clock={"today": __import__("datetime").date(2026, 9, 22)},
    )
    missed = [item for item in candidates if item.category == "missed_session"]
    assert missed
    assert missed[0].content == "User missed a key session"
    assert "panic" not in missed[0].content.lower()


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


def _profile(db, **extra) -> AthleteProfile:
    profile = AthleteProfile(
        name="Voice",
        age=32,
        weight=68.0,
        onboarding_completed=True,
        **extra,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_chat_taper_tantrum_is_the_elite_reply(db_session):
    profile = _profile(db_session)
    result = coach_chat(
        db_session,
        profile,
        "Three days out from the race. I feel sluggish and these phantom pains won't quit.",
    )
    text = result["reply"]["reply"]
    assert text == TAPER_TANTRUM_REPLY
    assert "🟢" not in text
    assert result["provider"] == "taper-voice"


def test_chat_bfr_without_aop_refuses_and_with_aop_scales(db_session):
    profile = _profile(db_session)
    refused = coach_chat(db_session, profile, "What pressure should I set my BFR cuffs to?")
    text = refused["reply"]["reply"]
    assert text == BFR_REFUSAL
    assert not re.search(r"\d+\s*mmHg", text)
    assert refused["provider"] == "bfr-gate"

    calibrated = _profile(db_session, aop_mmhg=180)
    answered = coach_chat(db_session, calibrated, "What pressure should I set my BFR cuffs to?")
    scaled = answered["reply"]["reply"]
    assert "72" in scaled and "144" in scaled
    assert "180" in scaled

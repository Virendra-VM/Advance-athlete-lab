"""Phase 5 — plain-language quick debrief guardrails and eval bank."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AthleteProfile, CoachMessage, CoachReviewFlag
from app.services.ai_coach import template_quick_debrief
from app.services.coach_ai import _maybe_auto_flag_coach_reply
from app.services.coach_debrief_plain import (
    QUICK_DEBRIEF_FLAG_WORDS,
    QUICK_DEBRIEF_MAX_FK,
    apply_quick_debrief_plain_language,
    count_bold_spans,
    score_quick_debrief_quality,
    should_auto_flag_quick_debrief,
    strip_analogies_unless_teaching,
    trim_excess_bold,
    validate_debrief_eval_reply,
)
from app.services.debrief_mode import DEBRIEF_QUICK, is_quick_debrief_compliant
from scripts.ai_eval.coach_golden_bank import DEBRIEF_EVAL_CASES

_SATURDAY_RIDE_PACKET = {
    "name": "Morning Ride",
    "when": "Saturday",
    "minutes": 277,
    "km": 60.05,
    "family": "ride",
    "modality": "ride",
    "classification": "long",
    "power": {
        "source": "estimated",
        "coaching_note": "No power meter — Strava estimated watts are reference only.",
    },
    "heart_rate": {"avg_bpm": 138, "pct_lthr_avg": 82},
    "week_plan_session": {"title": "Easy ride", "duration_min": 90},
    "execution_headline": {
        "headline": "277 min / 60.05 km — longer than your 90 min Easy ride",
        "duration_longer": True,
    },
}

_SUNDAY_RUN_PACKET = {
    "name": "Sunday Long Run",
    "when": "Sunday",
    "minutes": 88,
    "km": 13.0,
    "pace_min_per_km": 6.77,
    "family": "run",
    "sport": "Run",
    "modality": "run",
    "classification": "steady",
    "power": {"source": "absent", "coaching_note": "Runs use pace and HR — no watt load."},
    "heart_rate": {"avg_bpm": 145, "pct_lthr_avg": 83},
    "run_intensity": {"pace_label": "easy", "hr_label": "steady"},
    "week_plan_session": {
        "title": "Easy long run",
        "duration_min": 60,
        "session_type": "easy",
        "intensity": "conversational",
    },
    "execution_headline": {
        "headline": (
            "88 min / 13.0 km at 6.77 min/km — longer than your 60 min Easy long run — "
            "not easy vs plan — HR 145 avg (83% LTHR)"
        ),
        "intensity_mismatch": True,
    },
}

_SAFETY = {"load": {"minutes_acwr": 1.21}, "injuries": {"active": []}}
_CONTEXT = {"coros": {"latest_health": {"sleep_score": 72, "hrv": 48, "resting_heart_rate": 52}}}


def _quick_reply(message: str, packet: dict) -> dict:
    reply = template_quick_debrief(message, _SAFETY, [], session_packet=packet, context=_CONTEXT)
    return apply_quick_debrief_plain_language(reply, message=message, session_packet=packet)


def test_debrief_eval_bank_has_phase5_cases():
    assert len(DEBRIEF_EVAL_CASES) >= 2
    ids = {case.case_id for case in DEBRIEF_EVAL_CASES}
    assert "debrief_saturday_no_meter_ride" in ids
    assert "debrief_sunday_easy_run_mismatch" in ids


def test_saturday_no_meter_ride_passes_eval_bank():
    case = next(c for c in DEBRIEF_EVAL_CASES if c.case_id == "debrief_saturday_no_meter_ride")
    reply = _quick_reply(case.message, _SATURDAY_RIDE_PACKET)
    score, detail = validate_debrief_eval_reply(reply["reply"], case)
    assert score == 1.0, detail
    assert "Normalized power" not in reply["reply"]


def test_sunday_easy_run_mismatch_passes_eval_bank():
    case = next(c for c in DEBRIEF_EVAL_CASES if c.case_id == "debrief_sunday_easy_run_mismatch")
    reply = _quick_reply(case.message, _SUNDAY_RUN_PACKET)
    score, detail = validate_debrief_eval_reply(reply["reply"], case)
    assert score == 1.0, detail
    assert is_quick_debrief_compliant(reply["reply"])


def test_strip_analogies_unless_teaching():
    text = "Good session. Your engine was overheating like a radiator."
    cleaned = strip_analogies_unless_teaching(text, "How was today?")
    assert "engine" not in cleaned.lower()
    assert "radiator" not in cleaned.lower()

    kept = strip_analogies_unless_teaching(text, "Why did my HR spike — explain how pacing works")
    assert "engine" in kept.lower()


def test_trim_excess_bold_keeps_plan_and_watch_numbers():
    text = (
        "**Longer than planned** and **HRV 48** plus **random one** **random two** **random three**"
    )
    trimmed = trim_excess_bold(text, max_spans=3)
    assert count_bold_spans(trimmed) <= 3
    assert "**Longer than planned**" in trimmed
    assert "**HRV 48**" in trimmed


def test_score_flags_bloated_quick_debrief():
    bloated = (
        "⚡ BOTTOM LINE\n"
        + " ".join(["word"] * 180)
        + "\n\n📋 VS PLAN\nShort.\n\n🧠 RECOVERY\nShort."
    )
    quality = score_quick_debrief_quality(bloated, "How was today?")
    assert quality["words"] > QUICK_DEBRIEF_FLAG_WORDS
    assert should_auto_flag_quick_debrief(quality)
    assert "words>150" in quality["issues"]


def test_template_quick_debrief_meets_fk_and_word_limits():
    for message, packet in (
        ("How was Saturday's ride?", _SATURDAY_RIDE_PACKET),
        ("Quick debrief Sunday run", _SUNDAY_RUN_PACKET),
    ):
        reply = _quick_reply(message, packet)
        quality = reply["_quick_debrief_quality"]
        assert quality["fk_grade"] <= QUICK_DEBRIEF_MAX_FK + 1.5, quality
        assert quality["words"] <= QUICK_DEBRIEF_FLAG_WORDS, quality
        assert not should_auto_flag_quick_debrief(quality), quality


def test_auto_flag_quick_debrief_review_queue():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        profile = AthleteProfile(name="Debrief QA", age=30, weight=70.0)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        message = CoachMessage(
            athlete_profile_id=profile.id,
            role="assistant",
            content="placeholder",
            created_at=datetime.utcnow(),
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        bloated = (
            "⚡ BOTTOM LINE\n"
            + " ".join(["padding"] * 160)
            + "\n\n📋 VS PLAN\nOk.\n\n🧠 RECOVERY\nOk."
        )
        quality = score_quick_debrief_quality(bloated, "How was today?")

        _maybe_auto_flag_coach_reply(
            db,
            profile.id,
            message.id,
            bloated,
            skill="review_session",
            debrief_mode=DEBRIEF_QUICK,
            message="How was today?",
            quick_debrief_quality=quality,
        )

        flag = db.query(CoachReviewFlag).filter_by(message_id=message.id).one()
        assert flag.category == "quick_debrief"
        assert flag.reason == "auto_quality"
        assert "words>150" in (flag.notes or "")
    finally:
        db.close()

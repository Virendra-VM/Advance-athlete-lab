"""Intent router for coach chat — autopsy vs week plan vs general."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coach_intent import (  # noqa: E402
    GENERAL_CHAT,
    SCHEDULE_UPDATE,
    WORKOUT_AUDIT,
    classify_chat_intent,
)
from app.services.ai_coach import template_schedule  # noqa: E402
from app.services.session_telemetry import detect_chat_intent  # noqa: E402


def test_workout_audit_examples():
    assert classify_chat_intent("How was today's session?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("analyse this ride", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("How was yoga?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("you got it wrong coach", use_llm=False) == WORKOUT_AUDIT
    paste = (
        "Tuesday 3x10 over-under. FTP 231W. Unders 201-204W. "
        "Overs 259-264W, surges 284W. Cadence 83-93 rpm. Peak HR 183 bpm."
    )
    assert classify_chat_intent(paste, use_llm=False) == WORKOUT_AUDIT


def test_schedule_update_examples():
    assert (
        classify_chat_intent("How should I adjust this week?", use_llm=False)
        == SCHEDULE_UPDATE
    )
    assert classify_chat_intent("Plan my week around my lower back", use_llm=False) == SCHEDULE_UPDATE
    proposed = """
I want to train this week:
Monday rest
Tuesday cycling quality
Wednesday yoga
Thursday easy run
Friday strength
Saturday long ride
Sunday rest
"""
    assert classify_chat_intent(proposed, use_llm=False) == SCHEDULE_UPDATE
    assert classify_chat_intent("update my schedule for this week", use_llm=False) == SCHEDULE_UPDATE


def test_general_chat_examples():
    assert classify_chat_intent("How easy should my easy sessions feel?", use_llm=False) == GENERAL_CHAT
    assert classify_chat_intent("I missed two sessions — what now?", use_llm=False) == GENERAL_CHAT
    assert classify_chat_intent("What is ACWR?", use_llm=False) == GENERAL_CHAT


def test_activity_id_forces_audit():
    assert (
        classify_chat_intent("tell me about this", activity_id=3510, use_llm=False)
        == WORKOUT_AUDIT
    )


def test_schedule_plus_workout_paste_stays_audit():
    text = (
        "I had planned this week as per my schedule so do use your schedule "
        "to match my workout. You got it wrong. Lap 7 262 W, lap 12 281 W. "
        "Now go and analyse the workout."
    )
    assert classify_chat_intent(text, use_llm=False) == WORKOUT_AUDIT


def test_detect_chat_intent_wrapper_uses_new_labels():
    assert detect_chat_intent("How was today's session?") == WORKOUT_AUDIT
    assert detect_chat_intent("How should I adjust this week?") == SCHEDULE_UPDATE
    assert detect_chat_intent("I missed two sessions — what now?") == GENERAL_CHAT


def test_template_schedule_is_not_an_autopsy():
    from datetime import date

    reply = template_schedule(
        "How should I adjust this week?",
        {
            "load": {"acute_minutes": 300, "chronic_minutes": 280, "minutes_acwr": 1.02},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": ["lower back"], "avoid_keywords": ["deadlift"]},
        },
        [],
        current_plan={
            "plan": {
                "workouts": [
                    {
                        "date": "2026-09-01",
                        "title": "Cycling quality session",
                        "sport": "Cycling",
                        "session_type": "threshold",
                        "intensity": "hard",
                        "duration_min": 60,
                    }
                ]
            }
        },
        context={"coros": {"latest_health": {"sleep_score": 73, "hrv": 48}}},
        clock={"today": date(2026, 9, 2), "week_start": date(2026, 8, 31)},
    )
    text = reply["reply"]
    assert "TODAY'S CALL" in text
    assert "🟡 CAUTION / ABSORB" in text
    assert "LOCKER ROOM DIRECTIVE" in text
    assert "| Day | Session | Primary Focus |" in text
    assert "Coach's Secret Rule" in text
    assert "SPINE LOCK" in text
    assert "DO NOT" in text
    assert "[THE SCIENCE]" in text
    assert "[LOCKER ROOM LINGO]" in text
    assert "lower-back" in text.lower() or "spine" in text.lower()
    assert "NP" not in text and "TSS" not in text
    assert reply["intent"] == SCHEDULE_UPDATE


def run() -> None:
    tests = [
        test_workout_audit_examples,
        test_schedule_update_examples,
        test_general_chat_examples,
        test_activity_id_forces_audit,
        test_schedule_plus_workout_paste_stays_audit,
        test_detect_chat_intent_wrapper_uses_new_labels,
        test_template_schedule_is_not_an_autopsy,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

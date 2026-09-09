"""Intent router for coach chat — autopsy vs week plan vs general."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coach_intent import (  # noqa: E402
    CLINICAL_VETO,
    DAY_ADJUST,
    GENERAL_CHAT,
    OFF_TOPIC,
    SCHEDULE_UPDATE,
    SCIENCE_LOOKUP,
    WEEK_REVIEW,
    WORKOUT_AUDIT,
    classify_chat_intent,
)
from app.services.ai_coach import review_week_window, template_schedule, template_week_review  # noqa: E402
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


def test_day_adjust_health_does_not_rewrite_the_week():
    assert (
        classify_chat_intent("HRV is low, should I still do intervals today?", use_llm=False)
        == DAY_ADJUST
    )
    assert (
        classify_chat_intent("Readiness is bad, how should I adjust this week?", use_llm=False)
        == DAY_ADJUST
    )
    assert classify_chat_intent("ACWR is high, skip today's quality", use_llm=False) == DAY_ADJUST
    assert classify_chat_intent("Stress is high this morning", use_llm=False) == DAY_ADJUST
    assert (
        classify_chat_intent("How should I adjust this week?", use_llm=False) == SCHEDULE_UPDATE
    )
    assert classify_chat_intent("How was today's session?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("What is HRV?", use_llm=False) == SCIENCE_LOOKUP


def test_general_chat_examples():
    assert classify_chat_intent("How easy should my easy sessions feel?", use_llm=False) == GENERAL_CHAT
    assert classify_chat_intent("I missed two sessions — what now?", use_llm=False) == GENERAL_CHAT
    assert classify_chat_intent("What is ACWR?", use_llm=False) == SCIENCE_LOOKUP


def test_week_review_examples():
    prompt = (
        "Done with the Week coach take a look at my week and tell me how did i do this week."
    )
    assert classify_chat_intent(prompt, use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("How did I do this week?", use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("How was my week?", use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("recap last week", use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("look at my week", use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("grade my week", use_llm=False) == WEEK_REVIEW


def test_week_review_does_not_steal_session_plan_or_science():
    assert classify_chat_intent("How was today's session?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("How did I do today?", use_llm=False) == WORKOUT_AUDIT
    assert (
        classify_chat_intent("How should I adjust this week?", use_llm=False)
        == SCHEDULE_UPDATE
    )
    assert classify_chat_intent("What is ACWR?", use_llm=False) == SCIENCE_LOOKUP
    assert classify_chat_intent("How easy should my easy sessions feel?", use_llm=False) == GENERAL_CHAT


def test_golden_router_table():
    assert classify_chat_intent("How was today's ride?", use_llm=False) == WORKOUT_AUDIT
    assert classify_chat_intent("How did I do this week?", use_llm=False) == WEEK_REVIEW
    assert classify_chat_intent("Adjust my plan for next week", use_llm=False) == SCHEDULE_UPDATE
    assert (
        classify_chat_intent("What is ACWR and why does it matter?", use_llm=False)
        == SCIENCE_LOOKUP
    )
    assert (
        classify_chat_intent(
            "I have sharp pain in my tendon when running", use_llm=False
        )
        == CLINICAL_VETO
    )
    assert classify_chat_intent("What stock should I buy?", use_llm=False) == OFF_TOPIC
    assert (
        classify_chat_intent(
            "How does blood flow restriction training affect my threshold recovery?",
            use_llm=False,
        )
        == SCIENCE_LOOKUP
    )
    assert (
        classify_chat_intent(
            "What is the latest research on heat acclimation for my half-marathon?",
            use_llm=False,
        )
        == SCIENCE_LOOKUP
    )


def test_monday_week_review_window_is_last_week():
    from datetime import date

    clock = {"today": date(2026, 9, 7), "week_start": date(2026, 9, 7)}
    prompt = (
        "Done with the Week coach take a look at my week and tell me how did i do this week."
    )
    start, end, label = review_week_window(clock, prompt)
    assert start == date(2026, 8, 31)
    assert end == date(2026, 9, 6)
    assert "last week" in label


def test_midweek_review_window_is_mon_to_today():
    from datetime import date

    clock = {"today": date(2026, 9, 9), "week_start": date(2026, 9, 7)}
    start, end, _label = review_week_window(clock, "How did I do this week?")
    assert start == date(2026, 9, 7)
    assert end == date(2026, 9, 9)


def test_template_week_review_is_not_an_autopsy():
    reply = template_week_review(
        "How did I do this week?",
        {
            "load": {"acute_minutes": 597, "chronic_minutes": 521, "minutes_acwr": 1.15},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": [], "avoid_keywords": []},
        },
        [],
        packet={
            "window": {
                "start": "2026-08-31",
                "end": "2026-09-06",
                "label": "last week (Mon–Sun just finished)",
            },
            "days": [
                {
                    "day": "Sunday",
                    "session": "Morning Ride",
                    "status": "Done",
                    "note": "275 min",
                }
            ],
            "totals": {"sessions": 1, "minutes": 275, "quality_days": 0},
            "recovery": {
                "avg_sleep_score": 50,
                "avg_sleep_min": 329,
                "avg_hrv": 42,
                "avg_stress": 43,
                "avg_rhr": 53,
            },
        },
    )
    text = reply["reply"]
    assert "WEEK GRADE" in text
    assert "WHAT LANDED" in text
    assert "Morning Ride" in text
    assert "THE BOTTOM LINE" not in text
    assert "MECHANICAL PRECISION" not in text
    assert "NP" not in text and "TSS" not in text
    assert reply["intent"] == WEEK_REVIEW


def test_week_review_packet_lists_all_days_not_one_ride():
    from datetime import date
    from zoneinfo import ZoneInfo

    from app.services.coach_ai import build_week_review_packet

    clock = {
        "today": date(2026, 9, 7),
        "week_start": date(2026, 9, 7),
        "tz": ZoneInfo("UTC"),
    }
    packet = build_week_review_packet(
        {
            "recent_activities": [
                {
                    "name": "Morning Ride",
                    "activity_date": "2026-09-06",
                    "sport": "Ride",
                    "minutes": 275,
                    "km": 80,
                    "avg_hr": 133,
                },
                {
                    "name": "Easy Run",
                    "activity_date": "2026-09-03",
                    "sport": "Run",
                    "minutes": 40,
                    "km": 6,
                    "avg_hr": 140,
                },
            ],
            "coros": {"health_trend": []},
            "safety": {
                "load": {
                    "minutes_acwr": 1.15,
                    "acute_minutes": 597,
                    "chronic_minutes": 521,
                }
            },
        },
        clock,
        None,
        "Done with the Week coach take a look at my week and tell me how did i do this week.",
    )
    assert packet["window"]["start"] == "2026-08-31"
    assert packet["window"]["end"] == "2026-09-06"
    landed = [
        day["session"] for day in packet["days"] if day["status"] in {"Done", "Unplanned"}
    ]
    assert "Morning Ride" in landed
    assert "Easy Run" in landed
    assert packet["totals"]["sessions"] == 2
    assert "laps" not in packet


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
    assert detect_chat_intent(
        "Done with the Week coach take a look at my week and tell me how did i do this week."
    ) == WEEK_REVIEW


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
    assert "THE SCIENCE" in text
    assert "LOCKER ROOM LINGO" in text
    assert "lower-back" in text.lower() or "spine" in text.lower()
    assert "NP" not in text and "TSS" not in text
    assert reply["intent"] == SCHEDULE_UPDATE


def run() -> None:
    tests = [
        test_workout_audit_examples,
        test_schedule_update_examples,
        test_day_adjust_health_does_not_rewrite_the_week,
        test_general_chat_examples,
        test_week_review_examples,
        test_week_review_does_not_steal_session_plan_or_science,
        test_golden_router_table,
        test_monday_week_review_window_is_last_week,
        test_midweek_review_window_is_mon_to_today,
        test_template_week_review_is_not_an_autopsy,
        test_week_review_packet_lists_all_days_not_one_ride,
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

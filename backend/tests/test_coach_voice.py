"""Phase 2 — conditional teaching, plain language, analogy variety."""

from __future__ import annotations

from datetime import date

from app.services.ai_coach import schedule_system_prompt, template_schedule
from app.services.coach_voice import (
    build_voice_context,
    extract_recent_analogies,
    finalize_general_chat_reply,
    finalize_schedule_full_reply,
    readiness_is_red,
    should_include_weekly_translations,
    strip_triplet_blocks,
    wants_teaching,
)


def test_wants_teaching_detects_why_and_how():
    assert wants_teaching("Why is Thursday hard?") is True
    assert wants_teaching("Explain how ACWR works") is True
    assert wants_teaching("How should I adjust this week?") is False


def test_readiness_is_red_below_65():
    safety = {"readiness": {"action": "proceed"}}
    context = {"coros": {"latest_health": {"sleep_score": 58}}}
    assert readiness_is_red(safety, context) is True


def test_should_include_weekly_translations_only_when_earned():
    safety = {"readiness": {"action": "proceed"}}
    context = {"coros": {"latest_health": {"sleep_score": 80}}}
    assert should_include_weekly_translations("Adjust my week", safety, context) is False
    assert should_include_weekly_translations("Why is my week like this?", safety, context) is True
    red_context = {"coros": {"latest_health": {"sleep_score": 55}}}
    assert should_include_weekly_translations("Adjust my week", safety, red_context) is True


def test_extract_recent_analogies_from_history():
    history = [
        {"role": "user", "content": "Plan my week"},
        {
            "role": "assistant",
            "content": "🔬 WEEKLY TRANSLATIONS\n• REAL-WORLD EXAMPLE: like a battery at 80%",
        },
        {"role": "user", "content": "again"},
        {
            "role": "assistant",
            "content": "The engine overheats when you stack hard days.",
        },
    ]
    found = extract_recent_analogies(history, max_assistant_turns=2)
    assert "battery" in found
    assert "engine" in found


def test_build_voice_context_includes_analogy_ban():
    history = [
        {
            "role": "assistant",
            "content": "Think of ACWR like a radiator — stay cool.",
        }
    ]
    voice = build_voice_context(
        "Adjust my week",
        {"readiness": {"action": "proceed"}},
        {"coros": {"latest_health": {"sleep_score": 75}}},
        history,
    )
    assert "radiator" in voice.analogy_ban_prompt
    assert "CONDITIONAL TEACHING" in voice.conditional_teaching_block


def test_strip_triplet_blocks_removes_weekly_translations():
    raw = """🟢 TODAY'S CALL
**Ready**

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: ACWR
• 🗣️ LOCKER ROOM LINGO: easy week
• 💡 REAL-WORLD EXAMPLE: battery
"""
    cleaned = strip_triplet_blocks(raw)
    assert "WEEKLY TRANSLATIONS" not in cleaned
    assert "THE SCIENCE" not in cleaned


def test_finalize_schedule_full_reply_strips_unearned_triplets():
    voice = build_voice_context(
        "Adjust my week",
        {"readiness": {"action": "proceed"}},
        {"coros": {"latest_health": {"sleep_score": 78}}},
        [],
    )
    reply = finalize_schedule_full_reply(
        {
            "reply": """🟢 TODAY'S CALL
**Ready**

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: polarized
• 🗣️ LOCKER ROOM LINGO: one hard day
• 💡 REAL-WORLD EXAMPLE: radiator
"""
        },
        voice,
        {"readiness": {"action": "proceed"}},
        {"coros": {"latest_health": {"sleep_score": 78}}},
    )
    assert "WEEKLY TRANSLATIONS" not in reply["reply"]
    assert "THE SCIENCE" not in reply["reply"]


def test_finalize_schedule_full_reply_adds_recovery_rationale_when_red():
    safety = {"readiness": {"action": "rest_or_mobility"}}
    context = {"coros": {"latest_health": {"sleep_score": 52}}}
    voice = build_voice_context("Adjust my week", safety, context, [])
    reply = finalize_schedule_full_reply(
        {"reply": "🟢 TODAY'S CALL\n**🔴 REST / RESTORE**"},
        voice,
        safety,
        context,
    )
    assert "Why recovery" in reply["reply"]


def test_finalize_general_chat_strips_triplets_without_why():
    voice = build_voice_context(
        "I missed yesterday",
        {"readiness": {"action": "proceed"}},
        None,
        [],
    )
    reply = finalize_general_chat_reply(
        {
            "reply": """📌 ANSWER
• Fine

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: guilt
"""
        },
        voice,
    )
    assert "WEEKLY TRANSLATIONS" not in reply["reply"]


def test_schedule_system_prompt_full_report_includes_conditional_teaching():
    voice = build_voice_context(
        "How should I adjust this week?",
        {"readiness": {"action": "proceed"}},
        {"coros": {"latest_health": {"sleep_score": 75}}},
        [],
    )
    system = schedule_system_prompt("full_report", voice)
    assert "CONDITIONAL TEACHING" in system
    assert "80-180 words" in system
    assert "Do NOT add 🔬 WEEKLY TRANSLATIONS" in system


def test_template_schedule_skips_teaching_for_simple_adjust():
    reply = template_schedule(
        "How should I adjust this week?",
        {
            "load": {"minutes_acwr": 1.02},
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
    assert "THE SCIENCE" not in text
    assert "LOCKER ROOM LINGO" not in text
    assert "WEEKLY TRANSLATIONS" not in text


def test_template_schedule_includes_why_block_when_asked():
    reply = template_schedule(
        "Why should I keep Thursday hard this week?",
        {
            "load": {"minutes_acwr": 1.15},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": []},
        },
        [],
        current_plan={
            "plan": {
                "workouts": [
                    {
                        "date": "2026-09-04",
                        "title": "Bike O/U",
                        "sport": "Cycling",
                        "session_type": "threshold",
                        "intensity": "hard",
                        "duration_min": 60,
                    }
                ]
            }
        },
        context={"coros": {"latest_health": {"sleep_score": 82, "hrv": 60}}},
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    text = reply["reply"]
    assert "Why this works" in text
    assert "ACWR" in text
    assert "THE SCIENCE" not in text


def run() -> None:
    tests = [
        test_wants_teaching_detects_why_and_how,
        test_readiness_is_red_below_65,
        test_should_include_weekly_translations_only_when_earned,
        test_extract_recent_analogies_from_history,
        test_build_voice_context_includes_analogy_ban,
        test_strip_triplet_blocks_removes_weekly_translations,
        test_finalize_schedule_full_reply_strips_unearned_triplets,
        test_finalize_schedule_full_reply_adds_recovery_rationale_when_red,
        test_finalize_general_chat_strips_triplets_without_why,
        test_schedule_system_prompt_full_report_includes_conditional_teaching,
        test_template_schedule_skips_teaching_for_simple_adjust,
        test_template_schedule_includes_why_block_when_asked,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

"""Phase 0/1 — schedule action summary mode and two-pass replan helpers."""

from __future__ import annotations

from datetime import date

from app.services.ai_coach import (
    schedule_system_prompt,
    schedule_task,
    template_schedule,
)
from app.services.coach_schedule_mode import finalize_schedule_narrator_reply
from app.services.coach_schedule_mode import (
    ACTION_SUMMARY,
    FULL_REPORT,
    build_proposed_schedule_week,
    detect_schedule_response_mode,
    diff_week_plans,
    ensure_what_changed_block,
    format_physiology_anchor_lines,
    strip_weekly_translations,
    wants_same_schedule,
)


USER_REPLAN_MESSAGE = (
    "Plan my this week again keep the schedule same, but plan it with your new updated "
    "workout library my newly add LTHR FTP MAX HR and Resrting HR and etc."
)


def test_detect_schedule_response_mode_replan_with_zones():
    assert detect_schedule_response_mode(USER_REPLAN_MESSAGE) == ACTION_SUMMARY
    assert detect_schedule_response_mode("rebuild this week with new FTP") == ACTION_SUMMARY
    assert detect_schedule_response_mode("How should I adjust this week?") == FULL_REPORT


def test_wants_same_schedule():
    assert wants_same_schedule(USER_REPLAN_MESSAGE) is True
    assert wants_same_schedule("replan with new zones") is False


def test_format_physiology_anchor_lines():
    lines = format_physiology_anchor_lines(
        {
            "physiology": {
                "ftp_watts": 232,
                "ftp_source": "profile",
                "lthr_bpm": 168,
                "max_hr_bpm": 192,
                "resting_hr_bpm": 51,
            }
        }
    )
    blob = " ".join(lines)
    assert "232" in blob
    assert "168" in blob
    assert "192" in blob
    assert "51" in blob


def test_diff_week_plans_detects_intensity_change():
    old = [
        {
            "date": "2026-09-04",
            "title": "Bike O/U",
            "intensity": "under 180–190 W · over 220–240 W",
            "structure": [{"detail": "180-190W"}],
        }
    ]
    new = [
        {
            "date": "2026-09-04",
            "title": "Bike O/U",
            "intensity": "under 204–213 W · over 244–267 W",
            "structure": [{"detail": "204-213W"}],
        }
    ]
    diff = diff_week_plans(old, new)
    assert len(diff["changes"]) == 1
    assert "204" in diff["changes"][0]["summary"] or "intensity" in diff["changes"][0]["kind"]


def test_strip_weekly_translations():
    raw = """🟢 TODAY'S CALL
**🟢 HARD**

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: ACWR in range
• 🗣️ LOCKER ROOM LINGO: easy week
• 💡 REAL-WORLD EXAMPLE: battery metaphor
"""
    cleaned = strip_weekly_translations(raw)
    assert "WEEKLY TRANSLATIONS" not in cleaned
    assert "THE SCIENCE" not in cleaned
    assert "LOCKER ROOM LINGO" not in cleaned
    assert "TODAY'S CALL" in cleaned


def test_ensure_what_changed_block_prepends_when_missing():
    reply = "🟢 TODAY'S CALL\n**Ready**"
    what = ["📊 **WHAT CHANGED**", "• **FTP:** 232 W"]
    merged = ensure_what_changed_block(reply, what)
    assert merged.index("WHAT CHANGED") < merged.index("TODAY'S CALL")


def test_finalize_schedule_narrator_reply_forces_plan_and_strips_triplets():
    proposed = {
        "title": "Week",
        "week_start": "2026-09-01",
        "workouts": [{"date": "2026-09-01", "title": "Rest", "session_type": "rest"}],
    }
    diff = {"changes": [], "unchanged_days": 1, "same_shape": True}
    physiology = ["**FTP:** 232 W"]
    raw = {
        "reply": """🟢 TODAY'S CALL
**Ready**

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: polarized
• 🗣️ LOCKER ROOM LINGO: one hard day
• 💡 REAL-WORLD EXAMPLE: radiator
""",
        "citations": [],
        "escalate": False,
    }
    out = finalize_schedule_narrator_reply(
        raw,
        proposed_plan=proposed,
        schedule_mode=ACTION_SUMMARY,
        schedule_diff=diff,
        physiology_lines=physiology,
        message=USER_REPLAN_MESSAGE,
    )
    assert "WEEKLY TRANSLATIONS" not in out["reply"]
    assert "WHAT CHANGED" in out["reply"]
    assert out["week_plan"] == proposed


def test_schedule_action_prompt_bans_translation_triplets():
    system = schedule_system_prompt(ACTION_SUMMARY)
    task = schedule_task(ACTION_SUMMARY)
    assert "WEEKLY TRANSLATIONS" in system and "BAN" in system
    assert "WHAT CHANGED" in system
    assert "triplets" in system.lower() or "TRIPLETS" in system
    assert "PROPOSED WEEK PLAN" in task


def test_schedule_full_report_prompt_uses_conditional_teaching():
    system = schedule_system_prompt(FULL_REPORT)
    assert "Do NOT add 🔬 WEEKLY TRANSLATIONS" in system
    assert "Why this works" in system or "**Why this works**" in system
    assert "80-180 words" in system


def test_template_schedule_action_summary_shape():
    proposed = {
        "title": "Week of Sep 01",
        "summary": "Zone refresh",
        "focus": "Consistency",
        "week_start": "2026-08-31",
        "workouts": [
            {
                "date": "2026-08-31",
                "title": "Rest",
                "sport": "Rest",
                "session_type": "rest",
                "intensity": "None",
            },
            {
                "date": "2026-09-04",
                "title": "Bike O/U 3×12",
                "sport": "Cycling",
                "session_type": "threshold",
                "intensity": "under 204–213 W · over 244–267 W",
            },
        ],
    }
    diff = diff_week_plans(
        [
            {
                "date": "2026-09-04",
                "title": "Bike O/U 3×12",
                "intensity": "under 180–190 W",
                "structure": [],
            }
        ],
        proposed["workouts"],
    )
    reply = template_schedule(
        USER_REPLAN_MESSAGE,
        {
            "load": {"minutes_acwr": 1.13},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": []},
        },
        [],
        proposed_plan=proposed,
        diff=diff,
        physiology_lines=["**FTP:** 232 W", "**LTHR:** 168 bpm"],
        response_mode=ACTION_SUMMARY,
        context={
            "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
            "coros": {"latest_health": {"sleep_score": 85, "hrv": 63}},
        },
        clock={"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)},
    )
    text = reply["reply"]
    assert "WHAT CHANGED" in text
    assert "232" in text
    assert "REVISED WEEK" in text
    assert "WEEKLY TRANSLATIONS" not in text
    assert "THE SCIENCE" not in text
    assert "LOCKER ROOM LINGO" not in text
    assert reply.get("week_plan") == proposed


def test_build_proposed_schedule_week_same_schedule_rezones():
    context = {
        "profile": {
            "primary_goal": "Half marathon",
            "sports": [{"sport": "Running", "priority": "primary"}],
            "days_per_week": 5,
            "workout_duration_minutes": 60,
        },
        "physiology": {
            "ftp_watts": 232,
            "lthr_bpm": 168,
            "max_hr_bpm": 192,
            "resting_hr_bpm": 51,
        },
        "season": {"current_phase": {"phase_type": "build"}},
    }
    safety = {
        "load": {"minutes_acwr": 1.1},
        "readiness": {"action": "proceed", "reason": "Cleared for training."},
        "injuries": {
            "active": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        "max_session_minutes": 180,
        "max_hard_sessions": 2,
        "max_days_per_week": 5,
        "max_weekly_minutes": 400,
        "weekly_minutes_budget": 400,
        "typical_session_minutes": 45,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
    }
    current_plan = {
        "plan": {
            "workouts": [
                {
                    "date": "2026-08-31",
                    "title": "Rest day",
                    "sport": "Rest",
                    "session_type": "rest",
                    "duration_min": 0,
                    "intensity": "None",
                },
                {
                    "date": "2026-09-03",
                    "title": "Easy aerobic",
                    "sport": "Running",
                    "session_type": "easy",
                    "duration_min": 45,
                    "intensity": "Easy",
                },
            ]
        }
    }
    proposed = build_proposed_schedule_week(
        context=context,
        safety=safety,
        clock={"week_start": date(2026, 8, 31), "today": date(2026, 9, 3)},
        current_plan=current_plan,
        message=USER_REPLAN_MESSAGE,
    )
    assert proposed.get("workouts")
    assert len(proposed["workouts"]) == 2
    assert proposed["workouts"][0]["title"] == "Rest day"


def run() -> None:
    tests = [
        test_detect_schedule_response_mode_replan_with_zones,
        test_wants_same_schedule,
        test_format_physiology_anchor_lines,
        test_diff_week_plans_detects_intensity_change,
        test_strip_weekly_translations,
        test_ensure_what_changed_block_prepends_when_missing,
        test_finalize_schedule_narrator_reply_forces_plan_and_strips_triplets,
        test_schedule_action_prompt_bans_translation_triplets,
        test_schedule_full_report_prompt_keeps_translations,
        test_template_schedule_action_summary_shape,
        test_build_proposed_schedule_week_same_schedule_rezones,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

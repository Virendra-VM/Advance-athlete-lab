"""Phase 3 — two-pass schedule generation (planner + narrator)."""

from __future__ import annotations

from datetime import date

from app.services.ai_coach import schedule_task, template_schedule
from app.services.coach_schedule_mode import (
    ACTION_SUMMARY,
    FULL_REPORT,
    build_planner_packet,
    build_proposed_schedule_week,
    build_schedule_narrator_block,
    detect_schedule_response_mode,
    diff_week_plans,
    extract_risk_flags,
    finalize_schedule_narrator_reply,
    format_physiology_anchor_lines,
)


def _safety():
    return {
        "load": {"minutes_acwr": 1.35},
        "readiness": {"action": "proceed", "reason": "Cleared."},
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


def test_pass1_runs_for_full_report_adjust_message():
    assert detect_schedule_response_mode("How should I adjust this week?") == FULL_REPORT


def test_build_planner_packet_shape():
    proposed = {
        "title": "Week",
        "week_start": "2026-09-01",
        "workouts": [{"date": "2026-09-01", "title": "Easy run", "session_type": "easy"}],
        "selection_engine": "swl-v2",
    }
    diff = {"changes": [{"summary": "Monday: easy run"}], "unchanged_days": 0, "total_days": 1}
    physiology = ["**FTP:** 232 W"]
    safety = _safety()
    packet = build_planner_packet(
        proposed_plan=proposed,
        schedule_diff=diff,
        physiology_lines=physiology,
        safety=safety,
        context={"physiology": {"ftp_watts": 232}},
        schedule_mode=FULL_REPORT,
        message="Adjust my week",
    )
    assert packet["intent"] == "SCHEDULE_UPDATE"
    assert packet["week_plan"] == proposed
    assert packet["changed_fields"] == ["Monday: easy run"]
    assert isinstance(packet["risk_flags"], list)
    assert packet["workout_count"] == 1


def test_extract_risk_flags_acwr_and_red_readiness():
    safety = _safety()
    flags = extract_risk_flags(safety, {"coros": {"latest_health": {"sleep_score": 80}}})
    assert any("ACWR" in flag for flag in flags)

    red_flags = extract_risk_flags(
        {"readiness": {"action": "rest_or_mobility"}, "load": {}, "injuries": {"has_severe_active": False}},
        {"coros": {"latest_health": {"sleep_score": 55}}},
    )
    assert any("Readiness below 65" in flag for flag in red_flags)


def test_build_schedule_narrator_block_includes_planner_packet():
    proposed = {"title": "Week", "workouts": [], "week_start": "2026-09-01"}
    diff = {"changes": []}
    block = build_schedule_narrator_block(
        schedule_mode=FULL_REPORT,
        planner_packet={"intent": "SCHEDULE_UPDATE", "week_plan": proposed},
        proposed_plan=proposed,
        schedule_diff=diff,
        physiology_lines=["**FTP:** 232 W"],
        table_rows=["| Day | Session | Primary Focus | Intensity | Coach's Secret Rule |"],
        today_call_block="TODAY CALL",
        athlete_state_block="ATHLETE STATE",
    )
    assert "Phase 3 two-pass" in block
    assert "PLANNER PACKET" in block
    assert "pass 2 narrator only" in block


def test_finalize_narrator_forces_week_plan_full_report():
    proposed = {
        "title": "Week",
        "week_start": "2026-09-01",
        "workouts": [{"date": "2026-09-01", "title": "Rest", "session_type": "rest"}],
    }
    voice = __import__(
        "app.services.coach_voice", fromlist=["build_voice_context"]
    ).build_voice_context(
        "Adjust my week",
        _safety(),
        {"coros": {"latest_health": {"sleep_score": 78}}},
        [],
    )
    out = finalize_schedule_narrator_reply(
        {
            "reply": """🟢 TODAY'S CALL
**Ready**

🔬 WEEKLY TRANSLATIONS
• 🔬 THE SCIENCE: polarized
"""
        },
        proposed_plan=proposed,
        schedule_mode=FULL_REPORT,
        schedule_diff={"changes": []},
        physiology_lines=[],
        message="Adjust my week",
        voice=voice,
        safety=_safety(),
        context={"coros": {"latest_health": {"sleep_score": 78}}},
    )
    assert out["week_plan"] == proposed
    assert "WEEKLY TRANSLATIONS" not in out["reply"]


def test_finalize_narrator_action_summary_what_changed():
    proposed = {
        "title": "Week",
        "week_start": "2026-09-01",
        "workouts": [{"date": "2026-09-04", "title": "Bike O/U", "session_type": "threshold"}],
    }
    diff = diff_week_plans([], proposed["workouts"])
    out = finalize_schedule_narrator_reply(
        {"reply": "🟢 TODAY'S CALL\n**Ready**"},
        proposed_plan=proposed,
        schedule_mode=ACTION_SUMMARY,
        schedule_diff=diff,
        physiology_lines=["**FTP:** 232 W"],
        message="Plan my week again keep schedule same with new FTP",
    )
    assert "WHAT CHANGED" in out["reply"]
    assert out["week_plan"] == proposed


def test_schedule_task_full_report_is_narrator_only():
    task = schedule_task(FULL_REPORT)
    assert "Pass 2 narrator only" in task
    assert "PLANNER PACKET" in task


def test_template_schedule_full_report_uses_proposed_plan():
    context = {
        "profile": {
            "primary_goal": "Half marathon",
            "sports": [{"sport": "Running", "priority": "primary"}],
            "days_per_week": 4,
            "workout_duration_minutes": 45,
        },
        "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
        "season": {"current_phase": {"phase_type": "build"}},
    }
    safety = _safety()
    proposed = build_proposed_schedule_week(
        context=context,
        safety=safety,
        clock={"week_start": date(2026, 8, 31), "today": date(2026, 9, 3)},
        current_plan=None,
        message="How should I adjust this week?",
    )
    reply = template_schedule(
        "How should I adjust this week?",
        safety,
        [],
        proposed_plan=proposed,
        diff=diff_week_plans([], proposed.get("workouts") or []),
        context=context,
        clock={"week_start": date(2026, 8, 31), "today": date(2026, 9, 3)},
    )
    assert reply.get("week_plan") == proposed
    assert "REVISED WEEK" in reply["reply"]
    assert "THE SCIENCE" not in reply["reply"]


def run() -> None:
    tests = [
        test_pass1_runs_for_full_report_adjust_message,
        test_build_planner_packet_shape,
        test_extract_risk_flags_acwr_and_red_readiness,
        test_build_schedule_narrator_block_includes_planner_packet,
        test_finalize_narrator_forces_week_plan_full_report,
        test_finalize_narrator_action_summary_what_changed,
        test_schedule_task_full_report_is_narrator_only,
        test_template_schedule_full_report_uses_proposed_plan,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

"""Phase B — coach tool executor tests."""

from __future__ import annotations

from datetime import date

from app.services.coach_agent import run_coach_agent, tools_for_skill
from app.services.coach_skills import (
    SKILL_ADJUST_DAY,
    SKILL_EXPLAIN_METRIC,
    SKILL_REVIEW_SESSION,
    SKILL_SUPPORT_CHAT,
    SKILL_VALIDATE_PLAN,
)
from app.services.coach_tools import (
    TOOL_CHECK_INJURY_RULES,
    TOOL_COMPARE_PLANNED_VS_DONE,
    TOOL_EXPLAIN_WITH_EVIDENCE,
    TOOL_GET_ATHLETE_SNAPSHOT,
    TOOL_GET_COACH_MEMORY,
    TOOL_GET_WEEK_PLAN,
    TOOL_PROPOSE_DAY_CHANGE,
    CoachToolContext,
    execute_tool,
    format_tool_results,
)


def _ctx(**overrides):
    base = {
        "message": "test",
        "skill": SKILL_VALIDATE_PLAN,
        "context": {
            "coros": {"latest_health": {"sleep_score": 82, "hrv": 63}},
            "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
        },
        "safety": {
            "load": {"minutes_acwr": 0.92, "acute_minutes": 300, "chronic_minutes": 325},
            "readiness": {"action": "proceed", "reason": "Cleared."},
            "injuries": {"active": ["lower back"], "avoid_keywords": ["deadlift"]},
            "spine_lock": True,
            "max_hard_sessions": 2,
            "no_consecutive_hard_days": True,
        },
        "clock": {"today": date(2026, 9, 4), "week_start": date(2026, 9, 1)},
        "current_plan": {
            "plan": {
                "workouts": [
                    {
                        "date": "2026-09-04",
                        "title": "Threshold ride",
                        "sport": "cycling",
                        "session_type": "threshold",
                        "intensity": "Hard",
                        "duration_min": 75,
                    },
                    {
                        "date": "2026-09-05",
                        "title": "Easy run",
                        "sport": "running",
                        "session_type": "easy",
                        "duration_min": 45,
                    },
                ]
            }
        },
        "hits": [
            {
                "heading": "ACWR and injury risk",
                "text": "Acute chronic workload ratio helps monitor spike risk.",
                "citation": {"slug": "aal-safety-and-load"},
                "score": 0.91,
            }
        ],
        "session_packet": {
            "activity_id": 42,
            "sport": "cycling",
            "modality": "ride",
            "date": "2026-09-04",
            "prescribed_vs_executed": {"hit_rate": 0.88},
            "normalized_power": 210,
        },
    }
    base.update(overrides)
    return CoachToolContext(**base)


def test_get_athlete_snapshot_returns_numbers():
    result = execute_tool(TOOL_GET_ATHLETE_SNAPSHOT, _ctx())
    assert result.ok
    assert result.data["load"]["minutes_acwr"] == 0.92
    assert result.data["daily_check_in"]["hrv"] == 63
    assert result.data["anchors"]["ftp_watts"] == 232


def test_get_week_plan_lists_workouts():
    result = execute_tool(TOOL_GET_WEEK_PLAN, _ctx())
    assert result.ok
    assert len(result.data["workouts"]) == 2
    assert result.data["workouts"][0]["when"] == "today"


def test_propose_day_change_downgrades_hard_session():
    ctx = _ctx(
        safety={
            "load": {"minutes_acwr": 1.55},
            "readiness": {"action": "downgrade_to_easy", "reason": "Poor HRV."},
            "injuries": {"active": []},
        }
    )
    result = execute_tool(TOOL_PROPOSE_DAY_CHANGE, ctx)
    assert result.ok
    assert result.data["changed"] is True
    assert result.data["after"]["session_type"] == "easy"


def test_explain_with_evidence_uses_hits():
    result = execute_tool(
        TOOL_EXPLAIN_WITH_EVIDENCE,
        _ctx(message="Why does ACWR matter for my training?"),
    )
    assert result.ok
    assert result.data["topic"] == "acwr"
    assert result.data["grounded"] is True
    assert result.data["chunks"][0]["slug"] == "aal-safety-and-load"


def test_compare_planned_vs_done_with_packet():
    result = execute_tool(TOOL_COMPARE_PLANNED_VS_DONE, _ctx())
    assert result.ok
    assert result.data["matched"] is True
    assert result.data["activity_id"] == 42


def test_compare_planned_vs_done_without_packet():
    result = execute_tool(TOOL_COMPARE_PLANNED_VS_DONE, _ctx(session_packet=None))
    assert result.ok
    assert result.data["matched"] is False


def test_check_injury_rules_spine_lock_and_veto():
    result = execute_tool(TOOL_CHECK_INJURY_RULES, _ctx())
    assert result.ok
    assert result.data["spine_lock"] is True
    assert "lower back" in result.data["active_injuries"]


def test_check_injury_rules_clinical_on_message():
    result = execute_tool(
        TOOL_CHECK_INJURY_RULES,
        _ctx(message="Sharp pain in my achilles when I run"),
    )
    assert result.ok
    assert result.data["clinical_boundary_hit"] is True


def test_format_tool_results_block():
    results = [
        execute_tool(TOOL_GET_ATHLETE_SNAPSHOT, _ctx()),
        execute_tool(TOOL_GET_WEEK_PLAN, _ctx()),
    ]
    block = format_tool_results(results)
    assert "COACH TOOLS" in block
    assert "get_athlete_snapshot" in block
    assert "0.92" in block


def test_tools_for_skill_validate_plan():
    tools = tools_for_skill(SKILL_VALIDATE_PLAN)
    assert TOOL_GET_ATHLETE_SNAPSHOT in tools
    assert TOOL_GET_WEEK_PLAN in tools
    assert TOOL_CHECK_INJURY_RULES in tools


def test_get_coach_memory_tool():
    ctx = _ctx(
        memory_snapshot=[
            {"type": "episodic", "category": "travel", "summary": "Travel", "content": "Kolhapur"}
        ]
    )
    result = execute_tool(TOOL_GET_COACH_MEMORY, ctx)
    assert result.ok
    assert result.data["count"] == 1
    assert "Kolhapur" in result.data["memories"][0]["content"]


def test_run_coach_agent_support_chat():
    run = run_coach_agent(_ctx(skill=SKILL_SUPPORT_CHAT, message="I missed two sessions"))
    assert TOOL_GET_COACH_MEMORY in run.tools_used
    assert TOOL_GET_ATHLETE_SNAPSHOT in run.tools_used
    assert TOOL_CHECK_INJURY_RULES in run.tools_used
    assert "COACH TOOLS" in run.prompt_block()


def test_run_coach_agent_explain_metric():
    run = run_coach_agent(
        _ctx(skill=SKILL_EXPLAIN_METRIC, message="Why is my HRV low?")
    )
    assert TOOL_EXPLAIN_WITH_EVIDENCE in run.tools_used
    assert "hrv" in run.prompt_block().lower() or "HRV" in run.prompt_block()


def test_run_coach_agent_adjust_day():
    run = run_coach_agent(
        _ctx(skill=SKILL_ADJUST_DAY, message="HRV is low — adjust today")
    )
    assert TOOL_PROPOSE_DAY_CHANGE in run.tools_used


def test_run_coach_agent_review_session():
    run = run_coach_agent(
        _ctx(skill=SKILL_REVIEW_SESSION, message="How was today's ride?")
    )
    assert TOOL_COMPARE_PLANNED_VS_DONE in run.tools_used

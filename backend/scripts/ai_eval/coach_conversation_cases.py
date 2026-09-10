"""Golden coach conversation cases for Phase 7 eval."""

from __future__ import annotations

from datetime import date

from app.services.coach_reply_eval import CoachEvalCase, CoachEvalExpectation
from app.services.coach_schedule_mode import ACTION_SUMMARY, FULL_REPORT

REPLAN_SAME_SCHEDULE_MESSAGE = (
    "Plan my this week again keep the schedule same, but plan it with your new updated "
    "workout library my newly add LTHR FTP MAX HR and Resrting HR and etc."
)

ADJUST_WEEK_MESSAGE = "How should I adjust this week with my current load?"

WHY_ACWR_MESSAGE = "Why does ACWR matter for my training this week?"

GENERAL_PACE_MESSAGE = "How should I pace my long run this week?"


def default_safety(acwr: float = 1.13) -> dict:
    return {
        "load": {"minutes_acwr": acwr},
        "readiness": {"action": "proceed", "reason": "Cleared."},
        "injuries": {"active": [], "has_severe_active": False},
        "max_session_minutes": 180,
        "max_hard_sessions": 2,
        "max_days_per_week": 5,
        "max_weekly_minutes": 400,
        "weekly_minutes_budget": 400,
        "typical_session_minutes": 45,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
    }


def default_context(ftp: int = 232, lthr: int = 168, sleep: int = 85) -> dict:
    return {
        "physiology": {
            "ftp_watts": ftp,
            "lthr_bpm": lthr,
            "max_hr_bpm": 192,
            "resting_hr_bpm": 51,
        },
        "coros": {"latest_health": {"sleep_score": sleep, "hrv": 63}},
        "profile": {
            "primary_goal": "Half marathon under 1:50",
            "sports": [{"sport": "Running", "priority": "primary"}],
            "days_per_week": 5,
            "workout_duration_minutes": 60,
        },
    }


def default_clock() -> dict:
    return {"today": date(2026, 9, 3), "week_start": date(2026, 8, 31)}


def sample_proposed_plan() -> dict:
    return {
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


def sample_diff() -> dict:
    return {
        "changes": [
            {
                "kind": "intensity",
                "date": "2026-09-04",
                "title": "Bike O/U 3×12",
                "summary": "Zone targets updated — under 204–213 W · over 244–267 W",
            }
        ],
        "unchanged_days": 6,
        "same_shape": True,
    }


COACH_CONVERSATION_CASES: list[CoachEvalCase] = [
    CoachEvalCase(
        case_id="replan_same_schedule",
        message=REPLAN_SAME_SCHEDULE_MESSAGE,
        description="Replan with updated zones — action summary, WHAT CHANGED, no triplets",
        expectation=CoachEvalExpectation(
            schedule_mode=ACTION_SUMMARY,
            require_what_changed=True,
            require_zone_mentions=True,
            ban_weekly_translations=True,
            max_triplet_blocks=0,
            max_fk_grade=10.0,
            max_words=280,
        ),
        diversity_runs=5,
    ),
    CoachEvalCase(
        case_id="adjust_week_full",
        message=ADJUST_WEEK_MESSAGE,
        description="Routine schedule adjust — plain voice, readable length",
        expectation=CoachEvalExpectation(
            schedule_mode=FULL_REPORT,
            require_what_changed=False,
            require_zone_mentions=False,
            ban_weekly_translations=True,
            max_triplet_blocks=1,
            max_fk_grade=11.0,
            max_words=320,
        ),
    ),
    CoachEvalCase(
        case_id="why_acwr",
        message=WHY_ACWR_MESSAGE,
        description="Explicit WHY — teaching allowed, still plain language",
        expectation=CoachEvalExpectation(
            schedule_mode=FULL_REPORT,
            require_what_changed=False,
            require_zone_mentions=False,
            ban_weekly_translations=False,
            max_triplet_blocks=2,
            max_fk_grade=12.0,
            max_words=350,
        ),
    ),
    CoachEvalCase(
        case_id="general_pace",
        message=GENERAL_PACE_MESSAGE,
        description="Quick chat — short, no schedule blocks required",
        expectation=CoachEvalExpectation(
            schedule_mode=FULL_REPORT,
            require_what_changed=False,
            require_zone_mentions=False,
            ban_weekly_translations=True,
            max_triplet_blocks=0,
            max_fk_grade=10.0,
            max_words=200,
        ),
    ),
]

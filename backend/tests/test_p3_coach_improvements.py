"""P3: session budget templates, planning notes, data sources."""

from __future__ import annotations

from datetime import date

from app.services.coach_safety import compose_safety_profile
from app.services.coach_templates import build_template_week
from app.services.planning_notes import parse_planning_notes


def _safety_six_by_sixty():
    return compose_safety_profile(
        days_per_week=6,
        session_minutes=60,
        weekly_minutes_budget=360,
        fitness_level="Advanced",
        injuries={
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        readiness_flags=[],
        load={"acute_minutes": 400, "chronic_minutes": 380, "minutes_acwr": 1.05},
        longest_recent_session="3 hours",
    )


def test_template_week_uses_typical_not_equal_split():
    safety = _safety_six_by_sixty()
    context = {
        "profile": {
            "primary_goal": "marathon",
            "sports": [{"sport": "Running", "priority": "primary"}],
        }
    }
    week_start = date(2026, 3, 2)
    plan = build_template_week(context, safety, week_start, today=week_start)
    durations = [workout["duration_min"] for workout in plan["workouts"]]
    assert durations, "expected at least one workout"
    assert max(durations) > 60, "long day should exceed typical weekday length"
    assert any(duration == 60 for duration in durations), "weekdays should use typical length"


def test_parse_planning_notes_travel_warning():
    parsed = parse_planning_notes("Traveling for work next month — mornings only.")
    assert "travel" in parsed["flags"]
    assert "morning_only" in parsed["flags"]
    assert any("travel" in warning.lower() for warning in parsed["warnings"])
    assert parsed["hints"]


def test_parse_planning_notes_empty():
    parsed = parse_planning_notes(None)
    assert parsed["flags"] == []
    assert parsed["warnings"] == []

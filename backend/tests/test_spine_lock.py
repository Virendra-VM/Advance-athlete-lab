"""Tests for orthopedic spine lock validation."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coach_safety import (  # noqa: E402
    has_spine_lock,
    safety_prompt_rules,
    spine_forbidden_hit,
    strip_intensity,
    validate_plan,
)


def _base_safety(**overrides):
    safety = {
        "max_session_minutes": 90,
        "max_hard_sessions": 2,
        "max_weekly_minutes": 400,
        "max_days_per_week": 5,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
        "spine_lock": True,
        "injuries": {
            "active": ["lower back"],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": ["dead bug", "plank"],
            "has_severe_active": False,
        },
        "readiness": {"action": "proceed", "reason": "ok"},
        "load": {"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.1},
    }
    safety.update(overrides)
    return safety


def test_spine_forbidden_detects_deadlift():
    assert spine_forbidden_hit("Back day: 5 x 5 deadlift") == "deadlift"


def test_validate_plan_strips_deadlift_with_spine_lock():
    today = date.today().isoformat()
    safety = _base_safety(
        injuries={
            "active": ["lower back"],
            "past": [],
            "avoid_keywords": ["deadlift"],
            "avoid_session_types": [],
            "prefer": ["dead bug", "plank"],
            "has_severe_active": False,
        }
    )
    plan = {
        "workouts": [
            {
                "date": today,
                "title": "Strength — deadlift focus",
                "session_type": "strength",
                "description": "5 x 5 deadlift and back squat",
                "duration_min": 45,
            }
        ]
    }
    result = validate_plan(plan, safety)
    workout = result["plan"]["workouts"][0]
    assert "deadlift" not in (workout.get("description") or "").lower()
    assert any(issue["code"] in ("spine_lock", "injury_contraindication") for issue in result["issues"])


def test_validate_plan_emits_spine_lock_without_avoid_keywords():
    """Isolate spine_lock from injury_contraindication keyword overlap."""
    today = date.today().isoformat()
    safety = _base_safety()
    plan = {
        "workouts": [
            {
                "date": today,
                "title": "Strength — hinge focus",
                "session_type": "strength",
                "description": "5 x 5 deadlift",
                "duration_min": 45,
            }
        ]
    }
    result = validate_plan(plan, safety)
    codes = {issue["code"] for issue in result["issues"]}
    assert "spine_lock" in codes
    assert "injury_contraindication" not in codes
    workout = result["plan"]["workouts"][0]
    assert "Spine-safe" in (workout.get("intensity") or "")
    assert "lower-back protection" in (workout.get("description") or "").lower()
    assert "deadlift" not in (workout.get("description") or "").lower()


def test_impact_stack_after_heavy_lower():
    day1 = date.today()
    day2 = day1 + timedelta(days=1)
    safety = _base_safety(
        max_session_minutes=120,
        require_rest_day=False,
        load={"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.0},
    )
    plan = {
        "workouts": [
            {
                "date": day1.isoformat(),
                "title": "Lower body strength",
                "session_type": "strength",
                "description": "Bulgarian split squat and RDL",
                "duration_min": 50,
            },
            {
                "date": day2.isoformat(),
                "title": "Hard run intervals",
                "session_type": "intervals",
                "intensity": "Hard",
                "description": "Running track intervals",
                "duration_min": 45,
            },
        ]
    }
    result = validate_plan(plan, safety)
    run_day = result["plan"]["workouts"][1]
    assert run_day["session_type"] == "easy"
    assert has_spine_lock(safety["injuries"])
    assert any(issue["code"] == "spine_impact_stack" for issue in result["issues"])


def test_spine_consecutive_impact_days_blocked():
    day1 = date.today()
    day2 = day1 + timedelta(days=1)
    safety = _base_safety(require_rest_day=False, max_hard_sessions=0)
    plan = {
        "workouts": [
            {
                "date": day1.isoformat(),
                "title": "Easy run",
                "session_type": "easy",
                "description": "Easy running shakeout",
                "duration_min": 40,
            },
            {
                "date": day2.isoformat(),
                "title": "Another easy run",
                "session_type": "easy",
                "description": "Easy running recovery",
                "duration_min": 40,
            },
        ]
    }
    result = validate_plan(plan, safety)
    assert any(issue["code"] == "spine_consecutive_impact" for issue in result["issues"])
    assert result["plan"]["workouts"][1]["session_type"] == "easy"


def test_validate_plan_session_too_long_and_weekly_volume():
    day = date.today()
    safety = _base_safety(
        spine_lock=False,
        injuries={
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        max_session_minutes=60,
        max_weekly_minutes=100,
        require_rest_day=False,
        no_consecutive_hard_days=False,
        max_hard_sessions=3,
    )
    plan = {
        "workouts": [
            {
                "date": day.isoformat(),
                "title": "Long ride",
                "session_type": "endurance",
                "duration_min": 180,
            },
            {
                "date": (day + timedelta(days=1)).isoformat(),
                "title": "Another long ride",
                "session_type": "endurance",
                "duration_min": 120,
            },
        ]
    }
    result = validate_plan(plan, safety)
    codes = {issue["code"] for issue in result["issues"]}
    assert "session_too_long" in codes
    assert "weekly_volume_exceeded" in codes
    # Ceiling trims 180→60, then weekly scale shrinks further under the load cap.
    assert result["plan"]["workouts"][0]["duration_min"] <= 60
    assert sum(w["duration_min"] for w in result["plan"]["workouts"]) <= 100


def test_validate_plan_readiness_override_and_empty_plan():
    today = date.today().isoformat()
    safety = _base_safety(
        spine_lock=False,
        injuries={
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        readiness={
            "action": "rest_or_mobility",
            "reason": "Two or more recovery markers are poor.",
        },
        max_hard_sessions=2,
    )
    result = validate_plan(
        {
            "workouts": [
                {
                    "date": today,
                    "title": "VO2 intervals",
                    "session_type": "intervals",
                    "intensity": "Hard",
                    "duration_min": 50,
                }
            ]
        },
        safety,
    )
    assert any(issue["code"] == "readiness_override" for issue in result["issues"])
    assert result["plan"]["workouts"][0]["session_type"] == "rest"

    empty = validate_plan({"workouts": []}, safety)
    assert empty["blocked"] is True
    assert any(issue["code"] == "empty_plan" for issue in empty["issues"])


def test_validate_plan_blocks_severe_active_injury():
    today = date.today().isoformat()
    safety = _base_safety(
        spine_lock=False,
        max_hard_sessions=2,
        injuries={
            "active": ["achilles (rupture risk)"],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": ["cycling"],
            "has_severe_active": True,
        },
    )
    result = validate_plan(
        {
            "workouts": [
                {
                    "date": today,
                    "title": "Track intervals",
                    "session_type": "intervals",
                    "intensity": "Hard",
                    "duration_min": 45,
                }
            ]
        },
        safety,
    )
    assert result["blocked"] is True
    assert any(issue["code"] == "severe_active_injury" for issue in result["issues"])


def test_strip_intensity_and_safety_prompt_rules():
    stripped = strip_intensity(
        {
            "workouts": [
                {"title": "Intervals", "session_type": "intervals", "intensity": "Hard"},
                {"title": "Off", "session_type": "rest", "intensity": "Recovery"},
            ]
        }
    )
    assert stripped["workouts"][0]["session_type"] == "easy"
    assert stripped["workouts"][1]["session_type"] == "rest"

    safety = _base_safety(
        typical_session_minutes=60,
        readiness={
            "action": "downgrade_to_easy",
            "reason": "One recovery marker is poor: poor sleep.",
        },
        season_phase="build",
        long_session_allowed_min=180,
        todays_call={
            "call_level": "easy",
            "label": "🟡 EASY",
            "directive": "Keep today conversational.",
        },
    )
    rules = safety_prompt_rules(safety, weekday_index=4)
    assert "SPINE LOCK" in rules
    assert "Adjust remaining sessions" in rules
    assert "Season phase: build" in rules
    assert "Today's Call" in rules

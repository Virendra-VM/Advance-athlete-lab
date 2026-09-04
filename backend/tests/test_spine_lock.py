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
    spine_forbidden_hit,
    validate_plan,
)


def test_spine_forbidden_detects_deadlift():
    assert spine_forbidden_hit("Back day: 5 x 5 deadlift") == "deadlift"


def test_validate_plan_strips_deadlift_with_spine_lock():
    today = date.today().isoformat()
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
            "avoid_keywords": ["deadlift"],
            "avoid_session_types": [],
            "prefer": ["dead bug", "plank"],
            "has_severe_active": False,
        },
        "readiness": {"action": "proceed", "reason": "ok"},
        "load": {"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.1},
    }
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


def test_impact_stack_after_heavy_lower():
    day1 = date.today()
    day2 = day1 + timedelta(days=1)
    safety = {
        "max_session_minutes": 120,
        "max_hard_sessions": 2,
        "max_weekly_minutes": 400,
        "max_days_per_week": 5,
        "require_rest_day": False,
        "no_consecutive_hard_days": True,
        "spine_lock": True,
        "injuries": {
            "active": ["lower back"],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": ["plank"],
            "has_severe_active": False,
        },
        "readiness": {"action": "proceed", "reason": "ok"},
        "load": {"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.0},
    }
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

"""Tests for daily autoregulation engine."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.autoregulation import resolve_todays_call  # noqa: E402
from app.services.biometric_baselines import hrv_delta_pct  # noqa: E402


def test_hrv_delta_pct_vs_baseline():
    assert hrv_delta_pct(46.5, 50.0) == -7.0
    assert hrv_delta_pct(42.5, 50.0) == -15.0


def test_readiness_85_allows_hard():
    result = resolve_todays_call(
        readiness_score=88,
        hrv=55,
        hrv_baseline=50,
        sleep_hours=7.5,
        acwr=1.0,
    )
    assert result["call_level"] == "hard"
    assert result["base_level"] == "hard"


def test_hrv_minus_7_downgrades_one_tier():
    result = resolve_todays_call(
        readiness_score=88,
        hrv=46.5,
        hrv_baseline=50.0,
        sleep_hours=7.5,
        acwr=1.0,
    )
    assert result["call_level"] == "moderate"
    assert any("HRV" in reason for reason in result["downgrade_reasons"])


def test_acwr_16_forces_rest():
    result = resolve_todays_call(
        readiness_score=90,
        hrv=55,
        hrv_baseline=50,
        sleep_hours=8,
        acwr=1.6,
    )
    assert result["call_level"] == "rest"
    assert any("ACWR" in reason for reason in result["downgrade_reasons"])


def test_sleep_debt_warning():
    result = resolve_todays_call(
        readiness_score=70,
        hrv=50,
        hrv_baseline=50,
        sleep_hours=6.5,
        acwr=1.0,
        recent_sleep=[6.0, 6.5, 8.0],
    )
    codes = {warning["code"] for warning in result["warnings"]}
    assert "sleep_debt" in codes


def test_validate_plan_vetoes_hard_on_rest_day():
    from app.services.coach_safety import validate_plan  # noqa: WPS433

    today = date.today().isoformat()
    safety = {
        "max_session_minutes": 120,
        "max_hard_sessions": 0,
        "max_weekly_minutes": 400,
        "max_days_per_week": 5,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
        "injuries": {
            "active": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        "readiness": {"action": "rest_or_mobility", "reason": "REST day"},
        "load": {"acute_minutes": 300, "chronic_minutes": 250, "minutes_acwr": 1.6},
        "autoregulation": {
            "call_level": "rest",
            "label": "🔴 REST / RESTORE",
            "directive": "Restore first",
        },
    }
    plan = {
        "workouts": [
            {
                "date": today,
                "title": "VO2 intervals",
                "session_type": "intervals",
                "intensity": "Hard",
                "duration_min": 60,
            }
        ]
    }
    result = validate_plan(plan, safety)
    workout = result["plan"]["workouts"][0]
    assert workout["session_type"] in ("rest", "easy")
    assert any(
        issue["code"] in ("autoregulation_veto", "acwr_veto", "too_many_hard_sessions")
        for issue in result["issues"]
    )

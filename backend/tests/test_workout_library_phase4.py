"""Phase 4 — persistence, favorites, repeat, autopsy overlay."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai_coach import autopsy_task_for_packet  # noqa: E402
from app.services.coach_ai import (  # noqa: E402
    _compliance_payload,
    _load_compliance,
    _persist_plan,
    add_favorite_template,
    list_favorite_templates,
    remove_favorite_template,
    repeat_planned_workout,
)
from app.services.session_plan import build_session_plan_overlay, match_week_plan_session  # noqa: E402
from app.services.workout_selection import build_library_week  # noqa: E402


def _memory_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _safety():
    from app.services.coach_safety import compose_safety_profile

    return compose_safety_profile(
        days_per_week=4,
        session_minutes=50,
        weekly_minutes_budget=200,
        fitness_level="Intermediate",
        injuries={
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        readiness_flags=[],
        load={"acute_minutes": 200, "chronic_minutes": 200, "minutes_acwr": 1.0},
    )


def _profile(db):
    from app.models import AthleteProfile

    profile = AthleteProfile(
        name="Phase4",
        age=32,
        weight=70.0,
        ftp_watts=250,
        lthr_bpm=170,
        days_per_week=4,
        workout_duration_minutes=50,
        onboarding_completed=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_persist_plan_stores_library_template_id():
    db = _memory_db()
    profile = _profile(db)
    week_start = date.today() - timedelta(days=date.today().weekday())
    safety = _safety()
    context = {
        "profile": {"primary_sports": ["running"], "days_per_week": 4},
        "season": {"phase_type": "build"},
    }
    plan = build_library_week(context, safety, week_start)
    plan_id = _persist_plan(
        db,
        profile,
        plan,
        week_start,
        provider="test",
        model="test",
        issues=[],
        citations=[],
        safety=safety,
        physiology={"ftp_watts": 250, "lthr_bpm": 170},
    )
    from app.models import PlannedWorkout

    rows = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.training_plan_id == plan_id)
        .all()
    )
    assert rows
    assert all(row.library_template_id for row in rows)
    assert all(row.library_version for row in rows)
    db.close()


def test_favorite_template_round_trip():
    db = _memory_db()
    profile = _profile(db)
    add_favorite_template(db, profile.id, "run_easy_z2")
    favorites = list_favorite_templates(db, profile.id)
    assert len(favorites) == 1
    assert favorites[0]["template_id"] == "run_easy_z2"
    remove_favorite_template(db, profile.id, "run_easy_z2")
    assert list_favorite_templates(db, profile.id) == []
    db.close()


def test_repeat_planned_workout():
    db = _memory_db()
    profile = _profile(db)
    week_start = date.today() - timedelta(days=date.today().weekday())
    safety = _safety()
    context = {
        "profile": {"primary_sports": ["running"], "days_per_week": 3},
        "season": {"phase_type": "base"},
    }
    plan = build_library_week(context, safety, week_start)
    plan_id = _persist_plan(
        db,
        profile,
        plan,
        week_start,
        provider="test",
        model="test",
        issues=[],
        citations=[],
        safety=safety,
        physiology={"lthr_bpm": 170},
    )
    from app.models import PlannedWorkout

    source = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.training_plan_id == plan_id)
        .first()
    )
    target = week_start + timedelta(days=14)
    result = repeat_planned_workout(
        db,
        profile,
        source.id,
        target_date=target,
    )
    assert result["workout_id"]
    assert result["library_template_id"] == source.library_template_id
    repeated = db.get(PlannedWorkout, result["workout_id"])
    assert repeated.workout_date == target
    db.close()


def test_library_overlay_in_session_plan():
    week_plan = {
        "plan": {
            "workouts": [
                {
                    "date": "2026-09-10",
                    "sport": "Running",
                    "title": "Threshold repeats",
                    "session_type": "threshold",
                    "duration_min": 50,
                    "library_template_id": "run_threshold_2x10_lthr1",
                }
            ]
        }
    }
    session = match_week_plan_session(week_plan, "2026-09-10", "run")
    assert session["library_template_id"] == "run_threshold_2x10_lthr1"
    overlay = build_session_plan_overlay(
        message="how did my threshold run go?",
        history=[],
        laps=[],
        ftp=None,
        week_plan=week_plan,
        session_date="2026-09-10",
        family="run",
        physiology={"lthr_bpm": 170, "threshold_pace_sec_per_km": 300},
        telemetry={"minutes": 49, "heart_rate": {"avg_bpm": 167}},
    )
    assert overlay["prescription"]["source"] == "library_template"
    assert overlay["library_compliance"]["score"] >= 50


def test_autopsy_task_mentions_library_compliance():
    task = autopsy_task_for_packet(
        "run",
        {
            "prescription": {"source": "library_template", "template_id": "run_threshold_2x10_lthr1"},
            "library_compliance": {"score": 88, "grade": "B"},
            "week_plan_session": {"date": "2026-09-10", "title": "Threshold"},
        },
    )
    lower = task.lower()
    assert "library" in lower
    assert "lthr" in lower or "ftp" in lower


def test_compliance_json_helpers():
    payload = _compliance_payload({"score": 84.5, "grade": "B", "dimensions": {"duration": 90}})
    assert payload
    loaded = _load_compliance(payload)
    assert loaded["grade"] == "B"
    assert loaded["dimensions"]["duration"] == 90

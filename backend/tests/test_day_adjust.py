"""Today-only health adjustments must not rewrite the rest of the week."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import AthleteProfile, PlannedWorkout, TrainingPlan  # noqa: E402
from app.services.coach_ai import persist_today_adjustment  # noqa: E402


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_persist_today_adjustment_leaves_other_days():
    db = _db()
    try:
        profile = AthleteProfile(
            name="Day Adjust", age=34, weight=70.0, onboarding_completed=True
        )
        db.add(profile)
        db.flush()
        today = date(2026, 9, 9)
        week_start = date(2026, 9, 7)
        plan = TrainingPlan(
            athlete_profile_id=profile.id,
            week_start=week_start,
            title="Test week",
            status="active",
        )
        db.add(plan)
        db.flush()
        today_row = PlannedWorkout(
            training_plan_id=plan.id,
            athlete_profile_id=profile.id,
            workout_date=today,
            title="Wednesday threshold",
            session_type="threshold",
            intensity="Hard",
            sport="Cycling",
            duration_min=60,
        )
        friday = PlannedWorkout(
            training_plan_id=plan.id,
            athlete_profile_id=profile.id,
            workout_date=date(2026, 9, 11),
            title="Friday intervals",
            session_type="intervals",
            intensity="Hard",
            sport="Running",
            duration_min=50,
        )
        db.add_all([today_row, friday])
        db.commit()

        safety = {
            "readiness": {"action": "downgrade_to_easy", "reason": "HRV suppressed"},
            "todays_call": {"call_level": "easy"},
            "spine_lock": False,
            "disclaimer": "Training guidance only",
            "max_session_minutes": 180,
            "max_hard_sessions": 2,
            "max_days_per_week": 5,
            "typical_session_minutes": 45,
            "require_rest_day": True,
            "no_consecutive_hard_days": True,
            "injuries": {
                "active": [],
                "avoid_keywords": [],
                "avoid_session_types": [],
                "prefer": [],
                "has_severe_active": False,
            },
            "load": {},
        }
        persist_today_adjustment(
            db,
            profile,
            today=today,
            week_start=week_start,
            plan_data=None,
            safety=safety,
            hits=[],
            provider="rules",
            model="test",
        )
        rows = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.training_plan_id == plan.id)
            .order_by(PlannedWorkout.workout_date.asc())
            .all()
        )
        by_date = {row.workout_date: row for row in rows}
        assert by_date[today].session_type == "easy"
        assert by_date[today].duration_min == 60
        assert by_date[date(2026, 9, 11)].title == "Friday intervals"
        assert by_date[date(2026, 9, 11)].session_type == "intervals"
        assert db.query(TrainingPlan).filter(TrainingPlan.id == plan.id).one().status == "active"
    finally:
        db.close()

"""Clinical veto: no meds, flag the tissue, convert remaining quality."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import AthleteInjury, AthleteProfile, PlannedWorkout, TrainingPlan  # noqa: E402
from app.services.ai_coach import template_clinical_veto, template_off_topic  # noqa: E402
from app.services.coach_safety import (  # noqa: E402
    apply_joint_safe_recovery_mode,
    detect_clinical_boundary,
    detect_red_flags,
    flag_clinical_injury,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_tendon_pain_is_clinical_not_emergency():
    message = "I have sharp pain in my tendon when running"
    assert not detect_red_flags(message)
    hit = detect_clinical_boundary(message)
    assert hit is not None
    assert hit["kind"] == "tissue_pain"
    assert hit["region"] in {"tendon", "achilles"}


def test_ibuprofen_is_clinical_medication():
    hit = detect_clinical_boundary("I have sharp knee pain, should I take ibuprofen?")
    assert hit is not None
    assert "medication" in hit["hits"]
    assert hit["region"] == "knee"


def test_chest_pain_stays_emergency_red_flag():
    assert detect_red_flags("I have chest pain when I ride")
    # Red-flag gate runs first in chat; clinical may also match but emergency wins.


def test_clinical_template_refers_and_refuses_meds():
    reply = template_clinical_veto(
        "sharp tendon pain",
        region="tendon",
        kind="tissue_pain",
        plan_changes=["2026-09-10: Threshold run → Joint-safe active recovery"],
    )
    text = reply["reply"]
    assert "CLINICAL VETO" in text
    assert "physical therapist" in text.lower() or "physician" in text.lower()
    assert "ibuprofen" in text.lower() or "NSAID" in text
    assert reply["escalate"] is True
    assert "Joint-safe" in text


def test_off_topic_template_rebricks_to_training():
    reply = template_off_topic("What stock should I buy?")
    assert reply["intent"] == "OFF_TOPIC"
    assert "athletic performance" in reply["reply"].lower()
    assert "stock" in reply["reply"].lower()


def test_joint_safe_mode_converts_remaining_quality():
    db = _db()
    try:
        profile = AthleteProfile(
            name="Veto Tester", age=34, weight=70.0, onboarding_completed=True
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
        past = PlannedWorkout(
            training_plan_id=plan.id,
            athlete_profile_id=profile.id,
            workout_date=week_start,
            title="Monday intervals",
            session_type="intervals",
            intensity="hard",
            sport="Run",
        )
        future = PlannedWorkout(
            training_plan_id=plan.id,
            athlete_profile_id=profile.id,
            workout_date=today + timedelta(days=1),
            title="Thursday threshold",
            session_type="threshold",
            intensity="hard",
            sport="Run",
        )
        db.add_all([past, future])
        db.flush()
        flag_clinical_injury(db, profile.id, "sharp tendon pain", region="tendon")
        changes = apply_joint_safe_recovery_mode(
            db, profile.id, today=today, week_start=week_start, region="tendon"
        )
        db.commit()
        db.refresh(past)
        db.refresh(future)
        assert past.session_type == "intervals"
        assert future.session_type == "mobility"
        assert future.title == "Joint-safe active recovery"
        assert changes
        injuries = db.query(AthleteInjury).filter_by(athlete_profile_id=profile.id).all()
        assert any(row.status == "active" and row.body_region == "tendon" for row in injuries)
    finally:
        db.close()


def run() -> None:
    tests = [
        test_tendon_pain_is_clinical_not_emergency,
        test_ibuprofen_is_clinical_medication,
        test_chest_pain_stays_emergency_red_flag,
        test_clinical_template_refers_and_refuses_meds,
        test_off_topic_template_rebricks_to_training,
        test_joint_safe_mode_converts_remaining_quality,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

"""Clinical veto: no meds, flag the tissue, convert remaining quality."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    compose_safety_profile,
    detect_clinical_boundary,
    detect_red_flags,
    flag_clinical_injury,
    injury_constraints_from_records,
    readiness_directive,
    readiness_flags_from_signals,
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


@pytest.mark.parametrize(
    "message,needle",
    [
        ("I fainted after the intervals", "faint"),
        ("I have numbness in my left foot", "numb"),
        ("Woke up with a fever this morning", "fever"),
        ("Coach I think I have a stress fracture", "stress fracture"),
        ("I heard an audible pop in my knee", "audible pop"),
    ],
)
def test_red_flag_matrix_catches_emergencies(message, needle):
    hits = detect_red_flags(message)
    assert hits
    assert any(needle in hit.lower() for hit in hits)


def test_diagnosis_request_is_clinical_boundary():
    hit = detect_clinical_boundary("Do I have a tear in my knee from yesterday?")
    assert hit is not None
    assert hit["kind"] == "diagnosis_request"
    assert "diagnosis request" in hit["hits"]
    assert hit["region"] == "knee"


def test_medication_only_message_is_medication_kind():
    hit = detect_clinical_boundary("Should I take ibuprofen after hard sessions?")
    assert hit is not None
    assert hit["kind"] == "medication"
    assert "medication" in hit["hits"]


def test_clinical_template_medication_and_empty_plan_lock():
    reply = template_clinical_veto(
        "should I take ibuprofen?",
        region="knee",
        kind="medication",
        plan_changes=[],
    )
    text = reply["reply"]
    assert "Medication is a clinician's call" in text
    assert "Remaining quality this week is locked" in text
    assert reply["escalate"] is True
    assert reply["intent"] == "CLINICAL_VETO"


def test_flag_clinical_injury_updates_existing_row():
    db = _db()
    try:
        profile = AthleteProfile(
            name="Upsert Tester", age=30, weight=68.0, onboarding_completed=True
        )
        db.add(profile)
        db.flush()
        first = flag_clinical_injury(db, profile.id, "sharp knee pain on stairs", region="knee")
        second = flag_clinical_injury(
            db, profile.id, "still sharp knee pain after easy jog", region="knee"
        )
        db.commit()
        assert first.id == second.id
        assert second.notes == "still sharp knee pain after easy jog"
        rows = (
            db.query(AthleteInjury)
            .filter_by(athlete_profile_id=profile.id, body_region="knee", status="active")
            .all()
        )
        assert len(rows) == 1
    finally:
        db.close()


def test_injury_constraints_from_records_merge_rules():
    rows = [
        SimpleNamespace(
            body_region="knee",
            condition="runner's knee",
            status="active",
            severity="moderate",
        ),
        SimpleNamespace(
            body_region="achilles",
            condition="tendinopathy",
            status="active",
            severity="severe",
        ),
        SimpleNamespace(
            body_region="shoulder",
            condition="old impingement",
            status="resolved",
            severity="mild",
        ),
    ]
    constraints = injury_constraints_from_records(rows)
    assert any("knee" in item for item in constraints["active"])
    assert any("achilles" in item for item in constraints["active"])
    assert any("shoulder" in item for item in constraints["past"])
    assert "plyometric" in constraints["avoid_keywords"]
    assert "intervals" in constraints["avoid_session_types"]
    assert constraints["has_severe_active"] is True


def test_readiness_flags_and_directive_thresholds():
    flags = readiness_flags_from_signals(
        recovery_pct=35,
        sleep_score=50,
        stress=80,
        hrv=42,
        hrv_assessment="Unbalanced",
        load_ratio=1.6,
    )
    assert "low_recovery" in flags
    assert "poor_sleep" in flags
    assert "elevated_stress" in flags
    assert "hrv_unbalanced" in flags
    assert "high_training_load_ratio" in flags

    rest = readiness_directive(["poor_sleep", "low_recovery"])
    assert rest["action"] == "rest_or_mobility"
    assert rest["max_hard_sessions_today"] == 0

    easy = readiness_directive(["elevated_stress"])
    assert easy["action"] == "downgrade_to_easy"

    ok = readiness_directive(["good_recovery"])
    assert ok["action"] == "proceed"


def test_compose_safety_profile_severe_and_spine_lock():
    injuries = {
        "active": ["lower back (disc)"],
        "past": [],
        "avoid_keywords": ["deadlift"],
        "avoid_session_types": [],
        "prefer": ["plank"],
        "has_severe_active": True,
    }
    profile = compose_safety_profile(
        days_per_week=5,
        session_minutes=60,
        weekly_minutes_budget=300,
        fitness_level="intermediate",
        injuries=injuries,
        readiness_flags=["good_recovery"],
        load={"acute_minutes": 200, "chronic_minutes": 180, "minutes_acwr": 1.1},
    )
    assert profile["max_hard_sessions"] == 0
    assert profile["spine_lock"] is True
    assert profile["readiness"]["action"] == "proceed"


def run() -> None:
    tests = [
        test_tendon_pain_is_clinical_not_emergency,
        test_ibuprofen_is_clinical_medication,
        test_chest_pain_stays_emergency_red_flag,
        test_clinical_template_refers_and_refuses_meds,
        test_off_topic_template_rebricks_to_training,
        test_joint_safe_mode_converts_remaining_quality,
        test_diagnosis_request_is_clinical_boundary,
        test_medication_only_message_is_medication_kind,
        test_clinical_template_medication_and_empty_plan_lock,
        test_flag_clinical_injury_updates_existing_row,
        test_injury_constraints_from_records_merge_rules,
        test_readiness_flags_and_directive_thresholds,
        test_compose_safety_profile_severe_and_spine_lock,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

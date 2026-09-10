"""Phase C — physiology estimate from activities tests."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import Activity, AthleteProfile, DailyHealthMetric, FitnessAssessment  # noqa: E402
from app.services.physiology_estimate import (  # noqa: E402
    apply_physiology_estimate,
    build_physiology_estimate,
)
from app.services.workout_library import physiology_from_profile  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    profile = AthleteProfile(name="Estimate Tester", age=35, weight=70.0)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    yield session, profile
    session.close()


def test_build_estimate_from_coros_and_age(db_session):
    db, profile = db_session
    db.add(
        FitnessAssessment(
            athlete_profile_id=profile.id,
            provider="coros",
            snapshot_at=datetime.utcnow(),
            vo2max=49.0,
            threshold_pace="4:20/km",
        )
    )
    db.add(
        DailyHealthMetric(
            athlete_profile_id=profile.id,
            provider="coros",
            metric_date=datetime.utcnow().date(),
            resting_heart_rate=52,
        )
    )
    db.commit()

    preview = build_physiology_estimate(db, profile)
    assert preview["suggestions"]["vo2max"] == 49.0
    assert preview["suggestions"]["threshold_pace_sec_per_km"] == 260
    assert preview["suggestions"]["resting_hr_bpm"] == 52
    assert preview["suggestions"]["max_hr_bpm"] == 185
    assert preview["sources"]["vo2max"] == "coros_fitness"


def test_apply_estimate_only_fills_empty_fields(db_session):
    db, profile = db_session
    profile.lthr_bpm = 168.0
    db.add(
        FitnessAssessment(
            athlete_profile_id=profile.id,
            provider="coros",
            snapshot_at=datetime.utcnow(),
            vo2max=50.0,
            threshold_pace="4:25/km",
        )
    )
    db.commit()

    result = apply_physiology_estimate(db, profile)
    assert profile.lthr_bpm == 168.0
    assert "lthr_bpm" not in result["applied"]
    assert result["applied"]["vo2max"] == 50.0
    assert result["applied"]["threshold_pace_sec_per_km"] == 265
    assert "lthr_bpm" in result["skipped"]


def test_apply_estimate_produces_zones(db_session):
    db, profile = db_session
    db.add(
        FitnessAssessment(
            athlete_profile_id=profile.id,
            provider="coros",
            snapshot_at=datetime.utcnow(),
            threshold_pace="4:30/km",
        )
    )
    db.commit()

    apply_physiology_estimate(db, profile)
    physiology = physiology_from_profile(profile)
    assert physiology["run_pace_zones"]
    assert physiology["anchors"]["threshold_pace_sec_per_km"] == 270


def test_onboarding_payload_parses_pace_fields():
    from app.auth_schemas import OnboardingSubmitRequest
    from app.services.athlete_profile import apply_physiology_updates

    profile = SimpleNamespace(
        threshold_pace_sec_per_km=None,
        css_sec_per_100m=None,
        zone_run_hr_method="lthr",
    )
    payload = OnboardingSubmitRequest(
        primary_goal="Half marathon",
        equipment="Road bike",
        days_per_week=4,
        workout_duration_minutes=60,
        preferred_workout_time="Morning",
        fitness_level="Intermediate",
        threshold_pace="4:40/km",
        css_pace="1:40/100m",
        zone_run_hr_method="hrr",
    )
    updates = payload.model_dump(exclude_unset=True)
    apply_physiology_updates(profile, updates)
    assert profile.threshold_pace_sec_per_km == 280
    assert profile.css_sec_per_100m == 100
    assert profile.zone_run_hr_method == "hrr"

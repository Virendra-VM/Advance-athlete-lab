"""Phase D — smarter defaults, test detection, and race pace updates."""

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
from app.models import Activity, AthleteEvent, AthleteProfile  # noqa: E402
from app.services.b_race_calibration import complete_b_race_event  # noqa: E402
from app.services.physiology_estimate import apply_test_suggestion, build_physiology_estimate  # noqa: E402
from app.services.test_activity_detection import (  # noqa: E402
    detect_ftp_test,
    detect_lthr_test,
    detect_race_threshold_pace,
    detect_test_suggestions,
    threshold_pace_from_race,
)
from app.services.zone_engine import build_anchor_nudges, resolve_effective_hr_method  # noqa: E402
from app.services.zone_recalibration import complete_d_race_event  # noqa: E402


def _activity(**kwargs):
    defaults = {
        "id": 1,
        "athlete_profile_id": 1,
        "provider": "strava",
        "external_activity_id": "1",
        "name": "Run",
        "activity_date": datetime.utcnow(),
        "distance_m": 0.0,
        "moving_time_s": 0,
        "source_fit_file": "test.fit",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_resolve_effective_hr_method_falls_back_to_max_hr():
    profile = SimpleNamespace(lthr_bpm=None, max_hr_bpm=190, zone_run_hr_method="lthr")
    assert resolve_effective_hr_method(profile) == "max_hr"


def test_build_anchor_nudges_for_estimated_lthr():
    profile = SimpleNamespace(
        lthr_bpm=None,
        max_hr_bpm=190,
        ftp_watts=None,
        threshold_pace_sec_per_km=None,
        zone_run_hr_method="lthr",
    )
    nudges = build_anchor_nudges(profile, {"lthr_source": "estimated_from_max_hr", "ftp_source": "estimated"})
    codes = {row["code"] for row in nudges}
    assert "confirm_lthr_test" in codes
    assert "confirm_ftp_test" in codes
    assert "add_threshold_pace" in codes


def test_detect_lthr_test_from_20_min_run():
    activity = _activity(
        name="20 min threshold test",
        sport_type="Run",
        moving_time_s=20 * 60,
        average_heartrate=172,
    )
    hit = detect_lthr_test(activity)
    assert hit is not None
    assert hit["field"] == "lthr_bpm"
    assert hit["value"] == 172
    assert hit["confidence"] == "high"


def test_detect_race_threshold_pace_from_10k():
    activity = _activity(
        name="City 10K",
        sport_type="Run",
        distance_m=10000,
        moving_time_s=46 * 60,
    )
    hit = detect_race_threshold_pace(activity)
    assert hit is not None
    assert hit["field"] == "threshold_pace_sec_per_km"
    assert hit["value"] > 250


def test_threshold_pace_from_race_distance():
    pace = threshold_pace_from_race(10000, 46 * 60)
    assert pace == pytest.approx(285.5, rel=0.01)


def test_detect_test_suggestions_picks_best_per_field():
    activities = [
        _activity(
            id=1,
            name="Easy run",
            sport_type="Run",
            moving_time_s=20 * 60,
            average_heartrate=168,
        ),
        _activity(
            id=2,
            name="20 min LTHR test",
            sport_type="Run",
            moving_time_s=20 * 60,
            average_heartrate=174,
        ),
    ]
    hits = detect_test_suggestions(activities)
    lthr = next(row for row in hits if row["field"] == "lthr_bpm")
    assert lthr["value"] == 174


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    profile = AthleteProfile(name="Phase D", age=35, weight=70.0)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    yield session, profile
    session.close()


def test_build_estimate_includes_test_suggestions(db_session):
    db, profile = db_session
    db.add(
        Activity(
            athlete_profile_id=profile.id,
            provider="strava",
            external_activity_id="run-1",
            name="20 min threshold",
            activity_date=datetime.utcnow(),
            distance_m=6000,
            moving_time_s=20 * 60,
            average_heartrate=171,
            sport_type="Run",
            source_fit_file="run.fit",
        )
    )
    db.commit()
    preview = build_physiology_estimate(db, profile)
    assert preview["test_suggestions"]
    assert preview["nudges"]
    assert preview["suggestions"].get("lthr_bpm") == 171


def test_apply_test_suggestion(db_session):
    db, profile = db_session
    db.add(
        Activity(
            athlete_profile_id=profile.id,
            provider="strava",
            external_activity_id="run-2",
            name="Threshold test",
            activity_date=datetime.utcnow(),
            distance_m=7000,
            moving_time_s=20 * 60,
            average_heartrate=173,
            sport_type="Run",
            source_fit_file="run.fit",
        )
    )
    db.commit()
    preview = build_physiology_estimate(db, profile)
    suggestion_id = preview["test_suggestions"][0]["id"]
    result = apply_test_suggestion(db, profile, suggestion_id)
    assert profile.lthr_bpm == 173
    assert result["applied"]["lthr_bpm"] == 173


def test_complete_d_race_sets_threshold_pace_from_result(db_session):
    db, profile = db_session
    event = AthleteEvent(
        athlete_profile_id=profile.id,
        name="10K TT",
        event_date=datetime.utcnow().date(),
        priority="D",
        sport_type="run",
        status="planned",
        target_metric="46:00",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    result = complete_d_race_event(
        db,
        profile,
        event,
        result_metric="46:00",
    )
    assert profile.threshold_pace_sec_per_km is not None
    assert "threshold_pace_sec_per_km" in result["zones_updated"]


def test_complete_b_race_sets_threshold_pace_when_empty(db_session):
    db, profile = db_session
    event = AthleteEvent(
        athlete_profile_id=profile.id,
        name="Tune-up 10K",
        event_date=datetime.utcnow().date(),
        priority="B",
        sport_type="run",
        status="planned",
        target_metric="45:30",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    result = complete_b_race_event(db, profile, event, result_metric="45:30")
    assert profile.threshold_pace_sec_per_km is not None
    assert result["zones_updated"]["threshold_pace_sec_per_km"] > 0

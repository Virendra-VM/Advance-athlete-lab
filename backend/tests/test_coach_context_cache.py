"""Phase D — athlete coach context cache tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Activity, AthleteProfile
from app.services.coach_context_cache import (
    cache_stats,
    context_fingerprint,
    get_athlete_coach_context,
    invalidate_coach_context_cache,
)


@pytest.fixture(autouse=True)
def clear_context_cache():
    invalidate_coach_context_cache(None)
    yield
    invalidate_coach_context_cache(None)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _profile(db) -> AthleteProfile:
    profile = AthleteProfile(name="Cache Test", age=30, weight=68.0, primary_goal="5K")
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_context_cache_hit_on_second_call(db_session):
    profile = _profile(db_session)
    built = {"athlete_profile_id": profile.id, "generated_at": datetime.utcnow(), "profile": {}}

    with patch(
        "app.services.coach_context_cache.build_athlete_coach_context",
        return_value=built,
    ) as builder:
        first = get_athlete_coach_context(db_session, profile.id)
        second = get_athlete_coach_context(db_session, profile.id)

    assert builder.call_count == 1
    assert first["_cache"]["hit"] is False
    assert second["_cache"]["hit"] is True


def test_invalidate_forces_rebuild(db_session):
    profile = _profile(db_session)
    built = {"athlete_profile_id": profile.id, "generated_at": datetime.utcnow(), "profile": {}}

    with patch(
        "app.services.coach_context_cache.build_athlete_coach_context",
        return_value=built,
    ) as builder:
        get_athlete_coach_context(db_session, profile.id)
        invalidate_coach_context_cache(profile.id)
        get_athlete_coach_context(db_session, profile.id)

    assert builder.call_count == 2


def test_fingerprint_changes_when_activity_added(db_session):
    profile = _profile(db_session)
    before = context_fingerprint(db_session, profile.id)
    db_session.add(
        Activity(
            athlete_profile_id=profile.id,
            provider="strava",
            external_activity_id="123",
            name="Morning Run",
            activity_date=datetime.utcnow(),
            moving_time_s=3600,
            distance_m=10000,
            source_fit_file="",
        )
    )
    db_session.commit()
    after = context_fingerprint(db_session, profile.id)
    assert before != after


def test_cache_stats_after_populate(db_session):
    profile = _profile(db_session)
    built = {"athlete_profile_id": profile.id, "generated_at": datetime.utcnow(), "profile": {}}
    with patch(
        "app.services.coach_context_cache.build_athlete_coach_context",
        return_value=built,
    ):
        get_athlete_coach_context(db_session, profile.id)
    stats = cache_stats(profile.id)
    assert stats["cached"] is True
    assert stats["expires_in_seconds"] >= 0

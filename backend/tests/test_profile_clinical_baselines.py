"""Profile storage for arterial occlusion pressure and basal temperature."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth_schemas import AthleteProfileResponse, ProfileUpdateRequest
from app.database import Base
from app.models import AthleteProfile


def _apply_scalar_updates(profile: AthleteProfile, updates: dict) -> None:
    """Same scalar write the profile route uses for these two columns."""
    for field in ("aop_mmhg", "basal_body_temp_c"):
        if field in updates:
            setattr(profile, field, updates[field])


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


def test_model_columns_exist():
    columns = set(AthleteProfile.__table__.columns.keys())
    assert "aop_mmhg" in columns
    assert "basal_body_temp_c" in columns
    auth_source = (Path(__file__).resolve().parents[1] / "app" / "routes" / "auth.py").read_text(
        encoding="utf-8"
    )
    assert '"aop_mmhg"' in auth_source
    assert '"basal_body_temp_c"' in auth_source


def test_profile_update_accepts_baselines_and_rejects_unsafe_ranges():
    payload = ProfileUpdateRequest(aop_mmhg=180, basal_body_temp_c=36.6)
    assert payload.aop_mmhg == 180
    assert payload.basal_body_temp_c == 36.6

    ProfileUpdateRequest(aop_mmhg=80, basal_body_temp_c=35.0)
    ProfileUpdateRequest(aop_mmhg=350, basal_body_temp_c=38.5)
    ProfileUpdateRequest(aop_mmhg=None, basal_body_temp_c=None)

    with pytest.raises(ValidationError):
        ProfileUpdateRequest(aop_mmhg=40)
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(aop_mmhg=351)
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(basal_body_temp_c=34.9)
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(basal_body_temp_c=38.6)


def test_unset_baselines_do_not_wipe_stored_values(db_session):
    profile = AthleteProfile(name="Baseline", age=30, weight=68.0, aop_mmhg=200, basal_body_temp_c=36.4)
    db_session.add(profile)
    db_session.commit()

    payload = ProfileUpdateRequest(name="Baseline Updated")
    updates = payload.model_dump(exclude_unset=True)
    _apply_scalar_updates(profile, updates)
    profile.name = updates["name"]
    db_session.commit()
    db_session.refresh(profile)

    assert profile.name == "Baseline Updated"
    assert profile.aop_mmhg == 200
    assert profile.basal_body_temp_c == 36.4


def test_apply_and_read_round_trip(db_session):
    profile = AthleteProfile(name="Baseline", age=30, weight=68.0)
    db_session.add(profile)
    db_session.commit()

    payload = ProfileUpdateRequest(aop_mmhg=165.5, basal_body_temp_c=36.8)
    updates = payload.model_dump(exclude_unset=True)
    _apply_scalar_updates(profile, updates)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.aop_mmhg == 165.5
    assert profile.basal_body_temp_c == 36.8

    response = AthleteProfileResponse.model_validate(profile)
    assert response.aop_mmhg == 165.5
    assert response.basal_body_temp_c == 36.8

    cleared = ProfileUpdateRequest(aop_mmhg=None, basal_body_temp_c=None)
    _apply_scalar_updates(profile, cleared.model_dump(exclude_unset=True))
    db_session.commit()
    db_session.refresh(profile)
    assert profile.aop_mmhg is None
    assert profile.basal_body_temp_c is None


def test_migration_list_adds_the_new_columns():
    source = (Path(__file__).resolve().parents[1] / "app" / "migrate.py").read_text(encoding="utf-8")
    assert '("basal_body_temp_c", "DOUBLE PRECISION")' in source
    assert '("aop_mmhg", "DOUBLE PRECISION")' in source

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import AthleteProfile, User
from app.schemas import ManualBiometricRequest, ManualBiometricResponse
from app.services.biometric_providers import ingest_daily_biometrics
from app.services.biometric_sync import upsert_biometric_row

router = APIRouter(prefix="/biometrics", tags=["biometrics"])


def _require_profile(current_user: User, db: Session) -> AthleteProfile:
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    profile = (
        db.query(AthleteProfile)
        .filter(AthleteProfile.id == current_user.athlete_profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    return profile


@router.post("/manual", response_model=ManualBiometricResponse)
def upsert_manual_biometric(
    payload: ManualBiometricRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    sleep_seconds = None
    if payload.sleep_hours is not None:
        sleep_seconds = int(round(float(payload.sleep_hours) * 3600))

    upsert_biometric_row(
        db,
        profile.id,
        payload.metric_date,
        resting_heart_rate=payload.resting_heart_rate,
        heart_rate_variability=payload.heart_rate_variability,
        sleep_seconds=sleep_seconds,
        sleep_score=payload.sleep_score,
        readiness_score=payload.readiness_score,
        stress_score=payload.stress_score,
        source_device="manual",
        raw={"source": "manual_api"},
    )
    merged = ingest_daily_biometrics(db, profile.id, payload.metric_date)
    db.commit()
    return ManualBiometricResponse(
        metric_date=payload.metric_date.isoformat(),
        source_device="manual",
        merged=merged,
    )


@router.post("/sync/{metric_date}", response_model=ManualBiometricResponse)
def sync_biometric_day(
    metric_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    merged = ingest_daily_biometrics(db, profile.id, metric_date)
    db.commit()
    return ManualBiometricResponse(
        metric_date=metric_date.isoformat(),
        source_device=merged.get("source_device") or "merged",
        merged=merged,
    )

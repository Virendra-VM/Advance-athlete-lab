from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import AthleteProfile, CyclePeriodLog, User
from app.schemas import CycleContextResponse, CyclePeriodLogCreate
from app.services.menstrual_engine import build_cycle_context_for_athlete

router = APIRouter(prefix="/cycle", tags=["cycle"])


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


@router.get("/context", response_model=CycleContextResponse)
def get_cycle_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    ctx = build_cycle_context_for_athlete(db, profile)
    if ctx is None:
        return CycleContextResponse(enabled=False, available=False)
    return CycleContextResponse(**ctx)


@router.post("/period-starts", response_model=CycleContextResponse)
def log_period_start(
    payload: CyclePeriodLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    if not profile.cycle_tracking_enabled:
        raise HTTPException(
            status_code=400,
            detail="Enable cycle tracking on your profile before logging period starts.",
        )
    existing = (
        db.query(CyclePeriodLog)
        .filter(
            CyclePeriodLog.athlete_profile_id == profile.id,
            CyclePeriodLog.period_start_date == payload.period_start_date,
        )
        .first()
    )
    if existing is None:
        db.add(
            CyclePeriodLog(
                athlete_profile_id=profile.id,
                period_start_date=payload.period_start_date,
                source="manual",
            )
        )
        db.commit()
    ctx = build_cycle_context_for_athlete(db, profile, ingest_coros=False)
    return CycleContextResponse(**(ctx or {"enabled": True, "available": False}))

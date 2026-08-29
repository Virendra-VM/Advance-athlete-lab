from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import AthleteProfile, User
from app.schemas import CoachContextResponse
from app.services.athlete_coach_context import build_athlete_coach_context

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/context", response_model=CoachContextResponse)
def get_coach_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    profile = (
        db.query(AthleteProfile)
        .filter(AthleteProfile.id == current_user.athlete_profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")

    context = build_athlete_coach_context(db, profile.id)
    return CoachContextResponse(**context)

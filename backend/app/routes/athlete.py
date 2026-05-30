from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AthleteStatsResponse
from app.services.training_load import compute_athlete_stats

router = APIRouter(prefix="/athlete", tags=["athlete"])


@router.get("/stats", response_model=AthleteStatsResponse)
def athlete_stats(
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return compute_athlete_stats(db, athlete_profile_id)

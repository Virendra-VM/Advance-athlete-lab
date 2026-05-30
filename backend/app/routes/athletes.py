from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AthleteProfile
from app.schemas import AthleteProfileCreate, AthleteProfileRead

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post("", response_model=AthleteProfileRead, status_code=status.HTTP_201_CREATED)
def create_athlete_profile(
    profile: AthleteProfileCreate,
    db: Session = Depends(get_db),
):
    db_profile = AthleteProfile(**profile.model_dump())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.get("", response_model=list[AthleteProfileRead])
def list_athlete_profiles(db: Session = Depends(get_db)):
    return db.query(AthleteProfile).order_by(AthleteProfile.id).all()


@router.get("/{athlete_id}", response_model=AthleteProfileRead)
def get_athlete_profile(athlete_id: int, db: Session = Depends(get_db)):
    profile = db.query(AthleteProfile).filter(AthleteProfile.id == athlete_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete profile with id {athlete_id} not found",
        )
    return profile

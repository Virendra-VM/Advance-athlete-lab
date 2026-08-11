from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_deps import build_user_response, get_current_user
from app.auth_schemas import (
    AuthResponse,
    OnboardingSubmitRequest,
    ProfileUpdateRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.database import get_db
from app.models import AthleteProfile, User
from app.services.auth import (
    create_access_token,
    default_avatar_letter,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    profile = AthleteProfile(
        name=payload.name.strip(),
        age=25,
        weight=70.0,
        avatar_letter=default_avatar_letter(payload.name),
        onboarding_completed=False,
        strava_onboarding_done=False,
    )
    db.add(profile)
    db.flush()

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        athlete_profile_id=profile.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return AuthResponse(
        access_token=token,
        user=build_user_response(user, db),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id, user.email)
    return AuthResponse(
        access_token=token,
        user=build_user_response(user, db),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_response(current_user, db)


profile_router = APIRouter(prefix="/profile", tags=["profile"])


def _get_profile_for_user(user: User, db: Session) -> AthleteProfile:
    if not user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = (
        db.query(AthleteProfile)
        .filter(AthleteProfile.id == user.athlete_profile_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@profile_router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_response(current_user, db)


@profile_router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_for_user(current_user, db)
    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "avatar_letter" and value:
            value = value[0].upper()
        setattr(profile, field, value)

    if "name" in updates and "avatar_letter" not in updates:
        profile.avatar_letter = default_avatar_letter(profile.name)

    if any(
        key in updates
        for key in (
            "primary_goal",
            "secondary_goal",
            "equipment",
            "days_per_week",
            "workout_duration_minutes",
            "preferred_workout_time",
            "injuries_limitations",
            "fitness_level",
            "exercises_hate",
            "exercises_love",
        )
    ):
        profile.fitness_goals = profile.primary_goal
        profile.medical_history = profile.injuries_limitations

    db.commit()
    db.refresh(profile)
    return build_user_response(current_user, db)


@profile_router.post("/onboarding", response_model=UserResponse)
def submit_onboarding(
    payload: OnboardingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_for_user(current_user, db)

    profile.primary_goal = payload.primary_goal.strip()
    profile.secondary_goal = (payload.secondary_goal or "").strip() or None
    profile.equipment = payload.equipment.strip()
    profile.days_per_week = payload.days_per_week
    profile.workout_duration_minutes = payload.workout_duration_minutes
    profile.preferred_workout_time = payload.preferred_workout_time.strip()
    profile.injuries_limitations = (payload.injuries_limitations or "").strip() or None
    profile.fitness_level = payload.fitness_level.strip()
    profile.exercises_hate = (payload.exercises_hate or "").strip() or None
    profile.exercises_love = (payload.exercises_love or "").strip() or None
    profile.fitness_goals = profile.primary_goal
    profile.medical_history = profile.injuries_limitations
    profile.onboarding_completed = True

    db.commit()
    db.refresh(profile)
    return build_user_response(current_user, db)


@profile_router.post("/strava-onboarding-complete", response_model=UserResponse)
def complete_strava_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_for_user(current_user, db)
    profile.strava_onboarding_done = True
    db.commit()
    return build_user_response(current_user, db)


@profile_router.post("/coros-onboarding-complete", response_model=UserResponse)
def complete_coros_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_for_user(current_user, db)
    profile.coros_onboarding_done = True
    db.commit()
    return build_user_response(current_user, db)

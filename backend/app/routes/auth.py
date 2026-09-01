from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_deps import build_user_response, get_current_user
from app.auth_schemas import (
    AuthResponse,
    EmailVerifyConfirmRequest,
    EmailVerifyStatusResponse,
    OnboardingSubmitRequest,
    ProfileUpdateRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.database import get_db
from app.models import AthleteProfile, User
from app.services.athlete_profile import (
    age_from_dob,
    dump_json_column,
    replace_injuries,
    replace_sports,
    upsert_consent,
)
from app.services.auth import (
    create_access_token,
    default_avatar_letter,
    hash_password,
    verify_password,
)
from app.services.email_verification import (
    confirm_verification,
    cooldown_remaining,
    deliver_verification_email,
    issue_token,
    request_verification,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    # Soft verification: mint the token now, deliver in the background, and let
    # the user continue straight into onboarding either way.
    verify_token = issue_token(db, user)
    db.commit()
    db.refresh(user)
    background_tasks.add_task(
        deliver_verification_email, user.email, profile.name, verify_token
    )

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


@router.get("/verify-email/status", response_model=EmailVerifyStatusResponse)
def email_verify_status(current_user: User = Depends(get_current_user)):
    return EmailVerifyStatusResponse(
        email=current_user.email,
        email_verified=current_user.email_verified_at is not None,
        verification_sent_at=current_user.email_verify_sent_at,
    )


@router.post("/verify-email/request", response_model=EmailVerifyStatusResponse)
def request_email_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    remaining = cooldown_remaining(current_user)
    if remaining > 0 and current_user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {remaining}s before requesting another email.",
        )

    result = request_verification(db, current_user)
    return EmailVerifyStatusResponse(
        email=current_user.email,
        email_verified=current_user.email_verified_at is not None,
        verification_sent_at=current_user.email_verify_sent_at,
        dev_verify_token=result["dev_verify_token"],
    )


@router.post("/verify-email/confirm", response_model=UserResponse)
def confirm_email_verification(
    payload: EmailVerifyConfirmRequest,
    db: Session = Depends(get_db),
):
    user = confirm_verification(db, payload.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        )
    return build_user_response(user, db)


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


SCALAR_V2_FIELDS = (
    "sex",
    "date_of_birth",
    "height_cm",
    "blood_type",
    "units",
    "training_history_months",
    "longest_recent_session",
    "race_prs",
    "weekly_minutes_budget",
    "goal_event_name",
    "goal_event_date",
    "goal_metric",
)

GOAL_MIRROR_FIELDS = (
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


def _apply_profile_v2_fields(db: Session, profile: AthleteProfile, updates: dict, payload) -> None:
    """Write Profile v2 scalars, JSON columns, and related rows."""
    for field in SCALAR_V2_FIELDS:
        if field in updates:
            setattr(profile, field, updates[field])

    if "current_weekly_volume" in updates:
        profile.current_weekly_volume = dump_json_column(updates["current_weekly_volume"])

    # Age stays authoritative for legacy UI; derive it from DOB when available.
    if updates.get("date_of_birth"):
        derived = age_from_dob(updates["date_of_birth"])
        if derived is not None:
            profile.age = derived

    if updates.get("sports") is not None and payload.sports is not None:
        replace_sports(db, profile, payload.sports)
    if updates.get("injuries") is not None and payload.injuries is not None:
        replace_injuries(db, profile, payload.injuries)
    if updates.get("consents") is not None and payload.consents is not None:
        upsert_consent(db, profile, payload.consents)


@profile_router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile_for_user(current_user, db)
    updates = payload.model_dump(exclude_unset=True)
    nested_fields = {"sports", "injuries", "consents", "current_weekly_volume"}

    for field, value in updates.items():
        if field in nested_fields or field in SCALAR_V2_FIELDS:
            continue
        if field == "avatar_letter" and value:
            value = value[0].upper()
        setattr(profile, field, value)

    _apply_profile_v2_fields(db, profile, updates, payload)

    if "name" in updates and "avatar_letter" not in updates:
        profile.avatar_letter = default_avatar_letter(profile.name)

    if any(key in updates for key in GOAL_MIRROR_FIELDS):
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
    updates = payload.model_dump(exclude_unset=True)

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

    if payload.name and payload.name.strip():
        profile.name = payload.name.strip()
        profile.avatar_letter = default_avatar_letter(profile.name)
    if payload.age is not None:
        profile.age = payload.age
    if payload.weight is not None:
        profile.weight = payload.weight

    _apply_profile_v2_fields(db, profile, updates, payload)

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

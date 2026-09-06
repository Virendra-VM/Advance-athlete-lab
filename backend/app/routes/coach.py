from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import Activity, AthleteProfile, PlannedWorkout, ScienceChunk, TrainingPlan, User
from app.schemas import (
    ApplyChatWeekRequest,
    CoachAdviceResponse,
    CoachChatHistoryResponse,
    CoachChatRequest,
    CoachChatResponse,
    CoachContextResponse,
    CoachPlannedWorkoutRead,
    CoachPlanResponse,
    CoachStatusResponse,
    PlanGenerateRequest,
    TodaysCallResponse,
)
from app.services.autoregulation import compute_todays_call
from app.services.ai import configured_providers, describe_ai_runtime
from app.services.athlete_coach_context import build_athlete_coach_context
from app.services.athlete_profile import get_profile_consent
from app.services.coach_ai import (
    PlanWeekNotCurrentError,
    apply_week_from_chat,
    chat_history,
    coach_chat,
    confirm_baseline,
    generate_daily_advice,
    generate_week_brief,
    generate_week_plan,
    get_active_plan,
    publish_plan_to_schedule,
)
from app.services.coach_intent import classify_chat_intent
from app.services.schedule_completion import match_planned_workout_completions

router = APIRouter(prefix="/coach", tags=["coach"])


def _require_profile(current_user: User, db: Session) -> AthleteProfile:
    profile = (
        db.query(AthleteProfile)
        .filter(AthleteProfile.id == current_user.athlete_profile_id)
        .first()
        if current_user.athlete_profile_id
        else None
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    return profile


def _require_ai_consent(db: Session, profile: AthleteProfile) -> None:
    consent = get_profile_consent(db, profile.id)
    if consent is None or not consent.ai_coaching:
        raise HTTPException(
            status_code=403,
            detail="AI coaching consent is required. Enable it in your profile to continue.",
        )


@router.get("/context", response_model=CoachContextResponse)
def get_coach_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    context = build_athlete_coach_context(db, profile.id)
    return CoachContextResponse(**context)


@router.get("/todays-call", response_model=TodaysCallResponse)
def get_todays_call(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    return compute_todays_call(db, profile.id, profile=profile)


@router.get("/status", response_model=CoachStatusResponse)
def get_coach_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lets the UI explain up front whether answers come from a model or the rules."""
    profile = _require_profile(current_user, db)
    consent = get_profile_consent(db, profile.id)
    runtime = describe_ai_runtime()
    return CoachStatusResponse(
        providers_configured=configured_providers(),
        active_provider=runtime["active_provider"],
        active_model=runtime["active_model"],
        fallback_provider=runtime["configured_fallback"],
        mode=runtime["mode"],
        ai_consent=bool(consent and consent.ai_coaching),
        science_chunks=db.query(ScienceChunk.id).count(),
        has_active_plan=get_active_plan(db, profile.id) is not None,
        ai_debug=runtime.get("debug"),
    )


@router.get("/plan", response_model=CoachPlanResponse | None)
def read_plan(
    week_start: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    plan = get_active_plan(db, profile.id, week_start)
    if plan is None:
        return None
    return CoachPlanResponse(**plan, disclaimer=None)


@router.post("/plan", response_model=CoachPlanResponse)
def create_plan(
    payload: PlanGenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    try:
        result = generate_week_plan(
            db,
            profile,
            week_start=payload.week_start if payload else None,
            timezone_name=payload.timezone if payload else None,
        )
    except PlanWeekNotCurrentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CoachPlanResponse(**result)


@router.post("/plan/{plan_id}/schedule", response_model=CoachPlanResponse)
def add_plan_to_schedule(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicit opt-in: only this copies the week onto the Schedule page."""
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    try:
        result = publish_plan_to_schedule(db, profile, plan_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Training plan not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CoachPlanResponse(**result)


@router.get("/advice", response_model=CoachAdviceResponse)
def read_advice(
    timezone: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's brief. Cached for the local day unless signals changed or refresh=true."""
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    return CoachAdviceResponse(
        **generate_daily_advice(db, profile, timezone_name=timezone, force=refresh)
    )


@router.get("/week-brief", response_model=CoachAdviceResponse)
def read_week_brief(
    timezone: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    topic: str = Query(default="volume"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """This week's page brief. Cached per Monday week + topic unless signals changed or refresh=true."""
    topic_key = (topic or "volume").strip().lower()
    if topic_key not in {
        "volume",
        "load",
        "hrv",
        "stress",
        "rhr",
        "daily",
        "sleep",
    }:
        raise HTTPException(
            status_code=422,
            detail="topic must be volume, load, hrv, stress, rhr, daily, or sleep",
        )
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    return CoachAdviceResponse(
        **generate_week_brief(
            db, profile, timezone_name=timezone, force=refresh, topic=topic_key
        )
    )


@router.get("/chat", response_model=CoachChatHistoryResponse)
def read_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    return CoachChatHistoryResponse(messages=chat_history(db, profile.id))


@router.post("/chat", response_model=CoachChatResponse)
def post_chat(
    payload: CoachChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    intent = classify_chat_intent(message, activity_id=payload.activity_id)
    return CoachChatResponse(
        **coach_chat(
            db,
            profile,
            message,
            timezone_name=payload.timezone,
            activity_id=payload.activity_id,
            intent=intent,
        )
    )


@router.post("/plan/from-chat", response_model=CoachPlanResponse)
def apply_chat_week(
    payload: ApplyChatWeekRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a chat-revised week as the current plan and optionally publish it to Schedule."""
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    try:
        result = apply_week_from_chat(
            db,
            profile,
            message_id=payload.message_id,
            markdown=payload.markdown,
            publish=payload.publish,
            timezone_name=payload.timezone,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Coach message or plan not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CoachPlanResponse(**result)


@router.post("/baseline/confirm", response_model=CoachContextResponse)
def confirm_wearable_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Athlete accepts the fitness estimates derived from their synced device data."""
    profile = _require_profile(current_user, db)
    confirm_baseline(db, profile)
    return CoachContextResponse(**build_athlete_coach_context(db, profile.id))


@router.get("/planned-workouts", response_model=list[CoachPlannedWorkoutRead])
def list_planned_workouts(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Coach plans in the shape the Schedule page already renders."""
    profile = _require_profile(current_user, db)
    start = from_date or date.today() - timedelta(days=60)
    end = to_date or date.today() + timedelta(days=90)

    match_planned_workout_completions(db, profile.id, from_date=start, to_date=end)

    workouts = (
        db.query(PlannedWorkout)
        .join(TrainingPlan, PlannedWorkout.training_plan_id == TrainingPlan.id)
        .filter(
            PlannedWorkout.athlete_profile_id == profile.id,
            PlannedWorkout.workout_date >= start,
            PlannedWorkout.workout_date <= end,
            TrainingPlan.published_at.is_not(None),
        )
        .order_by(PlannedWorkout.workout_date.asc(), PlannedWorkout.id.asc())
        .all()
    )
    activity_ids = [
        workout.completed_activity_id
        for workout in workouts
        if workout.completed_activity_id is not None
    ]
    activities = (
        {
            activity.id: activity
            for activity in db.query(Activity).filter(Activity.id.in_(activity_ids)).all()
        }
        if activity_ids
        else {}
    )

    rows = []
    for workout in workouts:
        activity = activities.get(workout.completed_activity_id)
        rows.append(
            CoachPlannedWorkoutRead(
                external_id=f"coach-{workout.id}",
                schedule_date=workout.workout_date,
                title=workout.title,
                sport_type=workout.sport,
                duration_min=workout.duration_min,
                distance_m=workout.distance_m,
                completed_activity_id=workout.completed_activity_id,
                status="completed" if activity is not None else "planned",
                completed_activity_name=activity.name if activity else None,
                completed_activity_provider=activity.provider if activity else None,
                completed_distance_m=float(activity.distance_m) if activity and activity.distance_m else None,
                completed_moving_time_s=int(activity.moving_time_s) if activity and activity.moving_time_s else None,
                workout_id=workout.id,
                plan_id=workout.training_plan_id,
                session_type=workout.session_type,
                intensity=workout.intensity,
                description=workout.description,
            )
        )
    return rows


@router.post("/workouts/{workout_id}/complete", response_model=dict)
def link_workout_completion(
    workout_id: int,
    activity_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    workout = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.id == workout_id,
            PlannedWorkout.athlete_profile_id == profile.id,
        )
        .first()
    )
    if workout is None:
        raise HTTPException(status_code=404, detail="Planned workout not found.")
    workout.completed_activity_id = activity_id
    db.commit()
    return {"id": workout.id, "completed_activity_id": workout.completed_activity_id}

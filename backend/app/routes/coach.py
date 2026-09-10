from datetime import date, datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
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
    CoachProactivePromptsResponse,
    CoachReviewFlagRead,
    CoachReviewFlagRequest,
    CoachReviewFlagsResponse,
    CoachWarmResponse,
    CoachContextResponse,
    CoachPlannedWorkoutRead,
    CoachPlanResponse,
    CoachStatusResponse,
    FavoriteTemplateRead,
    PlanGenerateRequest,
    RepeatWorkoutRequest,
    TodaysCallResponse,
    WeekPlanContextResponse,
    WorkoutComplianceRead,
)
from app.services.autoregulation import compute_todays_call
from app.services.ai import configured_providers, describe_ai_runtime
from app.services.coach_context_cache import (
    coach_context_for_response,
    get_athlete_coach_context,
)
from app.services.athlete_profile import get_profile_consent
from app.services.coach_ai import (
    PlanWeekNotCurrentError,
    add_favorite_template,
    apply_week_from_chat,
    chat_history,
    coach_chat,
    compute_workout_compliance,
    confirm_baseline,
    current_week_monday,
    generate_daily_advice,
    generate_week_brief,
    generate_week_plan,
    get_active_plan,
    list_favorite_templates,
    publish_plan_to_schedule,
    remove_favorite_template,
    repeat_planned_workout,
    resolve_clock,
)
from app.services.coach_intent import (
    SCHEDULE_UPDATE,
    WEEK_PLAN_REVIEW,
    classify_chat_intent,
)
from app.services.coach_memory import dismiss_proactive_prompt, list_proactive_prompts
from app.services.coach_review import (
    flag_message_for_review,
    list_review_flags,
    resolve_review_flag,
)
from app.services.coach_stream import (
    STREAM_STATUSES,
    delta_event,
    done_event,
    error_event,
    status_event,
    stream_reply_deltas,
)
from app.services.periodization import build_season_context
from app.services.schedule_completion import match_planned_workout_completions
from app.services.session_blueprints import enrich_workout
from app.services.workout_device_export import build_device_export
from app.services.workout_library import physiology_from_profile

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
    return CoachContextResponse(**coach_context_for_response(db, profile.id))


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
        "season",
    }:
        raise HTTPException(
            status_code=422,
            detail="topic must be volume, load, hrv, stress, rhr, daily, sleep, or season",
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


@router.get("/proactive-prompts", response_model=CoachProactivePromptsResponse)
def read_proactive_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    return CoachProactivePromptsResponse(prompts=list_proactive_prompts(db, profile.id))


@router.post("/proactive-prompts/{memory_id}/dismiss", response_model=dict)
def dismiss_proactive(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    if not dismiss_proactive_prompt(db, profile.id, memory_id):
        raise HTTPException(status_code=404, detail="Proactive prompt not found.")
    return {"dismissed": True, "id": memory_id}


@router.get("/reviews", response_model=CoachReviewFlagsResponse)
def read_review_queue(
    status: str = Query(default="open"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Human review queue — replies flagged by athletes or auto-quality checks."""
    profile = _require_profile(current_user, db)
    if status not in {"open", "resolved", "dismissed"}:
        raise HTTPException(status_code=422, detail="status must be open, resolved, or dismissed")
    return CoachReviewFlagsResponse(flags=list_review_flags(db, profile.id, status=status))


@router.post("/reviews/{message_id}/flag", response_model=CoachReviewFlagRead)
def flag_coach_reply(
    message_id: int,
    payload: CoachReviewFlagRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        row = flag_message_for_review(
            db,
            profile.id,
            message_id,
            reason="user_report",
            notes=payload.notes if payload else None,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Coach message not found.")
    preview_rows = list_review_flags(db, profile.id, status=row.status, limit=1)
    preview = preview_rows[0] if preview_rows else {}
    return CoachReviewFlagRead(
        id=row.id,
        message_id=row.message_id,
        reason=row.reason,
        category=row.category,
        notes=row.notes,
        quality_score=row.quality_score,
        status=row.status,
        created_at=row.created_at,
        message_preview=preview.get("message_preview"),
    )


@router.post("/reviews/flags/{flag_id}/resolve", response_model=CoachReviewFlagRead)
def resolve_coach_review_flag(
    flag_id: int,
    status: str = Query(default="resolved"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        row = resolve_review_flag(db, profile.id, flag_id, status=status)
    except LookupError:
        raise HTTPException(status_code=404, detail="Review flag not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CoachReviewFlagRead(
        id=row.id,
        message_id=row.message_id,
        reason=row.reason,
        category=row.category,
        notes=row.notes,
        quality_score=row.quality_score,
        status=row.status,
        created_at=row.created_at,
        message_preview=None,
    )


@router.get("/week-plan/context", response_model=WeekPlanContextResponse)
def read_week_plan_context(
    timezone: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    clock = resolve_clock(timezone)
    season_ctx = build_season_context(db, profile, on_date=clock["today"])
    return WeekPlanContextResponse(
        week_start=current_week_monday(clock["today"]),
        has_season=bool(season_ctx and season_ctx.get("has_plan")),
        planning_notes=profile.planning_notes,
        season=season_ctx,
    )


@router.get("/warm", response_model=CoachWarmResponse)
def warm_coach(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preload coach context, today's call, and proactive prompts in one round trip."""
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    context_raw = get_athlete_coach_context(db, profile.id)
    cache_meta = context_raw.get("_cache") or {}
    return CoachWarmResponse(
        context=CoachContextResponse(**coach_context_for_response(db, profile.id)),
        context_cache_hit=bool(cache_meta.get("hit")),
        todays_call=compute_todays_call(db, profile.id, profile=profile),
        proactive_prompts=list_proactive_prompts(db, profile.id),
        warmed_at=datetime.utcnow(),
    )


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

    mode = (payload.chat_mode or "").strip().lower()
    intent = None
    persist_plan = None
    if mode == "week_plan_commit":
        intent = SCHEDULE_UPDATE
        persist_plan = True
    elif mode == "week_plan_review":
        intent = WEEK_PLAN_REVIEW
        persist_plan = False
    else:
        intent = classify_chat_intent(message, activity_id=payload.activity_id)

    return CoachChatResponse(
        **coach_chat(
            db,
            profile,
            message,
            timezone_name=payload.timezone,
            activity_id=payload.activity_id,
            intent=intent,
            persist_plan=persist_plan,
        )
    )


@router.post("/chat/stream")
def post_chat_stream(
    payload: CoachChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """NDJSON stream: status updates, reply deltas, then full chat payload."""
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    mode = (payload.chat_mode or "").strip().lower()
    intent = None
    persist_plan = None
    if mode == "week_plan_commit":
        intent = SCHEDULE_UPDATE
        persist_plan = True
    elif mode == "week_plan_review":
        intent = WEEK_PLAN_REVIEW
        persist_plan = False
    else:
        intent = classify_chat_intent(message, activity_id=payload.activity_id)

    def event_generator():
        for status in STREAM_STATUSES[:-1]:
            yield status_event(status)
        try:
            result = coach_chat(
                db,
                profile,
                message,
                timezone_name=payload.timezone,
                activity_id=payload.activity_id,
                intent=intent,
                persist_plan=persist_plan,
            )
            yield status_event(STREAM_STATUSES[-1])
            reply_text = ""
            reply_payload = result.get("reply")
            if isinstance(reply_payload, dict):
                reply_text = reply_payload.get("reply") or ""
            for chunk in stream_reply_deltas(reply_text):
                yield delta_event(chunk)
            payload_json = CoachChatResponse(**result).model_dump(mode="json")
            yield done_event(payload_json)
        except Exception as exc:  # noqa: BLE001 — stream must emit error event
            yield error_event(str(exc))

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


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
    return CoachContextResponse(**coach_context_for_response(db, profile.id, force_refresh=True))


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
        try:
            structure = json.loads(workout.structure_json) if workout.structure_json else []
        except json.JSONDecodeError:
            structure = []
        filled = enrich_workout(
            {
                "sport": workout.sport,
                "title": workout.title,
                "session_type": workout.session_type,
                "duration_min": workout.duration_min,
                "description": workout.description,
                "structure": structure,
                "library_template_id": workout.library_template_id,
            }
        )
        compliance = None
        if workout.compliance_json:
            try:
                payload = json.loads(workout.compliance_json)
                compliance = WorkoutComplianceRead(
                    score=payload.get("score"),
                    grade=payload.get("grade"),
                    dimensions=payload.get("dimensions") or {},
                )
            except json.JSONDecodeError:
                compliance = None
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
                description=filled.get("description") or workout.description,
                structure=filled.get("structure") or [],
                library_template_id=workout.library_template_id,
                library_version=workout.library_version,
                compliance=compliance,
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
    if activity_id:
        from app.services.schedule_completion import _store_workout_compliance

        activity = (
            db.query(Activity)
            .filter(
                Activity.id == activity_id,
                Activity.athlete_profile_id == profile.id,
            )
            .first()
        )
        if activity:
            _store_workout_compliance(db, workout, activity)
    else:
        workout.compliance_json = None
    db.commit()
    return {"id": workout.id, "completed_activity_id": workout.completed_activity_id}


@router.post("/workouts/{workout_id}/repeat", response_model=dict)
def repeat_workout(
    workout_id: int,
    payload: RepeatWorkoutRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    _require_ai_consent(db, profile)
    try:
        return repeat_planned_workout(
            db,
            profile,
            workout_id,
            target_date=payload.target_date if payload else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workouts/{workout_id}/export")
def export_planned_workout(
    workout_id: int,
    format: str = Query(default="fit", pattern="^(fit|zwo|json)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a structured workout for Garmin / COROS / Zwift."""
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

    try:
        structure = json.loads(workout.structure_json) if workout.structure_json else []
    except json.JSONDecodeError:
        structure = []

    physiology = physiology_from_profile(profile)
    try:
        package = build_device_export(
            {
                "sport": workout.sport,
                "title": workout.title,
                "session_type": workout.session_type,
                "duration_min": workout.duration_min,
                "description": workout.description,
                "structure": structure,
                "library_template_id": workout.library_template_id,
            },
            physiology=physiology,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    export = package["formats"].get(format)
    if export is None:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{format}' is not available for this workout.",
        )

    filename = export["filename"]
    if format == "fit":
        return Response(
            content=export["bytes"],
            media_type=export["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if format == "zwo":
        return Response(
            content=export["text"],
            media_type=export["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return JSONResponse(
        content=export["payload"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/workouts/{workout_id}/compliance", response_model=dict)
def read_workout_compliance(
    workout_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        return compute_workout_compliance(db, profile, workout_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/library/favorites", response_model=list[FavoriteTemplateRead])
def read_favorite_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    return [FavoriteTemplateRead(**row) for row in list_favorite_templates(db, profile.id)]


@router.post("/library/favorites/{template_id}", response_model=dict)
def create_favorite_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        return add_favorite_template(db, profile.id, template_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/library/favorites/{template_id}", response_model=dict)
def delete_favorite_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    return remove_favorite_template(db, profile.id, template_id)

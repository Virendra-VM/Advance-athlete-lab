from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import AthleteEvent, AthleteProfile, User
from app.schemas import (
    AthleteEventCreate,
    AthleteEventRead,
    AthleteEventUpdate,
    EventCompleteRequest,
    EventCompleteResponse,
    SeasonBaselineRead,
    SeasonFeasibilityRead,
    SeasonGenerateResponse,
    SeasonPhaseAdjustRequest,
    SeasonPhaseDeleteRequest,
    SeasonPhaseReplaceRequest,
    SeasonPhaseShiftRequest,
    SeasonPhaseRead,
    SeasonPlanRead,
    SeasonPreviewConnectionsRead,
    SeasonPreviewPhaseRead,
    SeasonPreviewProfileRead,
    SeasonPreviewResponse,
    SeasonAuditResponse,
    SeasonReplanRequest,
    SeasonReplanResponse,
    SeasonReplanTrigger,
    SeasonWeekOutlineRead,
)
from app.services.season_audit import audit_season_plan
from app.services.b_race_calibration import complete_b_race_event
from app.services.periodization import (
    VALID_PRIORITIES,
    VALID_SPORTS,
    adjust_phase_weeks,
    build_season_context,
    delete_season_phase,
    replace_season_phase,
    shift_recovery_phase_to_week,
    generate_season_plan,
    get_active_season_plan,
    list_planned_events,
    preview_season_plan,
    serialize_event,
    sync_a_race_from_profile,
    sync_profile_from_a_race,
)
from app.services.zone_recalibration import complete_d_race_event, d_race_test_protocol
from app.services.season_replan import detect_replan_triggers, replan_season

router = APIRouter(prefix="/season", tags=["season"])


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


def _event_read(event: AthleteEvent) -> AthleteEventRead:
    data = serialize_event(event)
    return AthleteEventRead(
        id=data["id"],
        name=data["name"],
        date=event.event_date,
        priority=data["priority"],
        sport_type=data["sport_type"],
        target_metric=data["target_metric"],
        status=data["status"],
        result_metric=data["result_metric"],
        notes=data["notes"],
    )


def _season_read(db: Session, profile: AthleteProfile) -> SeasonPlanRead | None:
    ctx = build_season_context(db, profile)
    if ctx is None:
        return None
    if not ctx.get("has_plan"):
        a = ctx.get("a_race")
        return SeasonPlanRead(
            id=0,
            start_date=date.today(),
            end_date=date.today(),
            status="none",
            warnings=[],
            a_race=AthleteEventRead(**{**a, "date": date.fromisoformat(a["date"])})
            if a
            else None,
            upcoming_events=[
                AthleteEventRead(**{**event, "date": date.fromisoformat(event["date"])})
                for event in ctx.get("upcoming_events") or []
            ],
        )

    plan = get_active_season_plan(db, profile.id)
    if plan is None:
        return None

    # The context already serialized the phases against the athlete's baseline,
    # so reuse them instead of re-deriving the long-session ceiling without it.
    current = ctx.get("current_phase")
    a_race = ctx.get("a_race")
    feasibility = ctx.get("a_race_feasibility")
    baseline = ctx.get("baseline")

    return SeasonPlanRead(
        id=plan.id,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        template_key=plan.template_key,
        warnings=ctx.get("warnings") or [],
        a_race=AthleteEventRead(**{**a_race, "date": date.fromisoformat(a_race["date"])})
        if a_race
        else None,
        current_phase=SeasonPhaseRead(**current) if current else None,
        week_in_phase=ctx.get("week_in_phase"),
        week_intent=ctx.get("week_intent"),
        phases=[SeasonPhaseRead(**phase) for phase in ctx.get("phases") or []],
        week_outline=[
            SeasonWeekOutlineRead(**week) for week in ctx.get("week_outline") or []
        ],
        baseline=SeasonBaselineRead(**baseline) if baseline else None,
        a_race_feasibility=SeasonFeasibilityRead(**feasibility) if feasibility else None,
        upcoming_events=[
            AthleteEventRead(**{**event, "date": date.fromisoformat(event["date"])})
            for event in ctx.get("upcoming_events") or []
        ],
    )


@router.get("", response_model=SeasonPlanRead | None)
def read_season(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    sync_a_race_from_profile(db, profile)
    db.commit()
    return _season_read(db, profile)


@router.get("/preview", response_model=SeasonPreviewResponse)
def read_season_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    sync_a_race_from_profile(db, profile)
    db.commit()
    try:
        payload = preview_season_plan(db, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    a = payload["a_race"]
    return SeasonPreviewResponse(
        a_race=AthleteEventRead(**{**a, "date": date.fromisoformat(a["date"])}),
        events=[
            AthleteEventRead(**{**event, "date": date.fromisoformat(event["date"])})
            for event in payload.get("events") or []
        ],
        profile=SeasonPreviewProfileRead(**payload["profile"]),
        connections=SeasonPreviewConnectionsRead(**payload["connections"]),
        baseline=SeasonBaselineRead(**payload["baseline"]),
        warnings=payload.get("warnings") or [],
        triggers=[SeasonReplanTrigger(**trigger) for trigger in payload.get("triggers") or []],
        phase_sketch=[SeasonPreviewPhaseRead(**phase) for phase in payload.get("phase_sketch") or []],
        total_weeks=payload.get("total_weeks") or 0,
        season_start=payload["season_start"],
        season_end=payload["season_end"],
        has_existing_plan=bool(payload.get("has_existing_plan")),
    )


@router.post("/generate", response_model=SeasonGenerateResponse)
def generate_season(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        generate_season_plan(db, profile)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile)
    if plan_read is None:
        raise HTTPException(status_code=500, detail="Season plan was not persisted.")
    return SeasonGenerateResponse(plan=plan_read)


@router.get("/audit", response_model=SeasonAuditResponse)
def read_season_audit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    sync_a_race_from_profile(db, profile)
    db.commit()
    payload = audit_season_plan(db, profile)
    return SeasonAuditResponse(
        audited_at=payload["audited_at"],
        has_plan=payload["has_plan"],
        summary=payload["summary"],
        domains=payload.get("domains") or [],
        flags=payload["flags"],
    )


@router.get("/replan/triggers", response_model=list[SeasonReplanTrigger])
def read_replan_triggers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    plan = get_active_season_plan(db, profile.id)
    triggers = detect_replan_triggers(db, profile, plan=plan)
    return [SeasonReplanTrigger(**trigger) for trigger in triggers]


@router.post("/replan", response_model=SeasonReplanResponse)
def replan_season_route(
    payload: SeasonReplanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    try:
        result = replan_season(
            db,
            profile,
            reason=payload.reason,
            force=payload.force,
            new_bc_race=payload.new_bc_race,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.expire_all()
    plan = get_active_season_plan(db, profile.id)
    triggers_after = detect_replan_triggers(db, profile, plan=plan)
    plan_read = _season_read(db, profile) if result.get("replanned") else None
    return SeasonReplanResponse(
        replanned=result.get("replanned", False),
        message=result.get("message", ""),
        plan=plan_read,
        triggers=[SeasonReplanTrigger(**trigger) for trigger in triggers_after],
        diff=result.get("diff") or [],
        summary=result.get("summary") or [],
        reason=result.get("reason"),
    )


@router.post("/phases/{phase_id}/shift", response_model=SeasonPlanRead)
def shift_recovery_phase(
    phase_id: int,
    payload: SeasonPhaseShiftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move a recovery week to the Monday the athlete picks."""
    profile = _require_profile(current_user, db)
    try:
        shift_recovery_phase_to_week(
            db, profile, phase_id, payload.target_week_start
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile)
    if plan_read is None:
        raise HTTPException(status_code=404, detail="Season plan not found.")
    return plan_read


@router.post("/phases/{phase_id}/replace", response_model=SeasonPlanRead)
def replace_phase(
    phase_id: int,
    payload: SeasonPhaseReplaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Swap a block's macro type (base/build/peak/recovery) without moving dates."""
    profile = _require_profile(current_user, db)
    try:
        replace_season_phase(db, profile, phase_id, payload.phase_type)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile)
    if plan_read is None:
        raise HTTPException(status_code=404, detail="Season plan not found.")
    return plan_read


@router.delete("/phases/{phase_id}", response_model=SeasonPlanRead)
def remove_phase(
    phase_id: int,
    payload: SeasonPhaseDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a recovery week and merge it into the block before or after."""
    profile = _require_profile(current_user, db)
    try:
        delete_season_phase(db, profile, phase_id, merge_into=payload.merge_into)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile)
    if plan_read is None:
        raise HTTPException(status_code=404, detail="Season plan not found.")
    return plan_read


@router.patch("/phases/{phase_id}", response_model=SeasonPlanRead)
def adjust_phase(
    phase_id: int,
    payload: SeasonPhaseAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Give this block a week, or take one. The A-race date does not move."""
    if payload.delta_weeks == 0:
        raise HTTPException(status_code=400, detail="delta_weeks cannot be 0.")
    profile = _require_profile(current_user, db)
    try:
        adjust_phase_weeks(db, profile, phase_id, payload.delta_weeks)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile)
    if plan_read is None:
        raise HTTPException(status_code=404, detail="Season plan not found.")
    return plan_read


@router.get("/events", response_model=list[AthleteEventRead])
def list_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    sync_a_race_from_profile(db, profile)
    db.commit()
    return [_event_read(event) for event in list_planned_events(db, profile.id)]


@router.post("/events", response_model=AthleteEventRead)
def create_event(
    payload: AthleteEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    priority = payload.priority.upper()
    sport = payload.sport_type.lower()
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid event priority.")
    if sport not in VALID_SPORTS:
        raise HTTPException(status_code=400, detail="Invalid sport type.")

    if priority == "A":
        for existing in list_planned_events(db, profile.id):
            if existing.priority == "A" and existing.status == "planned":
                existing.status = "cancelled"

    row = AthleteEvent(
        athlete_profile_id=profile.id,
        name=payload.name.strip(),
        event_date=payload.date,
        priority=priority,
        sport_type=sport,
        target_metric=payload.target_metric,
        notes=payload.notes,
        status="planned",
    )
    db.add(row)
    db.flush()
    if priority == "A":
        sync_profile_from_a_race(profile, row)
    db.commit()
    db.refresh(row)
    return _event_read(row)


@router.patch("/events/{event_id}", response_model=AthleteEventRead)
def update_event(
    event_id: int,
    payload: AthleteEventUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    row = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.id == event_id,
            AthleteEvent.athlete_profile_id == profile.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.date is not None:
        row.event_date = payload.date
    if payload.priority is not None:
        priority = payload.priority.upper()
        if priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid event priority.")
        row.priority = priority
    if payload.sport_type is not None:
        sport = payload.sport_type.lower()
        if sport not in VALID_SPORTS:
            raise HTTPException(status_code=400, detail="Invalid sport type.")
        row.sport_type = sport
    if payload.target_metric is not None:
        row.target_metric = payload.target_metric
    if payload.status is not None:
        row.status = payload.status
    if payload.result_metric is not None:
        row.result_metric = payload.result_metric
    if payload.notes is not None:
        row.notes = payload.notes

    if row.priority == "A" and row.status == "planned":
        sync_profile_from_a_race(profile, row)

    db.commit()
    db.refresh(row)
    return _event_read(row)


@router.get("/events/{event_id}/protocol")
def get_event_protocol(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    row = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.id == event_id,
            AthleteEvent.athlete_profile_id == profile.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    if row.priority != "D":
        raise HTTPException(status_code=400, detail="Only D-priority events have test protocols.")
    return d_race_test_protocol(row)


@router.post("/events/{event_id}/complete", response_model=EventCompleteResponse)
def complete_event(
    event_id: int,
    payload: EventCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    row = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.id == event_id,
            AthleteEvent.athlete_profile_id == profile.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        if row.priority == "D":
            result = complete_d_race_event(
                db,
                profile,
                row,
                ftp_watts=payload.ftp_watts,
                lthr_bpm=payload.lthr_bpm,
                threshold_pace=payload.threshold_pace,
                threshold_pace_sec_per_km=payload.threshold_pace_sec_per_km,
                result_metric=payload.result_metric,
            )
        elif row.priority == "B":
            result = complete_b_race_event(
                db,
                profile,
                row,
                result_metric=payload.result_metric,
            )
        else:
            row.status = "completed"
            if payload.result_metric:
                row.result_metric = payload.result_metric
            db.commit()
            result = {
                "event_id": row.id,
                "status": row.status,
                "result_metric": row.result_metric,
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EventCompleteResponse(**result)


@router.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _require_profile(current_user, db)
    row = (
        db.query(AthleteEvent)
        .filter(
            AthleteEvent.id == event_id,
            AthleteEvent.athlete_profile_id == profile.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    db.delete(row)
    db.commit()

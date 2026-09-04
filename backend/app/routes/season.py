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
    SeasonGenerateResponse,
    SeasonPhaseRead,
    SeasonPlanRead,
    SeasonReplanRequest,
    SeasonReplanResponse,
    SeasonReplanTrigger,
)
from app.services.b_race_calibration import complete_b_race_event
from app.services.periodization import (
    VALID_PRIORITIES,
    VALID_SPORTS,
    build_season_context,
    generate_season_plan,
    get_active_season_plan,
    get_phases_for_plan,
    list_planned_events,
    serialize_event,
    serialize_phase,
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

    phases = [
        SeasonPhaseRead(**serialize_phase(phase))
        for phase in get_phases_for_plan(db, plan.id)
    ]
    current = ctx.get("current_phase")
    a_race = ctx.get("a_race")

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
        phases=phases,
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
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan_read = _season_read(db, profile) if result.get("replanned") else None
    return SeasonReplanResponse(
        replanned=result.get("replanned", False),
        message=result.get("message", ""),
        plan=plan_read,
        triggers=[SeasonReplanTrigger(**trigger) for trigger in result.get("triggers") or []],
        diff=result.get("diff") or [],
        reason=result.get("reason"),
    )


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

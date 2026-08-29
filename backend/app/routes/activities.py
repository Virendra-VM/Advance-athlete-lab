from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import Activity, ActivityNote, User
from app.schemas import (
    ActivityEnrichResponse,
    ActivityListResponse,
    ActivityNoteCreate,
    ActivityNoteListResponse,
    ActivityNoteRead,
    ActivityNoteUpdate,
    ActivityNotesUpdate,
    ActivityPointsResponse,
    ActivityRead,
    ActivitySummaryBucket,
    ActivitySummaryResponse,
)
from app.services.activity_detail import (
    activity_sport_family,
    enrich_activity_detail,
    parse_activity_detail,
)
from app.services.activity_points import load_activity_points

router = APIRouter(prefix="/activities", tags=["activities"])


def _serialize_activity(activity: Activity, *, include_detail: bool = True) -> ActivityRead:
    detail = parse_activity_detail(activity) if include_detail else None
    return ActivityRead(
        id=activity.id,
        athlete_profile_id=activity.athlete_profile_id,
        provider=activity.provider or "strava",
        external_activity_id=activity.external_activity_id,
        strava_activity_id=activity.strava_activity_id,
        canonical_activity_id=activity.canonical_activity_id,
        name=activity.name,
        activity_date=activity.activity_date,
        distance_m=activity.distance_m,
        moving_time_s=activity.moving_time_s,
        average_heartrate=activity.average_heartrate,
        max_heartrate=activity.max_heartrate,
        sport_type=activity.sport_type,
        sport_type_code=getattr(activity, "sport_type_code", None),
        points_file_path=activity.points_file_path,
        source_fit_file=activity.source_fit_file,
        notes=activity.notes,
        detail=detail,
        sport_family=activity_sport_family(activity.sport_type),
        detail_fetched_at=getattr(activity, "detail_fetched_at", None) if include_detail else None,
        created_at=activity.created_at,
    )


@router.get("", response_model=ActivityListResponse)
def list_activities(
    athlete_profile_id: int = Query(...),
    q: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    sort: str = Query(default="date_desc"),
    include_duplicates: bool = Query(
        default=False,
        description="If false (default), hide cross-provider duplicates linked via canonical_activity_id.",
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Activity).filter(Activity.athlete_profile_id == athlete_profile_id)

    if not include_duplicates:
        query = query.filter(Activity.canonical_activity_id.is_(None))

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(Activity.name.ilike(like), Activity.sport_type.ilike(like))
        )
    if sport and sport.lower() not in {"all", "all sports"}:
        query = query.filter(Activity.sport_type.ilike(f"%{sport}%"))
    if provider and provider.lower() in {"strava", "coros"}:
        query = query.filter(Activity.provider == provider.lower())
    if from_date:
        query = query.filter(
            Activity.activity_date >= datetime.combine(from_date, datetime.min.time())
        )
    if to_date:
        query = query.filter(
            Activity.activity_date
            <= datetime.combine(to_date, datetime.max.time().replace(microsecond=0))
        )

    sort_map = {
        "date_desc": desc(Activity.activity_date),
        "date_asc": asc(Activity.activity_date),
        "distance_desc": desc(Activity.distance_m),
        "distance_asc": asc(Activity.distance_m),
        "duration_desc": desc(Activity.moving_time_s),
        "duration_asc": asc(Activity.moving_time_s),
        "name_asc": asc(Activity.name),
    }
    order = sort_map.get(sort, desc(Activity.activity_date))

    total = query.with_entities(func.count(Activity.id)).scalar() or 0
    items = (
        query.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    )
    return ActivityListResponse(
        items=[_serialize_activity(item, include_detail=False) for item in items],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=ActivitySummaryResponse)
def activity_summary(
    athlete_profile_id: int = Query(...),
    include_duplicates: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = db.query(Activity).filter(Activity.athlete_profile_id == athlete_profile_id)
    if not include_duplicates:
        query = query.filter(Activity.canonical_activity_id.is_(None))
    activities = query.order_by(Activity.activity_date.asc()).all()

    buckets: dict[str, dict] = defaultdict(
        lambda: {"total_distance_km": 0.0, "activity_count": 0}
    )
    for activity in activities:
        month_key = activity.activity_date.strftime("%Y-%m")
        buckets[month_key]["total_distance_km"] += activity.distance_m / 1000.0
        buckets[month_key]["activity_count"] += 1

    return ActivitySummaryResponse(
        buckets=[
            ActivitySummaryBucket(
                month=month,
                total_distance_km=round(values["total_distance_km"], 2),
                activity_count=values["activity_count"],
            )
            for month, values in sorted(buckets.items())
        ]
    )


@router.post("/dedupe")
def dedupe_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link existing Strava↔COROS duplicate pairs for the current athlete."""
    from app.services.activity_dedupe import backfill_athlete_duplicates

    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    result = backfill_athlete_duplicates(db, current_user.athlete_profile_id)
    return {
        "status": "ok",
        "scanned_strava": result["scanned_strava"],
        "linked": result["linked"],
    }


@router.get("/{activity_id}/points", response_model=ActivityPointsResponse)
def get_activity_points(activity_id: int, db: Session = Depends(get_db)):
    result = load_activity_points(db, activity_id)
    if not result.get("found"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with id {activity_id} not found",
        )
    return ActivityPointsResponse(
        activity_id=result["activity_id"],
        has_points=result["has_points"],
        metrics=result.get("metrics", []),
        points=result.get("points", []),
    )


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with id {activity_id} not found",
        )
    return _serialize_activity(activity)


@router.post("/{activity_id}/enrich", response_model=ActivityEnrichResponse)
def enrich_activity(
    activity_id: int,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pull COROS detail/laps (+ Strava extras) and store a normalized detail payload."""
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_profile_id == current_user.athlete_profile_id,
        )
        .first()
    )
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with id {activity_id} not found",
        )

    client = None
    try:
        from app.services.coros_sync import _client_for_connection, get_coros_connection

        connection = get_coros_connection(db, current_user.athlete_profile_id)
        if connection is not None:
            client = _client_for_connection(db, connection)
            client.initialize()
    except Exception:  # noqa: BLE001
        client = None

    result = enrich_activity_detail(db, activity, client=client, force=force)
    db.refresh(activity)
    # If enrich wrote onto a canonical parent, re-load that row for the response.
    response_activity = activity
    if result.get("activity_id") and result["activity_id"] != activity.id:
        parent = db.query(Activity).filter(Activity.id == result["activity_id"]).first()
        if parent is not None:
            response_activity = parent

    return ActivityEnrichResponse(
        ok=bool(result.get("ok")),
        skipped=bool(result.get("skipped")),
        reason=result.get("reason"),
        activity_id=int(result.get("activity_id") or activity.id),
        detail=result.get("detail") or parse_activity_detail(response_activity),
        errors=list(result.get("errors") or []),
        sources=list(result.get("sources") or []),
        activity=_serialize_activity(response_activity),
    )


@router.patch("/{activity_id}/notes", response_model=ActivityRead)
def update_activity_notes(
    activity_id: int,
    payload: ActivityNotesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy single-field notes write — prefer /notes CRUD endpoints."""
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_profile_id == current_user.athlete_profile_id,
        )
        .first()
    )
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with id {activity_id} not found",
        )
    body = (payload.notes or "").strip() or None
    activity.notes = body
    if body:
        existing = (
            db.query(ActivityNote)
            .filter(ActivityNote.activity_id == activity_id)
            .order_by(ActivityNote.created_at.asc())
            .first()
        )
        if existing is None:
            db.add(
                ActivityNote(
                    activity_id=activity.id,
                    athlete_profile_id=current_user.athlete_profile_id,
                    body=body,
                )
            )
        else:
            existing.body = body
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


def _require_owned_activity(
    db: Session, activity_id: int, athlete_profile_id: int
) -> Activity:
    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_profile_id == athlete_profile_id,
        )
        .first()
    )
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with id {activity_id} not found",
        )
    return activity


@router.get("/{activity_id}/notes", response_model=ActivityNoteListResponse)
def list_activity_notes(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    activity = _require_owned_activity(db, activity_id, current_user.athlete_profile_id)

    notes = (
        db.query(ActivityNote)
        .filter(ActivityNote.activity_id == activity_id)
        .order_by(ActivityNote.created_at.desc())
        .all()
    )
    # One-time legacy migration if the old text field still has content.
    if not notes and activity.notes and activity.notes.strip():
        migrated = ActivityNote(
            activity_id=activity.id,
            athlete_profile_id=current_user.athlete_profile_id,
            body=activity.notes.strip(),
        )
        db.add(migrated)
        db.commit()
        db.refresh(migrated)
        notes = [migrated]

    return ActivityNoteListResponse(items=notes)


@router.post(
    "/{activity_id}/notes",
    response_model=ActivityNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_activity_note(
    activity_id: int,
    payload: ActivityNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    _require_owned_activity(db, activity_id, current_user.athlete_profile_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Note body is required.")
    note = ActivityNote(
        activity_id=activity_id,
        athlete_profile_id=current_user.athlete_profile_id,
        body=body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/{activity_id}/notes/{note_id}", response_model=ActivityNoteRead)
def update_activity_note(
    activity_id: int,
    note_id: int,
    payload: ActivityNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    _require_owned_activity(db, activity_id, current_user.athlete_profile_id)
    note = (
        db.query(ActivityNote)
        .filter(
            ActivityNote.id == note_id,
            ActivityNote.activity_id == activity_id,
            ActivityNote.athlete_profile_id == current_user.athlete_profile_id,
        )
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found.")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Note body is required.")
    note.body = body
    note.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{activity_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity_note(
    activity_id: int,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.athlete_profile_id:
        raise HTTPException(status_code=404, detail="Athlete profile not found.")
    _require_owned_activity(db, activity_id, current_user.athlete_profile_id)
    note = (
        db.query(ActivityNote)
        .filter(
            ActivityNote.id == note_id,
            ActivityNote.activity_id == activity_id,
            ActivityNote.athlete_profile_id == current_user.athlete_profile_id,
        )
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.delete(note)
    db.commit()
    return None

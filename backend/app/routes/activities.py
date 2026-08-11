from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.auth_deps import get_current_user
from app.database import get_db
from app.models import Activity, User
from app.schemas import (
    ActivityListResponse,
    ActivityNotesUpdate,
    ActivityPointsResponse,
    ActivityRead,
    ActivitySummaryBucket,
    ActivitySummaryResponse,
)
from app.services.activity_points import load_activity_points

router = APIRouter(prefix="/activities", tags=["activities"])


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
        items=items,
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
    return activity


@router.patch("/{activity_id}/notes", response_model=ActivityRead)
def update_activity_notes(
    activity_id: int,
    payload: ActivityNotesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    activity.notes = (payload.notes or "").strip() or None
    db.commit()
    db.refresh(activity)
    return activity

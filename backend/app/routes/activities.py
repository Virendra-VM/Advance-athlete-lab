from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity
from app.schemas import (
    ActivityPointsResponse,
    ActivityRead,
    ActivitySummaryBucket,
    ActivitySummaryResponse,
)
from app.services.activity_points import load_activity_points

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("", response_model=list[ActivityRead])
def list_activities(
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(Activity)
        .filter(Activity.athlete_profile_id == athlete_profile_id)
        .order_by(Activity.activity_date.desc())
        .all()
    )


@router.get("/summary", response_model=ActivitySummaryResponse)
def activity_summary(
    athlete_profile_id: int = Query(...),
    db: Session = Depends(get_db),
):
    activities = (
        db.query(Activity)
        .filter(Activity.athlete_profile_id == athlete_profile_id)
        .order_by(Activity.activity_date.asc())
        .all()
    )

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

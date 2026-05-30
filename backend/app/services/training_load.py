from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Activity
from app.schemas import AthleteStatsResponse, WeeklyVolumeBucket

WEEK_COUNT = 8
WEEK_DAYS = 7


def _round_km(value: float) -> float:
    return round(value, 2)


def _week_label(week_start: datetime) -> str:
    return week_start.strftime("%b %d")


def _sum_distance_km(
    db: Session,
    athlete_profile_id: int,
    start: datetime,
    end: datetime,
) -> float:
    total_m = (
        db.query(func.coalesce(func.sum(Activity.distance_m), 0.0))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= start,
            Activity.activity_date <= end,
        )
        .scalar()
    )
    return _round_km(float(total_m) / 1000.0)


def _build_weekly_buckets(
    db: Session,
    athlete_profile_id: int,
    now: datetime,
) -> list[WeeklyVolumeBucket]:
    lookback_days = WEEK_COUNT * WEEK_DAYS
    window_start = now - timedelta(days=lookback_days)

    rows = (
        db.query(Activity.activity_date, Activity.distance_m)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= window_start,
            Activity.activity_date <= now,
        )
        .all()
    )

    buckets: list[WeeklyVolumeBucket] = []
    for week_index in range(WEEK_COUNT):
        bucket_start = now - timedelta(days=lookback_days - week_index * WEEK_DAYS)
        is_latest_week = week_index == WEEK_COUNT - 1
        bucket_end = now if is_latest_week else bucket_start + timedelta(days=WEEK_DAYS)

        total_m = 0.0
        for activity_date, distance_m in rows:
            if is_latest_week:
                if bucket_start <= activity_date <= bucket_end:
                    total_m += distance_m
            elif bucket_start <= activity_date < bucket_end:
                total_m += distance_m

        buckets.append(
            WeeklyVolumeBucket(
                week_start=bucket_start.date().isoformat(),
                week_label=_week_label(bucket_start),
                total_distance_km=_round_km(total_m / 1000.0),
            )
        )

    return buckets


def compute_athlete_stats(db: Session, athlete_profile_id: int) -> AthleteStatsResponse:
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    twenty_eight_days_ago = now - timedelta(days=28)

    acute_load_km = _sum_distance_km(db, athlete_profile_id, seven_days_ago, now)
    total_28d_km = _sum_distance_km(db, athlete_profile_id, twenty_eight_days_ago, now)
    chronic_load_km = _round_km(total_28d_km / 4.0)

    acwr = None
    if chronic_load_km > 0:
        acwr = round(acute_load_km / chronic_load_km, 2)

    weekly_volume_history = _build_weekly_buckets(db, athlete_profile_id, now)

    return AthleteStatsResponse(
        acute_load_km=acute_load_km,
        chronic_load_km=chronic_load_km,
        acwr=acwr,
        weekly_volume_history=weekly_volume_history,
    )

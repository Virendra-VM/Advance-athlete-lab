from datetime import datetime, timedelta
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Activity
from app.schemas import AthleteStatsResponse, WeeklyVolumeBucket

WEEK_COUNT = 8
WEEK_DAYS = 7

STRENGTH_SPORTS = {"strength", "weighttraining", "weight_training", "gym", "yoga", "pilates", "crossfit"}
ENDURANCE_SPORTS = {"run", "running", "ride", "cycling", "bike", "swim", "swimming", "walk", "hike"}


def _round_km(value: float) -> float:
    return round(value, 2)


def _round_load(value: float) -> float:
    return round(value, 1)


def _week_label(week_start: datetime) -> str:
    return week_start.strftime("%b %d")


def _sport_key(sport_type: str | None) -> str:
    return (sport_type or "").strip().lower().replace(" ", "_")


def _is_strength_sport(sport_type: str | None) -> bool:
    key = _sport_key(sport_type)
    return any(token in key for token in STRENGTH_SPORTS)


def _detail_dict(activity: Activity) -> dict:
    raw = activity.detail_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def compute_session_load(
    activity: Activity,
    *,
    physiology: dict | None = None,
) -> float:
    """Unified session load — COROS effort, HR-TRIMP, distance, or duration fallback."""
    detail = _detail_dict(activity)
    for key in (
        "training_load",
        "trainingLoad",
        "effort_load",
        "effortLoad",
        "load",
        "tss",
    ):
        value = detail.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return _round_load(float(value))

    summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
    for key in ("training_load", "trainingLoad", "load", "tss"):
        value = summary.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return _round_load(float(value))

    minutes = max(0.0, float(activity.moving_time_s or 0) / 60.0)
    if minutes <= 0:
        return 0.0

    physiology = physiology or {}
    lthr = physiology.get("lthr_bpm") or physiology.get("max_hr_bpm")
    resting = physiology.get("resting_hr") or 60
    avg_hr = activity.average_heartrate

    if avg_hr and lthr and float(lthr) > resting:
        hr_ratio = max(0.5, min(1.6, float(avg_hr) / float(lthr)))
        trimp = minutes * hr_ratio * hr_ratio
        return _round_load(trimp)

    if activity.distance_m and float(activity.distance_m) > 0:
        return _round_load(float(activity.distance_m) / 1000.0)

    if _is_strength_sport(activity.sport_type):
        return _round_load(minutes * 0.75)

    return _round_load(minutes * 0.9)


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
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
    )
    return _round_km(float(total_m) / 1000.0)


def _sum_session_load(
    db: Session,
    athlete_profile_id: int,
    start: datetime,
    end: datetime,
    *,
    physiology: dict | None = None,
) -> float:
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= start,
            Activity.activity_date <= end,
            Activity.canonical_activity_id.is_(None),
        )
        .all()
    )
    total = sum(compute_session_load(row, physiology=physiology) for row in rows)
    return _round_load(total)


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
            Activity.canonical_activity_id.is_(None),
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


def compute_acwr(
    db: Session,
    athlete_profile_id: int,
    *,
    physiology: dict | None = None,
) -> dict:
    """Training load ratio — unified load units primary, minutes/km secondary."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    twenty_eight_days_ago = now - timedelta(days=28)

    acute_load = _sum_session_load(
        db, athlete_profile_id, seven_days_ago, now, physiology=physiology
    )
    total_28d_load = _sum_session_load(
        db, athlete_profile_id, twenty_eight_days_ago, now, physiology=physiology
    )
    chronic_load = _round_load(total_28d_load / 4.0)
    load_acwr = round(acute_load / chronic_load, 2) if chronic_load > 0 else None

    acute_minutes = (
        db.query(func.coalesce(func.sum(Activity.moving_time_s), 0))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= seven_days_ago,
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
        or 0
    )
    chronic_minutes = (
        db.query(func.coalesce(func.sum(Activity.moving_time_s), 0))
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= twenty_eight_days_ago,
            Activity.canonical_activity_id.is_(None),
        )
        .scalar()
        or 0
    )
    acute_min = round(float(acute_minutes) / 60.0)
    chronic_min = round(float(chronic_minutes) / 60.0 / 4.0)
    minutes_acwr = round(acute_min / chronic_min, 2) if chronic_min > 0 else None

    acute_load_km = _sum_distance_km(db, athlete_profile_id, seven_days_ago, now)
    total_28d_km = _sum_distance_km(db, athlete_profile_id, twenty_eight_days_ago, now)
    chronic_load_km = _round_km(total_28d_km / 4.0)
    km_acwr = round(acute_load_km / chronic_load_km, 2) if chronic_load_km > 0 else None

    primary = load_acwr or minutes_acwr or km_acwr
    return {
        "acute_load": acute_load,
        "chronic_load": chronic_load,
        "load_acwr": load_acwr,
        "acute_minutes": acute_min,
        "chronic_minutes": chronic_min,
        "minutes_acwr": minutes_acwr,
        "acute_km": acute_load_km,
        "chronic_km": chronic_load_km,
        "km_acwr": km_acwr,
        "acwr": primary,
        "acwr_source": "load"
        if load_acwr is not None
        else ("minutes" if minutes_acwr is not None else "km"),
    }


def compute_athlete_stats(
    db: Session,
    athlete_profile_id: int,
    *,
    physiology: dict | None = None,
) -> AthleteStatsResponse:
    bundle = compute_acwr(db, athlete_profile_id, physiology=physiology)
    weekly_volume_history = _build_weekly_buckets(db, athlete_profile_id, datetime.utcnow())

    return AthleteStatsResponse(
        acute_load_km=bundle["acute_km"],
        chronic_load_km=bundle["chronic_km"],
        acwr=bundle["acwr"],
        acute_load=bundle["acute_load"],
        chronic_load=bundle["chronic_load"],
        load_acwr=bundle["load_acwr"],
        acwr_source=bundle["acwr_source"],
        weekly_volume_history=weekly_volume_history,
    )

"""Assemble a unified athlete context for future AI coaching."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ActivityNote,
    AthleteProfile,
    CorosScheduleItem,
    DailyHealthMetric,
    FitnessAssessment,
    TrainingLoadSnapshot,
)
from app.services.athlete_profile import (
    age_from_dob,
    get_profile_consent,
    get_profile_sports,
    load_json_column,
)
from app.services.coach_safety import build_safety_profile, readiness_flags_from_signals
from app.services.coros_sync import get_coros_connection
from app.services.activity_detail import parse_activity_detail
from app.services.session_telemetry import (
    compact_activity_metrics,
    notes_by_activity_id,
    persist_physiology_estimate,
    resolve_physiology,
    _enrich_laps,
)


def build_athlete_coach_context(db: Session, athlete_profile_id: int) -> dict:
    profile = (
        db.query(AthleteProfile).filter(AthleteProfile.id == athlete_profile_id).first()
    )
    if profile is None:
        return {"error": "profile_not_found"}

    since = datetime.utcnow() - timedelta(days=28)
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_profile_id == athlete_profile_id,
            Activity.activity_date >= since,
            Activity.canonical_activity_id.is_(None),
        )
        .order_by(Activity.activity_date.desc())
        .limit(40)
        .all()
    )

    health_rows = (
        db.query(DailyHealthMetric)
        .filter(
            DailyHealthMetric.athlete_profile_id == athlete_profile_id,
            DailyHealthMetric.provider == "coros",
        )
        .order_by(DailyHealthMetric.metric_date.desc())
        .limit(14)
        .all()
    )
    fitness = (
        db.query(FitnessAssessment)
        .filter(
            FitnessAssessment.athlete_profile_id == athlete_profile_id,
            FitnessAssessment.provider == "coros",
        )
        .order_by(FitnessAssessment.snapshot_at.desc())
        .first()
    )
    load = (
        db.query(TrainingLoadSnapshot)
        .filter(
            TrainingLoadSnapshot.athlete_profile_id == athlete_profile_id,
            TrainingLoadSnapshot.provider == "coros",
        )
        .order_by(TrainingLoadSnapshot.snapshot_at.desc())
        .first()
    )
    schedule = (
        db.query(CorosScheduleItem)
        .filter(CorosScheduleItem.athlete_profile_id == athlete_profile_id)
        .order_by(CorosScheduleItem.schedule_date.asc())
        .limit(14)
        .all()
    )
    connection = get_coros_connection(db, athlete_profile_id)

    latest_health_row = health_rows[0] if health_rows else None
    readiness_flags = readiness_flags_from_signals(
        recovery_pct=fitness.recovery_pct if fitness else None,
        sleep_score=latest_health_row.sleep_score if latest_health_row else None,
        stress=latest_health_row.stress if latest_health_row else None,
        hrv=latest_health_row.hrv if latest_health_row else None,
        hrv_assessment=latest_health_row.hrv_assessment if latest_health_row else None,
        load_ratio=load.load_ratio if load else None,
    )

    race_preds = {}
    if fitness and fitness.race_preds_json:
        try:
            race_preds = json.loads(fitness.race_preds_json)
        except json.JSONDecodeError:
            race_preds = {}

    comments = []
    if load and load.daily_comments_json:
        try:
            comments = json.loads(load.daily_comments_json)
        except json.JSONDecodeError:
            comments = []

    sports = get_profile_sports(db, athlete_profile_id)
    consent = get_profile_consent(db, athlete_profile_id)
    safety = build_safety_profile(db, profile, readiness_flags)

    resting_hr = health_rows[0].resting_heart_rate if health_rows else None
    physiology = resolve_physiology(profile, activities, resting_hr=resting_hr)
    persist_physiology_estimate(profile, physiology)

    note_rows = []
    if activities:
        note_rows = (
            db.query(ActivityNote)
            .filter(ActivityNote.activity_id.in_([row.id for row in activities]))
            .all()
        )
    notes = notes_by_activity_id(note_rows)

    compact_rows = []
    focal_sessions = []
    for activity in activities:
        compact = compact_activity_metrics(
            activity,
            physiology=physiology,
            note=notes.get(activity.id),
            local_date=activity.activity_date.isoformat() if activity.activity_date else None,
        )
        compact["provider"] = activity.provider
        compact["activity_date"] = compact["date"]
        compact["distance_m"] = activity.distance_m
        compact["moving_time_s"] = activity.moving_time_s
        compact["average_heartrate"] = activity.average_heartrate
        compact["max_heartrate"] = activity.max_heartrate
        compact["sport_type"] = activity.sport_type
        compact_rows.append(compact)
        if len(focal_sessions) < 4:
            detail = parse_activity_detail(activity) or {}
            raw_laps = detail.get("laps") if isinstance(detail.get("laps"), list) else []
            exercises = detail.get("exercises") if isinstance(detail.get("exercises"), list) else []
            focal_sessions.append(
                {
                    **compact,
                    "laps": _enrich_laps(raw_laps, physiology)[:24],
                    "exercises": exercises[:12],
                }
            )

    return {
        "athlete_profile_id": athlete_profile_id,
        "generated_at": datetime.utcnow(),
        "profile": {
            "name": profile.name,
            "age": profile.age or age_from_dob(profile.date_of_birth),
            "sex": profile.sex,
            "height_cm": profile.height_cm,
            "weight": profile.weight,
            "units": profile.units,
            "primary_goal": profile.primary_goal,
            "secondary_goal": profile.secondary_goal,
            "goal_event_name": profile.goal_event_name,
            "goal_event_date": profile.goal_event_date.isoformat()
            if profile.goal_event_date
            else None,
            "goal_metric": profile.goal_metric,
            "equipment": profile.equipment,
            "days_per_week": profile.days_per_week,
            "workout_duration_minutes": profile.workout_duration_minutes,
            "weekly_minutes_budget": profile.weekly_minutes_budget,
            "preferred_workout_time": profile.preferred_workout_time,
            "injuries_limitations": profile.injuries_limitations,
            "fitness_level": profile.fitness_level,
            "training_history_months": profile.training_history_months,
            "current_weekly_volume": load_json_column(profile.current_weekly_volume),
            "longest_recent_session": profile.longest_recent_session,
            "race_prs": profile.race_prs,
            "exercises_hate": profile.exercises_hate,
            "exercises_love": profile.exercises_love,
            "ftp_watts": physiology.get("ftp_watts"),
            "lthr_bpm": physiology.get("lthr_bpm"),
            "max_hr_bpm": physiology.get("max_hr_bpm"),
            "sports": [
                {
                    "sport": row.sport,
                    "priority": row.priority,
                    "experience_level": row.experience_level,
                    "weekly_preference_days": row.weekly_preference_days,
                }
                for row in sports
            ],
            "consents": {
                "ai_coaching": bool(consent.ai_coaching) if consent else False,
                "health_data": bool(consent.health_data) if consent else False,
                "research": bool(consent.research) if consent else False,
            },
        },
        "physiology": physiology,
        "readiness_flags": readiness_flags,
        "safety": safety,
        "recent_activities": compact_rows,
        "focal_sessions": focal_sessions,
        "coros": {
            "connected": connection is not None,
            "last_synced_at": connection.last_synced_at.isoformat()
            if connection and connection.last_synced_at
            else None,
            "latest_health": {
                "metric_date": health_rows[0].metric_date.isoformat(),
                "sleep_score": health_rows[0].sleep_score,
                "sleep_duration_min": health_rows[0].sleep_duration_min,
                "deep_sleep_pct": health_rows[0].deep_sleep_pct,
                "rem_sleep_pct": health_rows[0].rem_sleep_pct,
                "light_sleep_pct": health_rows[0].light_sleep_pct,
                "nap_duration_min": health_rows[0].nap_duration_min,
                "bedtime": health_rows[0].bedtime,
                "wake_time": health_rows[0].wake_time,
                "hrv": health_rows[0].hrv,
                "hrv_assessment": health_rows[0].hrv_assessment,
                "stress": health_rows[0].stress,
                "resting_heart_rate": health_rows[0].resting_heart_rate,
                "steps": health_rows[0].steps,
                "calories": health_rows[0].calories,
                "avg_heart_rate": health_rows[0].avg_heart_rate,
            }
            if health_rows
            else None,
            "health_trend": [
                {
                    "metric_date": row.metric_date.isoformat(),
                    "sleep_score": row.sleep_score,
                    "sleep_duration_min": row.sleep_duration_min,
                    "deep_sleep_pct": row.deep_sleep_pct,
                    "rem_sleep_pct": row.rem_sleep_pct,
                    "hrv": row.hrv,
                    "stress": row.stress,
                    "resting_heart_rate": row.resting_heart_rate,
                    "steps": row.steps,
                    "calories": row.calories,
                    "avg_heart_rate": row.avg_heart_rate,
                }
                for row in health_rows
            ],
            "fitness": {
                "vo2max": fitness.vo2max,
                "threshold_pace": fitness.threshold_pace,
                "running_performance": fitness.running_performance,
                "race_predictions": race_preds,
                "recovery_pct": fitness.recovery_pct,
                "recovery_level": fitness.recovery_level,
                "recovery_full_at": fitness.recovery_full_at,
            }
            if fitness
            else None,
            "training_load": {
                "short_load": load.short_load,
                "long_load": load.long_load,
                "load_ratio": load.load_ratio,
                "daily_comments": comments,
            }
            if load
            else None,
            "schedule": [
                {
                    "schedule_date": item.schedule_date.isoformat(),
                    "title": item.title,
                    "sport_type": item.sport_type,
                    "duration_min": item.duration_min,
                    "distance_m": item.distance_m,
                }
                for item in schedule
            ],
        },
    }

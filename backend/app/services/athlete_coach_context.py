"""Assemble a unified athlete context for future AI coaching."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Activity,
    AthleteProfile,
    CorosScheduleItem,
    DailyHealthMetric,
    FitnessAssessment,
    TrainingLoadSnapshot,
)
from app.services.coros_sync import get_coros_connection


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

    readiness_flags: list[str] = []
    if fitness and fitness.recovery_pct is not None:
        if fitness.recovery_pct < 40:
            readiness_flags.append("low_recovery")
        elif fitness.recovery_pct < 70:
            readiness_flags.append("moderate_recovery")
        else:
            readiness_flags.append("good_recovery")
    if health_rows:
        latest = health_rows[0]
        if latest.sleep_score is not None and latest.sleep_score < 60:
            readiness_flags.append("poor_sleep")
        if latest.stress is not None and latest.stress >= 70:
            readiness_flags.append("elevated_stress")
        if latest.hrv is not None and latest.hrv_assessment:
            readiness_flags.append(f"hrv_{str(latest.hrv_assessment).lower()}")
    if load and load.load_ratio is not None:
        if load.load_ratio >= 1.5:
            readiness_flags.append("high_training_load_ratio")
        elif load.load_ratio <= 0.8:
            readiness_flags.append("low_training_load_ratio")

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

    return {
        "athlete_profile_id": athlete_profile_id,
        "generated_at": datetime.utcnow(),
        "profile": {
            "name": profile.name,
            "age": profile.age,
            "weight": profile.weight,
            "primary_goal": profile.primary_goal,
            "secondary_goal": profile.secondary_goal,
            "equipment": profile.equipment,
            "days_per_week": profile.days_per_week,
            "workout_duration_minutes": profile.workout_duration_minutes,
            "preferred_workout_time": profile.preferred_workout_time,
            "injuries_limitations": profile.injuries_limitations,
            "fitness_level": profile.fitness_level,
            "exercises_hate": profile.exercises_hate,
            "exercises_love": profile.exercises_love,
        },
        "readiness_flags": readiness_flags,
        "recent_activities": [
            {
                "id": activity.id,
                "provider": activity.provider,
                "external_activity_id": activity.external_activity_id,
                "name": activity.name,
                "activity_date": activity.activity_date.isoformat(),
                "distance_m": activity.distance_m,
                "moving_time_s": activity.moving_time_s,
                "average_heartrate": activity.average_heartrate,
                "sport_type": activity.sport_type,
            }
            for activity in activities
        ],
        "coros": {
            "connected": connection is not None,
            "last_synced_at": connection.last_synced_at.isoformat()
            if connection and connection.last_synced_at
            else None,
            "latest_health": {
                "metric_date": health_rows[0].metric_date.isoformat(),
                "sleep_score": health_rows[0].sleep_score,
                "sleep_duration_min": health_rows[0].sleep_duration_min,
                "hrv": health_rows[0].hrv,
                "hrv_assessment": health_rows[0].hrv_assessment,
                "stress": health_rows[0].stress,
                "resting_heart_rate": health_rows[0].resting_heart_rate,
            }
            if health_rows
            else None,
            "health_trend": [
                {
                    "metric_date": row.metric_date.isoformat(),
                    "sleep_score": row.sleep_score,
                    "hrv": row.hrv,
                    "stress": row.stress,
                    "resting_heart_rate": row.resting_heart_rate,
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

"""Turn a golden-athlete dict into the exact context/safety shapes the coach uses.

No database rows are created: the harness feeds the same structures that
``build_athlete_coach_context`` would produce, so prompts are byte-identical to
production apart from the athlete data itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.services.coach_safety import (
    compose_safety_profile,
    injury_constraints_from_records,
    readiness_flags_from_signals,
)

SPORT_TO_ACTIVITY = {
    "running": "Run",
    "trail running": "TrailRun",
    "cycling": "Ride",
    "swimming": "Swim",
    "strength training": "WeightTraining",
    "walking / hiking": "Walk",
    "yoga / mobility": "Yoga",
    "rowing": "Rowing",
    "triathlon": "Run",
    "team sport": "Soccer",
}


@dataclass
class InjuryRecord:
    body_region: str
    condition: str | None
    status: str
    severity: str | None


def _load_summary(athlete: dict) -> dict:
    acute = int(athlete.get("recent_weekly_minutes") or 0)
    chronic = int(athlete.get("chronic_weekly_minutes") or acute)
    ratio = round(acute / chronic, 2) if chronic > 0 else None
    return {"acute_minutes": acute, "chronic_minutes": chronic, "minutes_acwr": ratio}


def _recent_activities(athlete: dict, today: date) -> list[dict]:
    """Synthesise a plausible 4-week history matching the stated weekly volume."""
    weekly = int(athlete.get("recent_weekly_minutes") or 0)
    if weekly <= 0:
        return []
    rng = random.Random(athlete["id"])
    primary = [sport for sport, priority, _ in athlete["sports"] if priority == "primary"]
    sessions_per_week = max(1, athlete["days_per_week"])
    per_session = max(15, round(weekly / sessions_per_week))

    activities = []
    for week in range(4):
        for index in range(sessions_per_week):
            day = today - timedelta(days=week * 7 + index + 1)
            sport = primary[index % len(primary)] if primary else "Running"
            minutes = max(15, round(per_session * rng.uniform(0.7, 1.25)))
            is_endurance = sport.lower() not in {"strength training", "yoga / mobility"}
            activities.append(
                {
                    "activity_date": datetime.combine(
                        day, datetime.min.time()
                    ).isoformat(),
                    "sport_type": SPORT_TO_ACTIVITY.get(sport.lower(), sport),
                    "distance_m": round(minutes * 60 * rng.uniform(2.4, 3.4)) if is_endurance else None,
                    "moving_time_s": minutes * 60,
                    "average_heartrate": round(rng.uniform(128, 152)) if is_endurance else None,
                }
            )
    activities.sort(key=lambda item: item["activity_date"], reverse=True)
    return activities


def build_case(athlete: dict, today: date | None = None) -> dict:
    """Return ``{"context", "safety", "sports"}`` for one golden athlete."""
    today = today or date.today()
    health = athlete.get("health") or {}
    injuries = [
        InjuryRecord(body_region=region, condition=None, status=status, severity=severity)
        for region, status, severity in athlete["injuries"]
    ]
    injury_summary = injury_constraints_from_records(injuries)

    load = _load_summary(athlete)
    load_ratio = load["minutes_acwr"]
    readiness_flags = readiness_flags_from_signals(
        sleep_score=health.get("sleep_score"),
        stress=health.get("stress"),
        hrv=health.get("hrv"),
        hrv_assessment=health.get("hrv_assessment"),
        load_ratio=load_ratio,
    )

    weekly_budget = athlete["days_per_week"] * athlete["session_min"]
    safety = compose_safety_profile(
        days_per_week=athlete["days_per_week"],
        session_minutes=athlete["session_min"],
        weekly_minutes_budget=weekly_budget,
        fitness_level=athlete["fitness_level"],
        injuries=injury_summary,
        readiness_flags=readiness_flags,
        load=load,
        latest_health_date=today.isoformat() if health else None,
    )

    goal_date = (
        (today + timedelta(days=athlete["event_in_days"])).isoformat()
        if athlete.get("event_in_days")
        else None
    )
    sports = [
        {
            "sport": sport,
            "priority": priority,
            "experience_level": level,
            "weekly_preference_days": None,
        }
        for sport, priority, level in athlete["sports"]
    ]

    context = {
        "athlete_profile_id": 0,
        "generated_at": datetime.combine(today, datetime.min.time()),
        "profile": {
            "name": "Synthetic Athlete",
            "age": athlete["age"],
            "sex": athlete["sex"],
            "height_cm": athlete["height_cm"],
            "weight": athlete["weight"],
            "units": "metric",
            "primary_goal": athlete["primary_goal"],
            "secondary_goal": None,
            "goal_event_name": None,
            "goal_event_date": goal_date,
            "goal_metric": None,
            "equipment": athlete["equipment"],
            "days_per_week": athlete["days_per_week"],
            "workout_duration_minutes": athlete["session_min"],
            "weekly_minutes_budget": weekly_budget,
            "preferred_workout_time": None,
            "injuries_limitations": ", ".join(
                f"{region} ({status})" for region, status, _ in athlete["injuries"]
            )
            or None,
            "fitness_level": athlete["fitness_level"],
            "training_history_months": athlete["training_history_months"],
            "current_weekly_volume": None,
            "longest_recent_session": None,
            "race_prs": None,
            "exercises_hate": None,
            "exercises_love": None,
            "sports": sports,
            "consents": {"ai_coaching": True, "health_data": True, "research": False},
        },
        "readiness_flags": readiness_flags,
        "safety": safety,
        "recent_activities": _recent_activities(athlete, today),
        "coros": {
            "connected": bool(health),
            "latest_health": (
                {
                    "metric_date": today.isoformat(),
                    "sleep_score": health.get("sleep_score"),
                    "hrv": health.get("hrv"),
                    "hrv_assessment": health.get("hrv_assessment"),
                    "stress": health.get("stress"),
                    "resting_heart_rate": health.get("resting_heart_rate"),
                }
                if health
                else None
            ),
            "fitness": None,
            "training_load": {
                "acute_minutes": load["acute_minutes"],
                "chronic_minutes": load["chronic_minutes"],
                "load_ratio": load_ratio,
            },
            "schedule": [],
        },
    }

    return {
        "context": context,
        "safety": safety,
        "sports": [sport for sport, priority, _ in athlete["sports"] if priority == "primary"],
    }

"""End-to-end smoke test of the coach pipeline against a throwaway SQLite database.

    python scripts/ai_eval/smoke_coach.py

Creates one athlete with consent, an injury, some activity history, then exercises
plan generation, daily advice, chat (normal + red flag), and the schedule-facing
planned-workout query. Runs entirely on deterministic templates unless a provider
key is configured.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DB_PATH = Path(tempfile.gettempdir()) / "aal_coach_smoke.sqlite3"
DB_PATH.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Activity,
    AthleteConsent,
    AthleteInjury,
    AthleteProfile,
    AthleteSport,
    DailyHealthMetric,
)
from app.services.coach_ai import (  # noqa: E402
    chat_history,
    coach_chat,
    generate_daily_advice,
    generate_week_plan,
    get_active_plan,
    publish_plan_to_schedule,
    resolve_clock,
)
from app.services.schedule_completion import match_planned_workout_completions  # noqa: E402
from app.services.science_kb import ensure_corpus_loaded  # noqa: E402


def seed(db) -> AthleteProfile:
    profile = AthleteProfile(
        name="Smoke Tester",
        age=34,
        weight=72.0,
        height_cm=176.0,
        sex="female",
        fitness_level="Intermediate",
        days_per_week=4,
        workout_duration_minutes=50,
        weekly_minutes_budget=200,
        primary_goal="Half marathon under 1:50",
        primary_sports='["Running", "Strength training"]',
        equipment="Full gym",
        units="metric",
        onboarding_completed=True,
    )
    db.add(profile)
    db.flush()

    db.add_all(
        [
            AthleteSport(
                athlete_profile_id=profile.id,
                sport="Running",
                priority="primary",
                experience_level="Intermediate",
            ),
            AthleteSport(
                athlete_profile_id=profile.id,
                sport="Strength training",
                priority="secondary",
                experience_level="Beginner",
            ),
            AthleteInjury(
                athlete_profile_id=profile.id,
                body_region="Knee",
                status="active",
                severity="mild",
            ),
            AthleteConsent(
                athlete_profile_id=profile.id,
                ai_coaching=True,
                health_data=True,
                research=False,
                accepted_at=datetime.utcnow(),
            ),
            DailyHealthMetric(
                athlete_profile_id=profile.id,
                provider="coros",
                metric_date=date.today(),
                sleep_score=54,
                hrv=44,
                hrv_assessment="unbalanced",
                stress=72,
                resting_heart_rate=58,
            ),
        ]
    )

    for index in range(8):
        day = datetime.utcnow() - timedelta(days=index * 2 + 1)
        db.add(
            Activity(
                athlete_profile_id=profile.id,
                provider="strava",
                external_activity_id=f"smoke-{index}",
                name="Morning Run",
                sport_type="Run",
                activity_date=day,
                distance_m=9000,
                moving_time_s=2700,
                source_fit_file="smoke",
            )
        )
    db.commit()
    return profile


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_corpus_loaded(db)
        profile = seed(db)

        clock = resolve_clock("Asia/Kolkata")
        plan = generate_week_plan(
            db, profile, week_start=clock["week_start"], timezone_name="Asia/Kolkata"
        )
        workouts = plan["plan"]["workouts"]
        print(f"plan provider={plan['provider']} sessions={len(workouts)}")
        print(f"  weekly minutes={sum(w.get('duration_min') or 0 for w in workouts)}")
        for issue in plan["safety_issues"]:
            print(f"  safety[{issue['level']}] {issue['message']}")
        assert plan["plan_id"], "plan was not persisted"
        assert workouts, "plan has no sessions"
        assert not any(issue["level"] == "blocking" for issue in plan["safety_issues"])

        stored = get_active_plan(db, profile.id, clock["week_start"])
        assert stored and len(stored["plan"]["workouts"]) == len(workouts), "read-back mismatch"
        assert stored.get("on_schedule") is False
        print(f"read-back ok: {stored['plan']['title']}")

        unpublished = match_planned_workout_completions(db, profile.id)
        assert unpublished["scanned_plans"] == 0, "draft week leaked onto the schedule"
        published = publish_plan_to_schedule(db, profile, plan["plan_id"])
        assert published.get("on_schedule") is True
        print("schedule publish ok")

        advice = generate_daily_advice(db, profile, timezone_name="Asia/Kolkata")
        print(
            f"advice readiness={advice['readiness']['action']} "
            f"headline={advice['advice']['headline']!r}"
        )
        assert advice["readiness"]["action"] == "rest_or_mobility", "poor readiness not detected"

        normal = coach_chat(
            db, profile, "How should I pace my long run this week?", timezone_name="Asia/Kolkata"
        )
        print(f"chat provider={normal['provider']} escalate={normal['reply']['escalate']}")
        assert normal["reply"]["escalate"] is False

        flagged = coach_chat(db, profile, "I had chest pain and felt dizzy on today's run.")
        print(f"red flag: provider={flagged['provider']} escalate={flagged['reply']['escalate']}")
        assert flagged["provider"] == "safety-gate"
        assert flagged["reply"]["escalate"] is True

        history = chat_history(db, profile.id)
        assert len(history) == 4, f"expected 4 messages, got {len(history)}"

        matched = match_planned_workout_completions(db, profile.id)
        print(f"schedule linking: {matched}")

        print("\nSMOKE OK")
    finally:
        db.close()
        DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

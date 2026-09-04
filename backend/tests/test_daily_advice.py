"""Today advice is cached per day and only rewritten on new signals or Refresh."""

from __future__ import annotations

import copy
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import AthleteConsent, AthleteProfile, DailyHealthMetric  # noqa: E402
from app.services.coach_ai import advice_input_fingerprint, generate_daily_advice  # noqa: E402


def _base_context() -> dict:
    return {
        "coros": {
            "latest_health": {
                "metric_date": "2026-09-03",
                "sleep_score": 73,
                "sleep_duration_min": 420,
                "hrv": 51,
                "hrv_assessment": "balanced",
                "stress": 40,
                "resting_heart_rate": 52,
            },
            "fitness": {"recovery_pct": 82, "recovery_level": "high", "vo2max": 48},
            "training_load": {"short_load": 80, "long_load": 75, "load_ratio": 1.07},
        },
        "safety": {"readiness": {"action": "proceed"}},
        "readiness_flags": [],
        "recent_activities": [
            {"id": 9, "date": "2026-09-02", "name": "Easy run"},
        ],
    }


def test_fingerprint_is_stable():
    clock = {"local_date": "2026-09-03"}
    context = _base_context()
    assert advice_input_fingerprint(context, clock) == advice_input_fingerprint(
        copy.deepcopy(context), clock
    )


def test_fingerprint_changes_with_hrv_recovery_and_training():
    clock = {"local_date": "2026-09-03"}
    baseline = advice_input_fingerprint(_base_context(), clock)

    hrv = _base_context()
    hrv["coros"]["latest_health"]["hrv"] = 30
    assert advice_input_fingerprint(hrv, clock) != baseline

    recovery = _base_context()
    recovery["coros"]["fitness"]["recovery_pct"] = 40
    assert advice_input_fingerprint(recovery, clock) != baseline

    training = _base_context()
    training["recent_activities"] = [
        {"id": 10, "date": "2026-09-03", "name": "Threshold ride"}
    ]
    assert advice_input_fingerprint(training, clock) != baseline

    sleep = _base_context()
    sleep["coros"]["latest_health"]["sleep_score"] = 54
    assert advice_input_fingerprint(sleep, clock) != baseline


def test_generate_daily_advice_uses_cache_until_signals_change():
    from app.services import coach_ai as coach_ai_mod

    original = coach_ai_mod._call_provider
    coach_ai_mod._call_provider = lambda *args, **kwargs: None
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        profile = AthleteProfile(
            name="Cache Tester",
            age=32,
            weight=70.0,
            onboarding_completed=True,
        )
        db.add(profile)
        db.flush()
        db.add_all(
            [
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
                    sleep_score=78,
                    hrv=61,
                    hrv_assessment="balanced",
                    stress=32,
                    resting_heart_rate=50,
                ),
            ]
        )
        db.commit()

        first = generate_daily_advice(db, profile, timezone_name="UTC")
        assert first["cached"] is False
        headline = first["advice"]["headline"]

        second = generate_daily_advice(db, profile, timezone_name="UTC")
        assert second["cached"] is True
        assert second["advice"]["headline"] == headline

        forced = generate_daily_advice(db, profile, timezone_name="UTC", force=True)
        assert forced["cached"] is False

        health = (
            db.query(DailyHealthMetric)
            .filter(DailyHealthMetric.athlete_profile_id == profile.id)
            .first()
        )
        health.hrv = 28
        health.hrv_assessment = "unbalanced"
        db.commit()

        stale = generate_daily_advice(db, profile, timezone_name="UTC")
        assert stale["cached"] is False
    finally:
        coach_ai_mod._call_provider = original
        db.close()
        engine.dispose()


def run() -> None:
    tests = [
        test_fingerprint_is_stable,
        test_fingerprint_changes_with_hrv_recovery_and_training,
        test_generate_daily_advice_uses_cache_until_signals_change,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

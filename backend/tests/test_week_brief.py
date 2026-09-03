"""Week brief is cached per Monday week and rewritten on new load signals or Refresh."""

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
from app.models import Activity, AthleteConsent, AthleteProfile, DailyHealthMetric, TrainingLoadSnapshot  # noqa: E402
from app.services.coach_ai import generate_week_brief, week_brief_input_fingerprint  # noqa: E402


def _base_context() -> dict:
    return {
        "coros": {
            "latest_health": {"sleep_score": 73, "hrv": 51, "hrv_assessment": "balanced", "stress": 40},
            "fitness": {"recovery_pct": 82},
        },
        "safety": {
            "readiness": {"action": "proceed"},
            "load": {"minutes_acwr": 1.05},
        },
        "readiness_flags": [],
        "current_plan": {},
    }


def _distance() -> dict:
    return {
        "acwr": 1.12,
        "acute_load_km": 42.3,
        "chronic_load_km": 37.8,
        "weekly_volume_km": [28.0, 31.0, 36.0, 40.0, 33.0, 38.0, 41.0, 42.3],
    }


def test_week_fingerprint_is_stable():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    distance = _distance()
    assert week_brief_input_fingerprint(context, clock, distance) == week_brief_input_fingerprint(
        copy.deepcopy(context), clock, copy.deepcopy(distance)
    )


def test_week_fingerprint_changes_with_acwr_and_recovery():
    clock = {"week_start_iso": "2026-09-01"}
    baseline = week_brief_input_fingerprint(_base_context(), clock, _distance())

    spiked = _distance()
    spiked["acwr"] = 1.62
    assert week_brief_input_fingerprint(_base_context(), clock, spiked) != baseline

    tired = _base_context()
    tired["coros"]["fitness"]["recovery_pct"] = 40
    assert week_brief_input_fingerprint(tired, clock, _distance()) != baseline


def test_week_fingerprint_is_split_by_topic():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["training_load"] = {"short_load": 80, "long_load": 75, "load_ratio": 1.07}
    volume = week_brief_input_fingerprint(context, clock, _distance(), "volume")
    load = week_brief_input_fingerprint(context, clock, _distance(), "load")
    assert volume != load

    only_ratio = copy.deepcopy(context)
    only_ratio["coros"]["training_load"]["load_ratio"] = 1.61
    assert week_brief_input_fingerprint(only_ratio, clock, _distance(), "volume") == volume
    assert week_brief_input_fingerprint(only_ratio, clock, _distance(), "load") != load

    only_km = _distance()
    only_km["acwr"] = 1.62
    assert week_brief_input_fingerprint(context, clock, only_km, "load") == load
    assert week_brief_input_fingerprint(context, clock, only_km, "volume") != volume


def test_generate_week_brief_uses_cache_until_signals_change():
    from app.services import coach_ai as coach_ai_mod

    original = coach_ai_mod._call_provider
    coach_ai_mod._call_provider = lambda *args, **kwargs: None
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        profile = AthleteProfile(
            name="Week Brief Tester",
            age=32,
            weight=70.0,
            onboarding_completed=True,
        )
        db.add(profile)
        db.flush()
        db.add(
            AthleteConsent(
                athlete_profile_id=profile.id,
                ai_coaching=True,
                health_data=True,
                research=False,
                accepted_at=datetime.utcnow(),
            )
        )
        db.add(
            DailyHealthMetric(
                athlete_profile_id=profile.id,
                provider="coros",
                metric_date=date.today(),
                sleep_score=78,
                hrv=61,
                hrv_assessment="balanced",
                stress=32,
                resting_heart_rate=50,
            )
        )
        db.commit()

        first = generate_week_brief(db, profile, timezone_name="UTC")
        assert first["cached"] is False
        assert first["scope"] == "week"
        headline = first["advice"]["headline"]
        assert headline

        second = generate_week_brief(db, profile, timezone_name="UTC")
        assert second["cached"] is True
        assert second["advice"]["headline"] == headline

        forced = generate_week_brief(db, profile, timezone_name="UTC", force=True)
        assert forced["cached"] is False

        db.add(
            Activity(
                athlete_profile_id=profile.id,
                provider="strava",
                external_activity_id="week-brief-1",
                name="Long run",
                activity_date=datetime.utcnow(),
                distance_m=18000,
                moving_time_s=5400,
                source_fit_file="test.fit",
            )
        )
        db.commit()

        stale = generate_week_brief(db, profile, timezone_name="UTC")
        assert stale["cached"] is False
        assert stale["topic"] == "volume"

        db.add(
            TrainingLoadSnapshot(
                athlete_profile_id=profile.id,
                provider="coros",
                snapshot_at=datetime.utcnow(),
                short_load=88,
                long_load=70,
                load_ratio=1.26,
                daily_comments_json='[{"date":"2026-09-01","comment":"Productive week","load_ratio":1.26}]',
            )
        )
        db.commit()

        volume_again = generate_week_brief(db, profile, timezone_name="UTC", topic="volume")
        load_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="load")
        assert volume_again["cached"] is True
        assert load_brief["cached"] is False
        assert load_brief["topic"] == "load"
        assert load_brief["advice"]["headline"] != volume_again["advice"]["headline"]
        assert "Short-term load" in (load_brief["advice"]["recommendation"] or "")

        load_again = generate_week_brief(db, profile, timezone_name="UTC", topic="load")
        assert load_again["cached"] is True
    finally:
        coach_ai_mod._call_provider = original
        db.close()
        engine.dispose()


def run() -> None:
    tests = [
        test_week_fingerprint_is_stable,
        test_week_fingerprint_changes_with_acwr_and_recovery,
        test_week_fingerprint_is_split_by_topic,
        test_generate_week_brief_uses_cache_until_signals_change,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

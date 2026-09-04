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
from app.services.coach_ai import generate_week_brief, health_brief_off_topic, week_brief_input_fingerprint  # noqa: E402
from app.services.coach_templates import (  # noqa: E402
    build_template_daily_brief,
    build_template_hrv_brief,
    build_template_rhr_brief,
    build_template_sleep_brief,
    build_template_stress_brief,
)


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


def test_stress_fingerprint_tracks_stress_not_distance():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["health_trend"] = [
        {"metric_date": "2026-09-01", "stress": 40},
        {"metric_date": "2026-08-31", "stress": 38},
    ]
    baseline = week_brief_input_fingerprint(context, clock, _distance(), "stress")
    spiked = _distance()
    spiked["acwr"] = 1.8
    assert week_brief_input_fingerprint(context, clock, spiked, "stress") == baseline
    jumped = copy.deepcopy(context)
    jumped["coros"]["latest_health"]["stress"] = 78
    assert week_brief_input_fingerprint(jumped, clock, _distance(), "stress") != baseline
    assert week_brief_input_fingerprint(context, clock, _distance(), "stress") != week_brief_input_fingerprint(
        context, clock, _distance(), "hrv"
    )
    assert week_brief_input_fingerprint(context, clock, _distance(), "stress") != week_brief_input_fingerprint(
        context, clock, _distance(), "volume"
    )


def test_sleep_fingerprint_tracks_sleep_not_distance():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["latest_health"]["sleep_duration_min"] = 420
    context["coros"]["health_trend"] = [
        {"metric_date": "2026-09-01", "sleep_duration_min": 420, "sleep_score": 78},
        {"metric_date": "2026-08-31", "sleep_duration_min": 400, "sleep_score": 74},
    ]
    baseline = week_brief_input_fingerprint(context, clock, _distance(), "sleep")
    spiked = _distance()
    spiked["acwr"] = 1.8
    assert week_brief_input_fingerprint(context, clock, spiked, "sleep") == baseline
    short = copy.deepcopy(context)
    short["coros"]["latest_health"]["sleep_duration_min"] = 280
    assert week_brief_input_fingerprint(short, clock, _distance(), "sleep") != baseline
    assert week_brief_input_fingerprint(context, clock, _distance(), "sleep") != week_brief_input_fingerprint(
        context, clock, _distance(), "hrv"
    )


def test_daily_fingerprint_tracks_steps_not_distance():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["latest_health"]["steps"] = 8420
    context["coros"]["latest_health"]["calories"] = 2140
    context["coros"]["health_trend"] = [
        {"metric_date": "2026-09-01", "steps": 8420, "calories": 2140},
        {"metric_date": "2026-08-31", "steps": 7900, "calories": 2050},
    ]
    baseline = week_brief_input_fingerprint(context, clock, _distance(), "daily")
    spiked = _distance()
    spiked["acwr"] = 1.8
    assert week_brief_input_fingerprint(context, clock, spiked, "daily") == baseline
    jumped = copy.deepcopy(context)
    jumped["coros"]["latest_health"]["steps"] = 18200
    assert week_brief_input_fingerprint(jumped, clock, _distance(), "daily") != baseline
    assert week_brief_input_fingerprint(context, clock, _distance(), "daily") != week_brief_input_fingerprint(
        context, clock, _distance(), "volume"
    )
    assert week_brief_input_fingerprint(context, clock, _distance(), "daily") != week_brief_input_fingerprint(
        context, clock, _distance(), "stress"
    )


def test_rhr_fingerprint_tracks_rhr_not_distance():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["health_trend"] = [
        {"metric_date": "2026-09-01", "resting_heart_rate": 50},
        {"metric_date": "2026-08-31", "resting_heart_rate": 49},
    ]
    context["coros"]["latest_health"]["resting_heart_rate"] = 50
    baseline = week_brief_input_fingerprint(context, clock, _distance(), "rhr")
    spiked = _distance()
    spiked["acwr"] = 1.8
    assert week_brief_input_fingerprint(context, clock, spiked, "rhr") == baseline
    jumped = copy.deepcopy(context)
    jumped["coros"]["latest_health"]["resting_heart_rate"] = 62
    assert week_brief_input_fingerprint(jumped, clock, _distance(), "rhr") != baseline
    assert week_brief_input_fingerprint(context, clock, _distance(), "rhr") != week_brief_input_fingerprint(
        context, clock, _distance(), "hrv"
    )
    assert week_brief_input_fingerprint(context, clock, _distance(), "rhr") != week_brief_input_fingerprint(
        context, clock, _distance(), "stress"
    )
    assert week_brief_input_fingerprint(context, clock, _distance(), "rhr") != week_brief_input_fingerprint(
        context, clock, _distance(), "volume"
    )


def test_hrv_fingerprint_tracks_hrv_not_distance():
    clock = {"week_start_iso": "2026-09-01"}
    context = _base_context()
    context["coros"]["health_trend"] = [
        {"metric_date": "2026-09-01", "hrv": 51},
        {"metric_date": "2026-08-31", "hrv": 54},
    ]
    baseline = week_brief_input_fingerprint(context, clock, _distance(), "hrv")
    spiked = _distance()
    spiked["acwr"] = 1.8
    assert week_brief_input_fingerprint(context, clock, spiked, "hrv") == baseline
    dropped = copy.deepcopy(context)
    dropped["coros"]["latest_health"]["hrv"] = 33
    dropped["coros"]["latest_health"]["hrv_assessment"] = "unbalanced"
    assert week_brief_input_fingerprint(dropped, clock, _distance(), "hrv") != baseline
    assert week_brief_input_fingerprint(context, clock, _distance(), "hrv") != week_brief_input_fingerprint(
        context, clock, _distance(), "volume"
    )


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
                sleep_duration_min=420,
                hrv=61,
                hrv_assessment="balanced",
                stress=32,
                resting_heart_rate=50,
                steps=8420,
                calories=2140,
                avg_heart_rate=72,
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

        hrv_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="hrv")
        assert hrv_brief["cached"] is False
        assert hrv_brief["topic"] == "hrv"
        assert hrv_brief["advice"]["headline"] != volume_again["advice"]["headline"]
        assert "ms" in (hrv_brief["advice"]["recommendation"] or "")

        stress_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="stress")
        assert stress_brief["cached"] is False
        assert stress_brief["topic"] == "stress"
        assert stress_brief["advice"]["headline"] != hrv_brief["advice"]["headline"]
        rec = stress_brief["advice"]["recommendation"] or ""
        assert "stress" in rec.lower()
        assert "ms" not in rec.lower()

        rhr_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="rhr")
        assert rhr_brief["cached"] is False
        assert rhr_brief["topic"] == "rhr"
        assert rhr_brief["advice"]["headline"] != stress_brief["advice"]["headline"]
        rhr_rec = rhr_brief["advice"]["recommendation"] or ""
        assert "bpm" in rhr_rec.lower()
        assert "ms" not in rhr_rec.lower()

        daily_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="daily")
        assert daily_brief["cached"] is False
        assert daily_brief["topic"] == "daily"
        assert daily_brief["advice"]["headline"] != rhr_brief["advice"]["headline"]
        daily_rec = daily_brief["advice"]["recommendation"] or ""
        assert "step" in daily_rec.lower()
        assert "ms" not in daily_rec.lower()

        sleep_brief = generate_week_brief(db, profile, timezone_name="UTC", topic="sleep")
        assert sleep_brief["cached"] is False
        assert sleep_brief["topic"] == "sleep"
        assert sleep_brief["advice"]["headline"] != daily_brief["advice"]["headline"]
        sleep_rec = sleep_brief["advice"]["recommendation"] or ""
        assert "sleep" in sleep_rec.lower() or "min" in sleep_rec.lower()
        assert "ms" not in sleep_rec.lower()

        for rec in (
            hrv_brief["advice"]["recommendation"],
            stress_brief["advice"]["recommendation"],
            rhr_brief["advice"]["recommendation"],
            daily_brief["advice"]["recommendation"],
            sleep_brief["advice"]["recommendation"],
        ):
            text = (rec or "").lower()
            assert "interval" not in text
            assert "train as planned" not in text
            assert "kilometre" not in text and "kilometer" not in text
    finally:
        coach_ai_mod._call_provider = original
        db.close()
        engine.dispose()


def test_health_brief_rejects_workouts_and_other_metrics():
    assert health_brief_off_topic(
        "sleep",
        {
            "headline": "Sleep is short",
            "recommendation": "Keep easy days and skip the intervals.",
            "session_adjustment": None,
            "rationale": "",
        },
    )
    assert health_brief_off_topic(
        "sleep",
        {
            "headline": "Sleep",
            "recommendation": "HRV is also low tonight.",
            "session_adjustment": None,
            "rationale": "",
        },
    )
    assert health_brief_off_topic(
        "hrv",
        {
            "headline": "HRV is low",
            "recommendation": "Train as planned if sleep was fine.",
            "session_adjustment": None,
            "rationale": "",
        },
    )
    assert not health_brief_off_topic(
        "sleep",
        {
            "headline": "Sleep is around your usual night",
            "recommendation": "Last night 420 min vs 7-day usual 400 min.",
            "session_adjustment": "Typical sleep duration is the useful zone on this page.",
            "rationale": "",
        },
    )


def test_health_templates_stay_on_metric():
    safety = {}
    ctx = {}
    cases = [
        (
            "hrv",
            build_template_hrv_brief(
                ctx, safety, {"hrv": 50, "avg_7d": 52, "ratio_vs_usual": 0.96, "hrv_assessment": "balanced"}
            ),
        ),
        (
            "stress",
            build_template_stress_brief(
                ctx, safety, {"stress": 32, "avg_7d": 30, "ratio_vs_usual": 1.07, "high_absolute": False}
            ),
        ),
        (
            "rhr",
            build_template_rhr_brief(
                ctx,
                safety,
                {"resting_heart_rate": 48, "avg_7d": 50, "ratio_vs_usual": 0.96, "delta_bpm": -2},
            ),
        ),
        (
            "daily",
            build_template_daily_brief(
                ctx,
                safety,
                {
                    "steps": 8000,
                    "avg_7d_steps": 7500,
                    "ratio_vs_usual": 1.07,
                    "calories": 2200,
                    "avg_heart_rate": 72,
                },
            ),
        ),
        (
            "sleep",
            build_template_sleep_brief(
                ctx,
                safety,
                {"sleep_duration_min": 420, "avg_7d_min": 400, "ratio_vs_usual": 1.05, "sleep_score": 78},
            ),
        ),
        ("hrv", build_template_hrv_brief(ctx, safety, {})),
        ("sleep", build_template_sleep_brief(ctx, safety, {})),
    ]
    for topic, advice in cases:
        assert not health_brief_off_topic(topic, advice), (topic, advice)


def run() -> None:
    tests = [
        test_week_fingerprint_is_stable,
        test_week_fingerprint_changes_with_acwr_and_recovery,
        test_week_fingerprint_is_split_by_topic,
        test_hrv_fingerprint_tracks_hrv_not_distance,
        test_stress_fingerprint_tracks_stress_not_distance,
        test_rhr_fingerprint_tracks_rhr_not_distance,
        test_daily_fingerprint_tracks_steps_not_distance,
        test_sleep_fingerprint_tracks_sleep_not_distance,
        test_generate_week_brief_uses_cache_until_signals_change,
        test_health_brief_rejects_workouts_and_other_metrics,
        test_health_templates_stay_on_metric,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

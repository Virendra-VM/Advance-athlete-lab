"""Embedding router + month/year period review packets."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.coach_ai import _stamp_message_routing, chat_history
from app.models import Activity, AthleteProfile, CoachMessage, DailyHealthMetric
from app.services.coach_intent import MONTH_REVIEW, WEEK_REVIEW, YEAR_REVIEW, classify_chat_intent
from app.services.coach_intent_embed import classify_with_embeddings
from app.services.period_review import (
    build_period_review_packet,
    review_period_window,
    template_period_review,
)


def test_embedding_long_tail_week_improvement():
    decision = classify_with_embeddings("how much have I improved over the last 7 days")
    assert decision is not None
    assert decision.intent == WEEK_REVIEW


def test_structural_plus_embed_long_tail_phrases():
    assert (
        classify_chat_intent("how much have I improved over the last 7 days", use_llm=False)
        == WEEK_REVIEW
    )
    assert (
        classify_chat_intent("how's my training been this past week", use_llm=False)
        == WEEK_REVIEW
    )


def test_review_period_windows():
    clock = {"today": date(2026, 9, 16), "week_start": date(2026, 9, 14)}
    start, end, label = review_period_window(clock, "analyse last month", horizon="month")
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)
    assert "last" in label

    start, end, _ = review_period_window(clock, "how was this year", horizon="year")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 9, 16)


def test_template_period_review_month_not_a_week_plan():
    reply = template_period_review(
        "How did I do this month?",
        {"load": {"minutes_acwr": 0.91}},
        [],
        packet={
            "horizon": "month",
            "window": {"start": "2026-08-01", "end": "2026-08-31", "label": "last calendar month"},
            "totals": {"sessions": 12, "minutes": 540, "quality_days": 2},
            "buckets": [
                {
                    "key": "2026-08-03",
                    "label": "2026-08-03 → 2026-08-09",
                    "sessions": 3,
                    "minutes": 120,
                    "quality": 1,
                }
            ],
            "recovery": {"avg_sleep_score": 75, "avg_hrv": 54},
            "coverage_note": "Synced files only.",
        },
        horizon="month",
    )
    text = reply["reply"]
    assert reply["intent"] == MONTH_REVIEW
    assert "🧭 MONTH GRADE" in text
    assert "📅 WHAT LANDED" in text
    assert "REVISED WEEK" not in text
    assert "Add to Schedule" not in text
    assert "| Week |" in text


def test_build_period_packet_from_activities():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        profile = AthleteProfile(name="Period QA", age=30, weight=70.0)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        db.add(
            Activity(
                athlete_profile_id=profile.id,
                provider="coros",
                external_activity_id="1",
                name="Threshold Ride",
                activity_date=datetime(2026, 8, 12, 6, 0),
                distance_m=40000,
                moving_time_s=3600,
                sport_type="Ride",
                source_fit_file="x.fit",
            )
        )
        db.add(
            DailyHealthMetric(
                athlete_profile_id=profile.id,
                provider="coros",
                metric_date=date(2026, 8, 12),
                sleep_score=80,
                hrv=55,
                resting_heart_rate=50,
            )
        )
        db.commit()
        clock = {"today": date(2026, 9, 16), "week_start": date(2026, 9, 14)}
        packet = build_period_review_packet(
            db,
            profile,
            {"safety": {"load": {"minutes_acwr": 0.9}}},
            clock,
            "analyse last month",
            horizon="month",
        )
        assert packet["totals"]["sessions"] == 1
        assert packet["window"]["start"] == "2026-08-01"
        assert packet["buckets"]
    finally:
        db.close()


def test_year_template_uses_month_rows():
    reply = template_period_review(
        "How did I do this year?",
        {"load": {}},
        [],
        packet={
            "window": {"start": "2026-01-01", "end": "2026-09-16", "label": "this year"},
            "totals": {"sessions": 80, "minutes": 4000, "quality_days": 18},
            "buckets": [
                {"key": "2026-01", "label": "Jan", "sessions": 10, "minutes": 400, "quality": 2}
            ],
            "recovery": {},
        },
        horizon="year",
    )
    assert reply["intent"] == YEAR_REVIEW
    assert "🧭 YEAR GRADE" in reply["reply"]
    assert "| Month |" in reply["reply"]


def test_intent_is_stamped_on_user_message():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        profile = AthleteProfile(name="Intent QA", age=30, weight=70.0)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        row = CoachMessage(
            athlete_profile_id=profile.id,
            role="user",
            content="How did I do this week?",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        _stamp_message_routing(db, row, WEEK_REVIEW, "week_debrief")
        history = chat_history(db, profile.id)
        assert history[0]["intent"] == WEEK_REVIEW
        assert history[0]["skill"] == "week_debrief"
    finally:
        db.close()

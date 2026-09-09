from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Activity, AthleteInjury, AthleteProfile
from app.services.periodization import build_season_context, generate_season_plan
from app.services.season_replan import (
    _phase_diff,
    _replan_summary,
    detect_replan_triggers,
    replan_season,
)


def _phase(phase_type, start, end, **extra):
    return {"phase_type": phase_type, "start_date": start, "end_date": end, **extra}


def test_phase_diff_shifted():
    before = [_phase("build", "2026-03-01", "2026-03-21")]
    after = [_phase("build", "2026-03-08", "2026-03-28")]
    diff = _phase_diff(before, after)
    assert len(diff) == 1
    assert diff[0]["change"] == "shifted"
    assert diff[0]["shift_days"] == 7


def test_phase_diff_reports_nothing_when_the_plan_is_unchanged():
    rows = [
        _phase("base", "2026-03-01", "2026-03-21"),
        _phase("recovery_week", "2026-03-22", "2026-03-28"),
        _phase("base", "2026-03-29", "2026-04-18"),
    ]
    assert _phase_diff(rows, [dict(row) for row in rows]) == []


def test_phase_diff_pairs_repeated_blocks_by_occurrence():
    """A season repeats base and recovery_week, so blocks pair up positionally.

    Keying on phase type alone compared the first base block against the last
    one and reported changes that were not there.
    """
    before = [
        _phase("base", "2026-03-01", "2026-03-21"),
        _phase("recovery_week", "2026-03-22", "2026-03-28"),
        _phase("base", "2026-03-29", "2026-04-18"),
    ]
    after = [
        _phase("base", "2026-03-01", "2026-03-21"),
        _phase("recovery_week", "2026-03-22", "2026-03-28"),
        _phase("base", "2026-03-29", "2026-04-25"),
    ]
    diff = _phase_diff(before, after)
    assert len(diff) == 1
    assert diff[0]["phase_type"] == "base"
    assert diff[0]["occurrence"] == 2
    assert diff[0]["after_end"] == "2026-04-25"


def test_phase_diff_reports_dropped_and_added_blocks():
    before = [
        _phase("base", "2026-03-01", "2026-03-21"),
        _phase("recovery_week", "2026-03-22", "2026-03-28"),
    ]
    after = [_phase("base", "2026-03-01", "2026-03-28")]
    changes = {(row["phase_type"], row["change"]) for row in _phase_diff(before, after)}
    assert ("recovery_week", "removed") in changes
    assert ("base", "shifted") in changes


def test_replan_summary_rolls_blocks_up_into_phase_totals():
    before = [
        _phase("base", "2026-03-02", "2026-03-22"),
        _phase("build", "2026-03-23", "2026-04-19"),
    ]
    after = [
        _phase("base", "2026-03-02", "2026-03-29"),
        _phase("build", "2026-03-30", "2026-04-19"),
    ]
    summary = " ".join(_replan_summary(before, after))
    assert "Base: 3 → 4 weeks" in summary
    assert "Build: 4 → 3 weeks" in summary
    assert "Build now starts 2026-03-30" in summary
    assert "7 days later" in summary


def test_replan_summary_says_so_when_only_the_detail_moved():
    rows = [_phase("base", "2026-03-02", "2026-03-22")]
    summary = _replan_summary(rows, [dict(row) for row in rows])
    assert len(summary) == 1
    assert "unchanged" in summary[0]


def test_detect_replan_triggers_empty_without_db(monkeypatch):
    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def count(self):
            return 0

        def join(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return []

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    profile = type("Profile", (), {"id": 1})()
    triggers = detect_replan_triggers(FakeDb(), profile, as_of=date(2026, 6, 1))
    assert triggers == []


# ------------------------------------------------------- plan integrity (live DB)

SEASON_START = date(2026, 9, 7)  # a Monday
A_RACE = SEASON_START + timedelta(weeks=20)


def _seeded_session(*, injured: bool):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    profile = AthleteProfile(
        name="Replan Tester",
        age=38,
        weight=71.0,
        fitness_level="intermediate",
        workout_duration_minutes=60,
        days_per_week=5,
        onboarding_completed=True,
        primary_goal="Train for an event",
        goal_event_name="Autumn Marathon",
        goal_event_date=A_RACE,
        goal_metric="3:30:00",
    )
    db.add(profile)
    db.flush()
    for week in range(6):
        day = SEASON_START - timedelta(days=7 * week + 2)
        db.add(
            Activity(
                athlete_profile_id=profile.id,
                provider="strava",
                external_activity_id=f"act-{week}",
                name="Long run",
                activity_date=date(day.year, day.month, day.day),
                distance_m=18000.0,
                moving_time_s=110 * 60,
                sport_type="Run",
                source_fit_file="test",
            )
        )
    if injured:
        db.add(
            AthleteInjury(
                athlete_profile_id=profile.id,
                body_region="knee",
                condition="patellar tendinopathy",
                status="active",
                severity="moderate",
            )
        )
    db.flush()
    return db, profile


def _assert_plan_is_sound(ctx, plan, label):
    phases = ctx["phases"]
    assert phases, label
    for prev, nxt in zip(phases, phases[1:]):
        prev_end = date.fromisoformat(prev["end_date"])
        nxt_start = date.fromisoformat(nxt["start_date"])
        assert nxt_start == prev_end + timedelta(days=1), (
            f"{label}: {prev['phase_type']} {prev['end_date']} then "
            f"{nxt['phase_type']} {nxt['start_date']}"
        )
    tapers = [row for row in phases if row["phase_type"] == "taper"]
    assert tapers, f"{label}: no taper"
    assert tapers[-1]["end_date"] == A_RACE.isoformat(), label
    assert phases[-1]["phase_type"] == "restore", label
    assert plan.end_date.isoformat() == phases[-1]["end_date"], label


def test_generated_plan_is_sound_with_and_without_injury():
    for injured in (False, True):
        db, profile = _seeded_session(injured=injured)
        try:
            plan = generate_season_plan(db, profile, today=SEASON_START)
            db.flush()
            ctx = build_season_context(db, profile, on_date=SEASON_START)
            _assert_plan_is_sound(ctx, plan, f"generate injured={injured}")
        finally:
            db.close()


def test_replan_keeps_the_plan_sound_from_any_day_of_the_week():
    """The injury path used to shift phases forward by a week.

    That left recovery weeks overlapping their neighbours, a gap where the shift
    began, a taper landing after the A-race, and no restore phase at all.
    """
    for injured in (False, True):
        for offset in range(14, 21):  # covers every weekday the athlete may replan on
            db, profile = _seeded_session(injured=injured)
            try:
                plan = generate_season_plan(db, profile, today=SEASON_START)
                db.flush()
                as_of = SEASON_START + timedelta(days=offset)
                replan_season(db, profile, force=True, as_of=as_of)
                db.flush()
                db.refresh(plan)
                ctx = build_season_context(db, profile, on_date=as_of)
                _assert_plan_is_sound(ctx, plan, f"replan +{offset}d injured={injured}")
            finally:
                db.close()


def test_replan_does_not_shrink_peak_as_the_race_approaches():
    """Peak is anchored to the A-race, so a shorter runway must not eat into it."""
    db, profile = _seeded_session(injured=False)
    try:
        generate_season_plan(db, profile, today=SEASON_START)
        db.flush()

        def peak_weeks(on_date):
            ctx = build_season_context(db, profile, on_date=on_date)
            return sum(
                row["week_count"]
                for row in ctx["phases"]
                if row["phase_type"] == "peak"
            )

        before = peak_weeks(SEASON_START)
        as_of = SEASON_START + timedelta(days=28)
        replan_season(db, profile, force=True, as_of=as_of)
        db.flush()
        assert peak_weeks(as_of) == before
    finally:
        db.close()


def test_replan_reports_a_readable_summary_alongside_the_block_diff():
    db, profile = _seeded_session(injured=True)
    try:
        generate_season_plan(db, profile, today=SEASON_START)
        db.flush()
        result = replan_season(
            db, profile, force=True, as_of=SEASON_START + timedelta(days=21)
        )
        db.flush()
        assert result["replanned"] is True
        if result["diff"]:
            assert result["summary"]
            assert all(isinstance(line, str) and line for line in result["summary"])
    finally:
        db.close()

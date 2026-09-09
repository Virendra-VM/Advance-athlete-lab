"""Calendar placement for recovery weeks keeps the A-race covered."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402
from app.models import AthleteProfile  # noqa: E402
from app.services.periodization import (  # noqa: E402
    generate_season_plan,
    get_phases_for_plan,
    monday_of,
    shift_recovery_phase_to_week,
)


def _open():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _profile_with_plan(db, *, today: date, weeks: int = 20):
    profile = AthleteProfile(
        name="Shift Tester",
        age=32,
        weight=70.0,
        onboarding_completed=True,
        fitness_level="intermediate",
        primary_goal="run a marathon",
        goal_event_name="City Marathon",
        goal_event_date=today + timedelta(weeks=weeks),
        goal_metric="sub 3:30",
        workout_duration_minutes=60,
    )
    db.add(profile)
    db.flush()
    plan = generate_season_plan(db, profile, today=today)
    db.commit()
    return profile, plan


def _assert_contiguous(phases):
    for prev, nxt in zip(phases, phases[1:]):
        assert nxt.start_date == prev.end_date + timedelta(days=1)


def test_shift_recovery_one_week_earlier():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today)
        phases = get_phases_for_plan(db, plan.id)
        recovery = next(row for row in phases if row.phase_type == "recovery_week")
        target = monday_of(recovery.start_date - timedelta(days=7))
        race_end = next(row for row in phases if row.phase_type == "taper").end_date

        shift_recovery_phase_to_week(db, profile, recovery.id, target, today=today)
        db.commit()

        after = get_phases_for_plan(db, plan.id)
        _assert_contiguous(after)
        moved = next(row for row in after if row.id == recovery.id)
        assert moved.start_date == target
        assert next(row for row in after if row.phase_type == "taper").end_date == race_end
    finally:
        db.close()
        engine.dispose()


def test_shift_recovery_rejects_non_recovery_phases():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today)
        phases = get_phases_for_plan(db, plan.id)
        base = next(row for row in phases if row.phase_type == "base")
        try:
            shift_recovery_phase_to_week(db, profile, base.id, base.start_date, today=today)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "recovery" in str(exc).lower()
    finally:
        db.close()
        engine.dispose()


def run() -> None:
    tests = [
        test_shift_recovery_one_week_earlier,
        test_shift_recovery_rejects_non_recovery_phases,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

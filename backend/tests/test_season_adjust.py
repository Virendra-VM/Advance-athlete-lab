"""Manual phase-week trades keep the A-race covered and phases contiguous."""

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
    adjust_phase_weeks,
    annotate_phase_adjustability,
    delete_season_phase,
    generate_season_plan,
    get_phases_for_plan,
)


def _open():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _profile_with_plan(db, *, today: date, weeks: int = 16):
    profile = AthleteProfile(
        name="Adjust Tester",
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
        assert nxt.start_date == prev.end_date + timedelta(days=1), (
            prev.phase_type,
            nxt.phase_type,
            prev.end_date,
            nxt.start_date,
        )


def test_growing_base_steals_from_a_later_block():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today)
        phases = get_phases_for_plan(db, plan.id)
        base = next(row for row in phases if row.phase_type == "base")
        before = {row.id: (row.start_date, row.end_date, row.week_count) for row in phases}
        race_end = next(row for row in phases if row.phase_type == "taper").end_date

        adjust_phase_weeks(db, profile, base.id, 1, today=today)
        db.commit()

        after = get_phases_for_plan(db, plan.id)
        _assert_contiguous(after)
        grown = next(row for row in after if row.id == base.id)
        assert grown.week_count == before[base.id][2] + 1
        assert grown.end_date == before[base.id][1] + timedelta(days=7)
        assert next(row for row in after if row.phase_type == "taper").end_date == race_end
        assert next(row for row in after if row.phase_type == "restore").start_date == race_end + timedelta(
            days=1
        )
        pre_before = sum(row.week_count for row in phases if row.phase_type != "restore")
        pre_after = sum(row.week_count for row in after if row.phase_type != "restore")
        assert pre_after == pre_before
    finally:
        db.close()
        engine.dispose()


def test_shrinking_hands_the_week_to_the_next_block():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today)
        phases = get_phases_for_plan(db, plan.id)
        base = next(row for row in phases if row.phase_type == "base")
        nxt = next(row for row in phases if row.sort_order == base.sort_order + 1)
        base_weeks = base.week_count
        next_weeks = nxt.week_count

        adjust_phase_weeks(db, profile, base.id, -1, today=today)
        db.commit()

        after = get_phases_for_plan(db, plan.id)
        _assert_contiguous(after)
        assert next(row for row in after if row.id == base.id).week_count == base_weeks - 1
        assert next(row for row in after if row.id == nxt.id).week_count == next_weeks + 1
    finally:
        db.close()
        engine.dispose()


def test_restore_and_finished_blocks_stay_locked():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today)
        phases = get_phases_for_plan(db, plan.id)
        restore = next(row for row in phases if row.phase_type == "restore")
        try:
            adjust_phase_weeks(db, profile, restore.id, 1, today=today)
            raise AssertionError("restore should be locked")
        except ValueError as exc:
            assert "Restore" in str(exc) or "later" in str(exc).lower() or "cannot" in str(exc).lower()

        # A phase that already ended cannot move.
        past = phases[0]
        try:
            adjust_phase_weeks(db, profile, past.id, 1, today=past.end_date + timedelta(days=1))
            raise AssertionError("finished phase should be locked")
        except ValueError:
            pass
    finally:
        db.close()
        engine.dispose()


def test_adjustability_flags_match_the_rules():
    rows = [
        {
            "id": 1,
            "phase_type": "base",
            "start_date": "2026-09-07",
            "end_date": "2026-10-04",
            "week_count": 4,
        },
        {
            "id": 2,
            "phase_type": "build",
            "start_date": "2026-10-05",
            "end_date": "2026-11-01",
            "week_count": 4,
        },
        {
            "id": 3,
            "phase_type": "taper",
            "start_date": "2026-11-02",
            "end_date": "2026-11-08",
            "week_count": 1,
        },
        {
            "id": 4,
            "phase_type": "restore",
            "start_date": "2026-11-09",
            "end_date": "2026-11-15",
            "week_count": 1,
        },
    ]
    annotated = annotate_phase_adjustability(rows, today=date(2026, 9, 7))
    assert annotated[0]["can_grow"] is True
    assert annotated[0]["can_shrink"] is True
    assert annotated[2]["can_grow"] is False  # nothing after taper but restore
    assert annotated[2]["can_shrink"] is False
    assert annotated[3]["can_grow"] is False
    assert annotated[3]["can_shrink"] is False

    # A block that would lose the week we are standing in cannot shrink.
    current_week = [
        {
            "id": 1,
            "phase_type": "base",
            "start_date": "2026-09-07",
            "end_date": "2026-09-13",
            "week_count": 2,
        },
        {
            "id": 2,
            "phase_type": "build",
            "start_date": "2026-09-14",
            "end_date": "2026-10-11",
            "week_count": 4,
        },
    ]
    now = annotate_phase_adjustability(current_week, today=date(2026, 9, 7))
    assert now[0]["can_shrink"] is False
    assert now[0]["can_grow"] is True


def test_delete_recovery_week_merges_into_next():
    engine, db = _open()
    try:
        today = date(2026, 9, 7)
        profile, plan = _profile_with_plan(db, today=today, weeks=20)
        phases = get_phases_for_plan(db, plan.id)
        recovery = next(row for row in phases if row.phase_type == "recovery_week")
        succ = phases[phases.index(recovery) + 1]
        succ_weeks_before = succ.week_count

        delete_season_phase(db, profile, recovery.id, merge_into="next", today=today)
        db.commit()

        after = get_phases_for_plan(db, plan.id)
        _assert_contiguous(after)
        assert all(row.phase_type != "recovery_week" or row.id != recovery.id for row in after)
        assert not any(row.id == recovery.id for row in after)
        merged = next(row for row in after if row.id == succ.id)
        assert merged.week_count == succ_weeks_before + recovery.week_count
        assert merged.start_date == recovery.start_date
    finally:
        db.close()
        engine.dispose()


def run() -> None:
    tests = [
        test_growing_base_steals_from_a_later_block,
        test_shrinking_hands_the_week_to_the_next_block,
        test_restore_and_finished_blocks_stay_locked,
        test_adjustability_flags_match_the_rules,
        test_delete_recovery_week_merges_into_next,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

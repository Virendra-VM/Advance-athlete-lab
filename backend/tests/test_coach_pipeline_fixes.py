"""Pipeline fixes: DIY Pass 1, executed Done stamps, REST today-only."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.autoregulation import apply_autoregulation_to_safety
from app.services.coach_safety import validate_plan
from app.services.coach_schedule_mode import (
    build_proposed_schedule_week,
    build_week_table_rows,
)
from app.services.diy_week_parser import (
    executed_by_day_from_context,
    has_diy_week_proposal,
    parse_diy_week_from_message,
    soft_cap_today_only,
    workouts_from_executed,
)


KOLHAPUR_DIY = (
    "done with the recovery week, which was in kolhapur. "
    "now we go into base week again. "
    "Yesterday i did an endurance ride. "
    "and today I'll be doing an mobility and Strength Training with Core. "
    "and tomorrow I'll do a Run in the morning of 8 km and in afternoon I'll do 1 hr endurance ride. "
    "On friday I'll do full body strength Training and on saturday Long run of 15 km "
    "and on sunday Long ride in mountain of 3 to 4 hr."
)


def _clock(*, today: date) -> dict:
    week_start = today - timedelta(days=today.weekday())
    return {
        "today": today,
        "week_start": week_start,
        "weekday": today.strftime("%A"),
        "weekday_index": today.weekday(),
        "local_date": today.isoformat(),
    }


def _safety(**overrides) -> dict:
    base = {
        "load": {"minutes_acwr": 0.74, "acute_minutes": 200, "chronic_minutes": 270},
        "readiness": {"action": "proceed", "reason": "Cleared"},
        "injuries": {
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        "max_session_minutes": 300,
        "max_hard_sessions": 2,
        "max_days_per_week": 6,
        "max_weekly_minutes": 600,
        "weekly_minutes_budget": 600,
        "typical_session_minutes": 45,
        "require_rest_day": True,
        "no_consecutive_hard_days": True,
    }
    base.update(overrides)
    return base


def _context() -> dict:
    return {
        "profile": {
            "primary_goal": "Train for an event",
            "sports": [
                {"sport": "Cycling", "priority": "primary"},
                {"sport": "Running", "priority": "secondary"},
            ],
            "days_per_week": 5,
            "workout_duration_minutes": 60,
        },
        "physiology": {"ftp_watts": 232, "lthr_bpm": 168},
        "season": {"has_plan": True, "current_phase": {"phase_type": "base"}},
        "recent_activities": [],
        "coros": {"latest_health": {"sleep_score": 57, "hrv": 50}},
    }


def test_has_diy_week_proposal_on_athlete_message():
    assert has_diy_week_proposal(KOLHAPUR_DIY) is True
    assert has_diy_week_proposal("let's plan this week") is False
    assert has_diy_week_proposal("Plan my week again with new FTP") is False


def test_parse_diy_week_kolhapur_shape():
    # Wednesday = today (2026-09-23)
    today = date(2026, 9, 23)
    clock = _clock(today=today)
    workouts = parse_diy_week_from_message(KOLHAPUR_DIY, clock)
    by_date: dict[str, list] = {}
    for item in workouts:
        by_date.setdefault(str(item["date"])[:10], []).append(item)

    assert "2026-09-22" in by_date  # yesterday endurance ride
    assert any("ride" in (w.get("title") or "").lower() or w.get("session_type") == "endurance"
               for w in by_date["2026-09-22"])

    today_rows = by_date["2026-09-23"]
    titles = " ".join(w.get("title") or "" for w in today_rows).lower()
    types = {w.get("session_type") for w in today_rows}
    assert "mobility" in types or "mobility" in titles
    assert "strength" in types or "strength" in titles

    thu = by_date["2026-09-24"]
    assert len(thu) >= 2
    thu_blob = " ".join(f"{w.get('title')} {w.get('sport')}" for w in thu).lower()
    assert "run" in thu_blob
    assert "ride" in thu_blob or "cycl" in thu_blob

    fri = by_date["2026-09-25"]
    assert any("strength" in (w.get("session_type") or "") for w in fri)

    sat = by_date["2026-09-26"]
    assert any(
        "15" in (w.get("title") or "") or (w.get("session_type") == "long" and "run" in (w.get("sport") or "").lower())
        for w in sat
    )

    sun = by_date["2026-09-27"]
    assert any(
        180 <= (w.get("duration_min") or 0) <= 240
        or "mountain" in (w.get("title") or "").lower()
        for w in sun
    )


def test_build_proposed_honors_diy_and_keeps_weekend():
    today = date(2026, 9, 23)
    clock = _clock(today=today)
    safety = _safety(
        readiness={
            "action": "rest_or_mobility",
            "reason": "Sleep scored 57",
            "max_hard_sessions_today": 0,
        },
        autoregulation={
            "call_level": "rest",
            "label": "🔴 REST / RESTORE",
            "directive": "Restore first",
        },
        todays_call={
            "call_level": "rest",
            "label": "🔴 REST / RESTORE",
            "directive": "Restore first",
        },
    )
    proposed = build_proposed_schedule_week(
        context=_context(),
        safety=safety,
        clock=clock,
        current_plan=None,
        message=KOLHAPUR_DIY,
    )
    assert proposed.get("diy_honored") is True
    assert proposed.get("selection_engine") == "diy-v1"

    by_date: dict[str, list] = {}
    for item in proposed.get("workouts") or []:
        by_date.setdefault(str(item["date"])[:10], []).append(item)

    # Today soft-capped to a single restore block.
    today_rows = by_date.get("2026-09-23", [])
    assert len(today_rows) == 1
    assert today_rows[0]["session_type"] in ("mobility", "rest", "easy")

    # Weekend preserved — not wiped to Sunday mobility.
    sat_blob = " ".join(
        f"{w.get('title')} {w.get('session_type')} {w.get('sport')}"
        for w in by_date.get("2026-09-26", [])
    ).lower()
    assert "run" in sat_blob or "long" in sat_blob

    sun_rows = by_date.get("2026-09-27", [])
    assert sun_rows
    sun_blob = " ".join(
        f"{w.get('title')} {w.get('session_type')} {w.get('duration_min')}"
        for w in sun_rows
    ).lower()
    assert "mountain" in sun_blob or "long" in sun_blob or any(
        (w.get("duration_min") or 0) >= 150 for w in sun_rows
    )
    assert not all(
        str(w.get("session_type") or "").lower() in {"mobility", "rest", "yoga"}
        for w in sun_rows
    )


def test_executed_days_stamp_done_not_missed():
    today = date(2026, 9, 23)
    week_start = date(2026, 9, 21)
    clock = _clock(today=today)
    context = _context()
    context["recent_activities"] = [
        {
            "date": "2026-09-21",
            "activity_date": "2026-09-21",
            "name": "Morning Yoga",
            "sport": "Yoga",
            "minutes": 40,
            "km": 0,
        },
        {
            "date": "2026-09-22",
            "activity_date": "2026-09-22",
            "name": "Endurance Ride",
            "sport": "Cycling",
            "minutes": 65,
            "km": 28,
        },
    ]
    proposed = build_proposed_schedule_week(
        context=context,
        safety=_safety(),
        clock=clock,
        current_plan=None,
        message="let's plan this week",
    )
    rows = build_week_table_rows(proposed, clock=clock, context=context)
    table = "\n".join(rows)
    assert "Morning Yoga" in table or "Yoga" in table
    assert "Endurance Ride" in table or "Cycling" in table
    # Secret rule column should say Done for those days, not Missed.
    monday = [line for line in rows if line.startswith("| Monday")][0]
    tuesday = [line for line in rows if line.startswith("| Tuesday")][0]
    assert "Done" in monday
    assert "Missed" not in monday
    assert "Done" in tuesday
    assert "Missed" not in tuesday


def test_rest_autoreg_does_not_zero_weekly_hard_budget():
    safety = _safety(max_hard_sessions=2)
    adjusted = apply_autoregulation_to_safety(
        safety,
        {
            "call_level": "rest",
            "directive": "Restore first",
            "downgrade_reasons": ["Sleep 5.5h"],
        },
    )
    assert adjusted["max_hard_sessions"] == 2
    assert adjusted["readiness"]["action"] == "rest_or_mobility"
    assert adjusted["readiness"]["max_hard_sessions_today"] == 0


def test_validate_plan_rest_only_touches_today():
    today = date.today()
    saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    if saturday <= today:
        saturday = today + timedelta(days=1)
    # Ensure saturday is a future day in the same week when possible.
    week_start = today - timedelta(days=today.weekday())
    saturday = week_start + timedelta(days=5)
    if saturday <= today:
        saturday = today + timedelta(days=2)

    safety = _safety(
        readiness={"action": "rest_or_mobility", "reason": "Sleep 57"},
        autoregulation={"call_level": "rest", "directive": "Restore"},
        todays_call={"call_level": "rest", "directive": "Restore"},
        max_hard_sessions=2,
    )
    plan = {
        "workouts": [
            {
                "date": today.isoformat(),
                "title": "Full-body strength",
                "session_type": "strength",
                "intensity": "RPE 6–7",
                "duration_min": 45,
                "sport": "Strength",
            },
            {
                "date": saturday.isoformat(),
                "title": "Long run (15 km)",
                "session_type": "long",
                "intensity": "Easy / conversational",
                "duration_min": 90,
                "sport": "Running",
            },
            {
                "date": (saturday + timedelta(days=1)).isoformat(),
                "title": "Long mountain ride",
                "session_type": "long",
                "intensity": "Easy / endurance",
                "duration_min": 210,
                "sport": "Cycling",
            },
        ]
    }
    result = validate_plan(plan, safety)
    by_date = {str(w["date"])[:10]: w for w in result["plan"]["workouts"]}
    today_row = by_date[today.isoformat()]
    assert today_row["session_type"] in ("mobility", "rest", "easy")
    sat_row = by_date[saturday.isoformat()]
    assert sat_row["session_type"] == "long"
    assert sat_row["title"] == "Long run (15 km)"


def test_soft_cap_today_only_leaves_sunday():
    today = date(2026, 9, 23)
    safety = _safety(
        readiness={"action": "rest_or_mobility", "reason": "Sleep 57"},
        autoregulation={"call_level": "rest", "directive": "Restore"},
    )
    workouts = [
        {
            "date": "2026-09-23",
            "title": "Strength Training with Core",
            "session_type": "strength",
            "duration_min": 45,
            "sport": "Strength",
            "intensity": "RPE 6–7",
        },
        {
            "date": "2026-09-27",
            "title": "Long mountain ride",
            "session_type": "long",
            "duration_min": 210,
            "sport": "Cycling",
            "intensity": "Easy / endurance",
        },
    ]
    capped = soft_cap_today_only(workouts, safety, today=today)
    by_date = {str(w["date"])[:10]: w for w in capped}
    assert by_date["2026-09-23"]["session_type"] in ("mobility", "easy")
    assert by_date["2026-09-27"]["title"] == "Long mountain ride"
    assert by_date["2026-09-27"]["duration_min"] == 210


def test_workouts_from_executed_helper():
    week_start = date(2026, 9, 21)
    executed = executed_by_day_from_context(
        {
            "recent_activities": [
                {
                    "date": "2026-09-22",
                    "name": "Endurance Ride",
                    "sport": "Cycling",
                    "minutes": 70,
                }
            ]
        },
        week_start=week_start,
    )
    rows = workouts_from_executed(executed, today=date(2026, 9, 23))
    assert len(rows) == 1
    assert rows[0]["completed"] is True
    assert rows[0]["title"] == "Endurance Ride"


def run() -> None:
    tests = [
        test_has_diy_week_proposal_on_athlete_message,
        test_parse_diy_week_kolhapur_shape,
        test_build_proposed_honors_diy_and_keeps_weekend,
        test_executed_days_stamp_done_not_missed,
        test_rest_autoreg_does_not_zero_weekly_hard_budget,
        test_validate_plan_rest_only_touches_today,
        test_soft_cap_today_only_leaves_sunday,
        test_workouts_from_executed_helper,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

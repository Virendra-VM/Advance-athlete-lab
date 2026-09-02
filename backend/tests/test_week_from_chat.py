"""Parse Athletic Director chat tables into persistable week plans."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.week_from_chat import parse_week_plan_from_text  # noqa: E402

ATHLETE_TABLE = """
📅 WEEK VERDICT
ACWR 1.02 is in range.
🗓️ REVISED WEEK
DAY	DATE	SESSION	SPORT	DURATION	INTENSITY	NOTES
Monday	2026-08-31	Easy running	Running	60 min	Easy	Missed
Tuesday	2026-09-01	Indoor cycling (quality)	Cycling	61 min	Hard	Done — quality slot 1/3 used
Wednesday	2026-09-02	Z1/Z2 Base Run + Hip/Spine Mobility	Running / Mobility	30 + 20 min	Easy	Prescribe today — 5 km cap
Thursday	2026-09-03	Power & Armor Protocol + Z2 Indoor Spin	Strength / Cycling	45 + 60 min	Moderate / Easy	AM: unilateral lower
Friday	2026-09-04	Active Recovery Spin + Deep Thoracic Decompression	Cycling / Mobility	40 + 15 min	Recovery	<125 W
Saturday	2026-09-05	Z2 Base Run + Football 11v11	Running / Football	60 + 60 min	Easy / Hard	Run capped 60 min
Sunday	2026-09-06	Long Z2 Endurance Ride	Cycling	180-210 min	Easy	Z2 only
⚠️ SAFETY GUARDRAILS
- No back-to-back hard days
"""

MARKDOWN_TABLE = """
🗓️ REVISED WEEK
| Day | Date | Session | Sport | Duration | Intensity | Notes |
|---|---|---|---|---|---|---|
| Monday | 2026-08-31 | Easy running | Running | 60 min | Easy | Missed |
| Tuesday | 2026-09-01 | Indoor cycling (quality) | Cycling | 61 min | Hard | Done |
| Wednesday | 2026-09-02 | Z1/Z2 Base Run + Hip/Spine Mobility | Running / Mobility | 30 + 20 min | Easy | Today |
| Thursday | 2026-09-03 | Power & Armor Protocol + Z2 Indoor Spin | Strength / Cycling | 45 + 60 min | Moderate / Easy | AM/PM |
| Friday | 2026-09-04 | Active Recovery Spin + Deep Thoracic Decompression | Cycling / Mobility | 40 + 15 min | Recovery | Easy |
| Saturday | 2026-09-05 | Z2 Base Run + Football 11v11 | Running / Football | 60 + 60 min | Easy / Hard | Match |
| Sunday | 2026-09-06 | Long Z2 Endurance Ride | Cycling | 180-210 min | Easy | Long |
"""


def test_parses_copied_director_table():
    plan = parse_week_plan_from_text(ATHLETE_TABLE, week_start=date(2026, 8, 31))
    assert plan is not None
    assert len(plan["workouts"]) == 11
    by_date = {}
    for workout in plan["workouts"]:
        by_date.setdefault(str(workout["date"]), []).append(workout)
    assert len(by_date["2026-09-03"]) == 2
    assert len(by_date["2026-09-05"]) == 2
    saturday = by_date["2026-09-05"]
    assert any("Football" in (item["title"] or "") for item in saturday)
    assert any(item["session_type"] == "cross-training" for item in saturday)
    sunday = by_date["2026-09-06"][0]
    assert sunday["duration_min"] == 195
    assert sunday["session_type"] == "long"


def test_parses_markdown_pipe_table():
    plan = parse_week_plan_from_text(MARKDOWN_TABLE, week_start=date(2026, 8, 31))
    assert plan is not None
    assert len(plan["workouts"]) == 11
    thursday = [item for item in plan["workouts"] if str(item["date"]) == "2026-09-03"]
    assert {item["session_type"] for item in thursday} == {"strength", "easy"}


CALL_TABLE = """
🟢 TODAY'S CALL
🟡 CAUTION / ABSORB
🗓️ REVISED WEEK
| Day | Session | Primary Focus | Intensity | Coach's Secret Rule |
|---|---|---|---|---|
| Monday | Easy running | Running | Easy | Missed |
| Tuesday | Indoor cycling (quality) | Cycling | Hard | Done |
| Wednesday | Z1/Z2 Base Run + Hip/Spine Mobility | Running / Mobility | Easy | If you can't sing, you're going too fast |
| Thursday | Power & Armor Protocol + Z2 Indoor Spin | Strength / Cycling | Moderate / Easy | Unilateral only. Spine stays a pillar. |
| Friday | Active Recovery Spin + Deep Thoracic Decompression | Cycling / Mobility | Recovery | Gossip pace only |
| Saturday | Z2 Base Run + Football 11v11 | Running / Football | Easy / Hard | Chaos load — legs already paid for |
| Sunday | Long Z2 Endurance Ride | Cycling | Easy | If you can't sing while moving, you're going too fast |
"""


def test_empty_text_returns_none():
    assert parse_week_plan_from_text("hello coach", week_start=date(2026, 8, 31)) is None


def test_parses_five_column_call_table():
    plan = parse_week_plan_from_text(CALL_TABLE, week_start=date(2026, 8, 31))
    assert plan is not None
    assert len(plan["workouts"]) == 11
    thursday = [item for item in plan["workouts"] if str(item["date"]) == "2026-09-03"]
    assert {item["session_type"] for item in thursday} == {"strength", "easy"}
    sunday = [item for item in plan["workouts"] if str(item["date"]) == "2026-09-06"][0]
    assert sunday["title"] == "Long Z2 Endurance Ride"
    assert "sing" in (sunday["description"] or "").lower()


def run() -> None:
    tests = [
        test_parses_copied_director_table,
        test_parses_markdown_pipe_table,
        test_parses_five_column_call_table,
        test_empty_text_returns_none,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

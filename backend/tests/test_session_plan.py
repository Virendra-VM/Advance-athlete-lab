"""Prescribed-vs-executed overlay for coach autopsies."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.session_plan import (  # noqa: E402
    align_laps_to_plan,
    build_session_plan_overlay,
    parse_prescribed_workout,
)
from app.services.session_telemetry import detect_chat_intent  # noqa: E402

ATHLETE_PASTE = """
You got it wrong coach, I had planned that workout and it was
1) 10 mins warmup
2) 3 mins at 175 w
3) 2 mins Rest at 125 w
4) 3 mins at 175 w
5) 2 mins Rest at 125 w

main set under and over

1) 2 mins at 200 w
2) 1 min at 260 w
3) 2 mins at 200 w
4) 1 min at 260 w
5) 2 mins at 200 w
6) 1 min at 260 w
7) 1 min at 280 w

repeat this set 3 times with no rest

and cool down of 10 mins

lap 12, 19, 26 are the VO2 max to finish the set got it,
lap 7 was part of the under and over
now go and analyse the workout
"""


def _colombia_laps() -> list[dict]:
    steps = [
        (600, 131),
        (180, 177),
        (120, 127),
        (180, 180),
        (120, 124),
    ]
    blocks = [
        [(120, 202), (60, 262), (120, 203), (60, 260), (120, 203), (60, 265), (60, 281)],
        [(120, 201), (60, 261), (120, 202), (60, 260), (120, 204), (60, 263), (60, 283)],
        [(120, 200), (60, 259), (120, 201), (60, 262), (120, 202), (60, 264), (60, 284)],
    ]
    for block in blocks:
        steps.extend(block)
    steps.append((600, 112))
    return [
        {"index": index, "label": f"Lap {index}", "duration_s": duration, "avg_power": watts}
        for index, (duration, watts) in enumerate(steps, start=1)
    ]


def test_parse_expands_three_main_blocks_to_27_steps():
    prescription = parse_prescribed_workout(ATHLETE_PASTE)
    assert prescription is not None
    assert prescription["repeats"] == 3
    assert prescription["main_steps_per_block"] == 7
    assert prescription["step_count"] == 27
    assert prescription["vo2_lap_overrides"] == [12, 19, 26]
    by_index = {step["index"]: step for step in prescription["steps"]}
    assert by_index[1]["role"] == "warmup"
    assert by_index[7]["role"] == "over"
    assert by_index[7]["target_w"] == 260
    assert by_index[12]["role"] == "vo2_cap"
    assert by_index[12]["target_w"] == 280
    assert by_index[19]["role"] == "vo2_cap"
    assert by_index[26]["role"] == "vo2_cap"
    assert by_index[27]["role"] == "cooldown"


def test_align_labels_lap_7_over_and_vo2_caps():
    prescription = parse_prescribed_workout(ATHLETE_PASTE)
    alignment = align_laps_to_plan(_colombia_laps(), prescription, ftp=232)
    assert alignment["aligned"] is True
    by_index = {row["index"]: row for row in alignment["laps"]}
    assert by_index[7]["role"] == "over"
    assert by_index[12]["role"] == "vo2_cap"
    assert by_index[19]["role"] == "vo2_cap"
    assert by_index[26]["role"] == "vo2_cap"
    assert {row["index"] for row in alignment["vo2_caps"]} == {12, 19, 26}
    assert 7 in {row["index"] for row in alignment["overs"]}
    assert 12 not in {row["index"] for row in alignment["overs"]}


def test_overlay_matches_week_plan_and_mutates_roles():
    laps = _colombia_laps()
    overlay = build_session_plan_overlay(
        message=ATHLETE_PASTE,
        history=[],
        laps=laps,
        ftp=232,
        week_plan={
            "plan": {
                "workouts": [
                    {
                        "date": "2026-09-01",
                        "title": "Cycling quality session",
                        "sport": "Cycling",
                        "session_type": "over-under",
                        "intensity": "hard",
                        "duration_min": 60,
                    }
                ]
            }
        },
        session_date="2026-09-01",
        family="ride",
    )
    assert overlay["week_plan_session"]["title"] == "Cycling quality session"
    assert overlay["week_plan_session"]["sport_match"] is True
    assert overlay["prescription"]["step_count"] == 27
    executed = overlay["prescribed_vs_executed"]
    assert executed["hit_rate"] >= 0.8
    assert [row["lap"] for row in executed["vo2_caps"]] == [12, 19, 26]
    by_index = {lap["index"]: lap for lap in laps}
    assert by_index[7]["role"] == "over"
    assert by_index[12]["role"] == "vo2_cap"


def test_followup_does_not_duplicate_steps_from_history():
    overlay = build_session_plan_overlay(
        message=ATHLETE_PASTE,
        history=[
            {"role": "user", "content": ATHLETE_PASTE},
            {"role": "assistant", "content": "⚡ THE BOTTOM LINE\nLap 7 (over)..."},
            {"role": "user", "content": ATHLETE_PASTE},
        ],
        laps=_colombia_laps(),
        ftp=232,
        week_plan=None,
        session_date="2026-09-01",
        family="ride",
    )
    assert overlay["prescription"]["step_count"] == 27
    assert overlay["prescribed_vs_executed"]["aligned"] is True


def test_correction_message_is_session_analysis():
    assert detect_chat_intent("you got it wrong coach") == "WORKOUT_AUDIT"
    assert detect_chat_intent(ATHLETE_PASTE) == "WORKOUT_AUDIT"
    assert detect_chat_intent("use your schedule to match my workout") == "WORKOUT_AUDIT"


def run() -> None:
    tests = [
        test_parse_expands_three_main_blocks_to_27_steps,
        test_align_labels_lap_7_over_and_vo2_caps,
        test_overlay_matches_week_plan_and_mutates_roles,
        test_followup_does_not_duplicate_steps_from_history,
        test_correction_message_is_session_analysis,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

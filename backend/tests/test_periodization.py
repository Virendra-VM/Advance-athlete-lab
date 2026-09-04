"""Tests for retrograde periodization engine."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import AthleteEvent  # noqa: E402
from app.services.periodization import (  # noqa: E402
    blocks_to_dated_phases,
    build_phase_blocks,
    collapse_blocks,
    distribute_macro_weeks,
    get_week_intent,
    insert_recovery_weeks,
    monday_of,
    season_prompt_block,
    validate_events,
    weeks_between_inclusive,
)
from app.services.periodization import PhaseBlock  # noqa: E402


def test_weeks_between_inclusive():
    start = date(2026, 9, 1)  # Tuesday
    end = date(2026, 9, 14)
    assert weeks_between_inclusive(start, end) >= 2


def test_distribute_macro_weeks_sums_to_total():
    total = 16
    counts = distribute_macro_weeks(total)
    assert sum(counts.values()) == total
    assert counts["taper"] >= 1
    assert counts["peak"] >= 1


def test_short_season_gets_minimum_blocks():
    counts = distribute_macro_weeks(4, short_season=True)
    assert sum(counts.values()) == 4
    assert counts["taper"] == 1


def test_recovery_weeks_inserted_in_base_build():
    blocks = [
        PhaseBlock("base", 4),
        PhaseBlock("build", 4),
    ]
    expanded = insert_recovery_weeks(blocks, every=4)
    types = [block.phase_type for block in expanded]
    assert "recovery_week" in types


def test_collapse_blocks_merges_adjacent():
    merged = collapse_blocks(
        [
            PhaseBlock("base", 1),
            PhaseBlock("base", 2),
            PhaseBlock("build", 1),
        ]
    )
    assert merged == [PhaseBlock("base", 3), PhaseBlock("build", 1)]


def test_build_phase_blocks_includes_taper_and_restore():
    class Profile:
        fitness_level = "Intermediate"
        workout_duration_minutes = 60
        primary_goal = "Train for an event"
        goal_event_name = "Half Marathon"

    start = date(2026, 9, 1)
    a_race = date(2027, 1, 17)
    phases = build_phase_blocks(Profile(), start, a_race)
    types = [phase["phase_type"] for phase in phases]
    assert "base" in types
    assert "build" in types
    assert "taper" in types
    assert types[-1] == "restore"
    assert phases[-2]["phase_type"] == "taper"
    assert phases[-2]["end_date"] == a_race


def test_validate_events_warns_b_race_close_to_a():
    a = AthleteEvent(
        id=1,
        athlete_profile_id=1,
        name="A Race",
        event_date=date(2027, 1, 17),
        priority="A",
        sport_type="run",
        status="planned",
    )
    b = AthleteEvent(
        id=2,
        athlete_profile_id=1,
        name="Tune-up",
        event_date=date(2027, 1, 10),
        priority="B",
        sport_type="run",
        status="planned",
    )
    warnings = validate_events([a, b], a)
    assert any("7 days" in warning for warning in warnings)


def test_get_week_intent_notes_b_race():
    class Phase:
        phase_type = "build"
        intent = "Build"
        volume_bias = 1.0
        intensity_bias = "moderate"
        start_date = date(2026, 10, 5)
        end_date = date(2026, 10, 11)

    class Profile:
        workout_duration_minutes = 60

    event = AthleteEvent(
        id=3,
        athlete_profile_id=1,
        name="10k tune-up",
        event_date=date(2026, 10, 10),
        priority="B",
        sport_type="run",
        status="planned",
    )
    intent = get_week_intent([Phase()], [event], date(2026, 10, 5), Profile())
    assert intent["volume_bias"] < 1.0
    assert any("mini-taper" in note for note in intent["notes"])


def test_season_prompt_block_without_plan():
    text = season_prompt_block({"has_plan": False, "a_race": {"name": "Half", "date": "2027-01-17", "target_metric": "1:35"}})
    assert "A-race" in text
    assert "Generate" in text


def test_blocks_to_dated_phases_end_before_race_week():
    blocks = [PhaseBlock("base", 2), PhaseBlock("build", 2)]
    phases = blocks_to_dated_phases(blocks, date(2026, 9, 7), date(2026, 10, 4))
    assert phases[0]["start_date"] == monday_of(date(2026, 9, 7))
    assert phases[-1]["phase_type"] == "taper"
    assert phases[-1]["start_date"] == monday_of(date(2026, 10, 4))

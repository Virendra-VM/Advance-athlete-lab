"""Tests for retrograde periodization engine."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from datetime import timedelta  # noqa: E402

from app.models import AthleteEvent, AthleteProfile  # noqa: E402
from app.services.periodization import (  # noqa: E402
    PEAK_MAX_WEEKS,
    TAPER_MAX_WEEKS,
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


def test_every_season_length_spends_exactly_its_budget():
    for total in range(2, 61):
        counts = distribute_macro_weeks(total)
        assert sum(counts.values()) == total, total
        assert counts["taper"] >= 1, total
        assert min(counts.values()) >= 0, total


def test_taper_and_peak_stay_inside_physiological_caps():
    counts = distribute_macro_weeks(52)
    # A year of runway must not become a six-week taper; the surplus goes to base.
    assert counts["taper"] == TAPER_MAX_WEEKS
    assert counts["peak"] == PEAK_MAX_WEEKS
    assert counts["base"] > counts["build"] > counts["peak"]


def test_long_season_earns_a_multi_week_taper():
    assert distribute_macro_weeks(8)["taper"] == 1
    assert distribute_macro_weeks(16)["taper"] == 2
    assert distribute_macro_weeks(32)["taper"] == 3


def test_replan_keeps_peak_and_taper_at_full_season_length():
    """Peak is anchored to the A-race, so a shorter runway must not shrink it."""
    full = distribute_macro_weeks(24)
    remaining = distribute_macro_weeks(18, anchor_weeks=24)
    assert remaining["peak"] == full["peak"]
    assert remaining["taper"] == full["taper"]
    # The six lost weeks come out of base and build instead.
    assert remaining["base"] + remaining["build"] == full["base"] + full["build"] - 6
    assert sum(remaining.values()) == 18


def test_recovery_weeks_inserted_in_base_build():
    blocks = [
        PhaseBlock("base", 4),
        PhaseBlock("build", 4),
    ]
    expanded = insert_recovery_weeks(blocks, every=4)
    types = [block.phase_type for block in expanded]
    assert "recovery_week" in types


def test_recovery_weeks_come_out_of_the_block_budget():
    """Recovery weeks are spent from base/build, never added on top of them.

    Adding them used to push the timeline past the A-race, which silently
    squeezed peak and taper out of long seasons.
    """
    blocks = [PhaseBlock("base", 8), PhaseBlock("build", 4)]
    expanded = insert_recovery_weeks(blocks, every=4)
    assert sum(block.week_count for block in expanded) == 12
    assert sum(1 for block in expanded if block.phase_type == "recovery_week") == 3


def test_recovery_cycle_resets_per_block():
    """A short build block never opens on a recovery week it cannot afford."""
    expanded = insert_recovery_weeks([PhaseBlock("base", 3), PhaseBlock("build", 2)], every=4)
    assert [block.phase_type for block in expanded] == ["base", "build"]
    assert [block.week_count for block in expanded] == [3, 2]


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


def test_blocks_never_overlap_reserved_race_week():
    """Race week belongs to the taper, so the block before it stops on Sunday."""
    race = date(2026, 10, 4)  # a Sunday
    phases = blocks_to_dated_phases(
        [PhaseBlock("base", 2), PhaseBlock("build", 2)], date(2026, 9, 7), race
    )
    taper = phases[-1]
    assert phases[-2]["end_date"] < taper["start_date"]
    assert taper["end_date"] == race


def test_trailing_taper_block_merges_into_race_week():
    """A planned two-week taper is one contiguous phase, not two adjacent ones."""
    phases = blocks_to_dated_phases(
        [PhaseBlock("build", 2), PhaseBlock("taper", 1)],
        date(2026, 9, 7),
        date(2026, 10, 4),
    )
    tapers = [row for row in phases if row["phase_type"] == "taper"]
    assert len(tapers) == 1
    assert tapers[0]["week_count"] == 2
    assert tapers[0]["end_date"] == date(2026, 10, 4)


def _profile(**overrides):
    defaults = {
        "name": "Test",
        "age": 34,
        "weight": 70.0,
        "fitness_level": "intermediate",
        "workout_duration_minutes": 60,
    }
    return AthleteProfile(**{**defaults, **overrides})


def test_plan_is_contiguous_and_lands_on_race_day_for_any_length():
    """The structural contract of a season, checked across every plausible span.

    Phases must tile the season with no overlap and no gap, the taper must end on
    the A-race, and restore must follow it.
    """
    start = date(2026, 9, 7)  # a Monday
    for weeks in range(2, 53):
        race = start + timedelta(weeks=weeks) - timedelta(days=1)
        phases = build_phase_blocks(_profile(), start, race)

        for prev, nxt in zip(phases, phases[1:]):
            assert nxt["start_date"] == prev["end_date"] + timedelta(days=1), (
                weeks,
                prev["phase_type"],
                nxt["phase_type"],
            )

        assert phases[-1]["phase_type"] == "restore", weeks
        assert phases[-2]["phase_type"] == "taper", weeks
        assert phases[-2]["end_date"] == race, weeks
        assert phases[0]["start_date"] == start, weeks

        planned = phases[:-1]
        spent = sum(row["week_count"] for row in planned)
        assert spent == weeks_between_inclusive(start, race), weeks


def test_long_seasons_keep_a_peak_phase():
    """Recovery weeks used to overflow the budget and push peak off the end."""
    start = date(2026, 9, 7)
    for weeks in range(8, 53):
        race = start + timedelta(weeks=weeks) - timedelta(days=1)
        types = {row["phase_type"] for row in build_phase_blocks(_profile(), start, race)}
        assert "peak" in types, weeks
        assert "build" in types, weeks


def test_long_build_up_earns_a_two_week_restore():
    start = date(2026, 9, 7)
    short = build_phase_blocks(_profile(), start, start + timedelta(weeks=10))
    long = build_phase_blocks(_profile(), start, start + timedelta(weeks=24))
    assert short[-1]["week_count"] == 1
    assert long[-1]["week_count"] == 2


def test_baseline_lowers_long_session_ceiling_and_damps_loading_volume():
    start = date(2026, 9, 7)
    race = start + timedelta(weeks=16)
    baseline = {
        "long_session_ceiling_min": 75,
        "volume_damp": 0.88,
        "recovery_cycle_weeks": 4,
    }
    phases = build_phase_blocks(_profile(), start, race, baseline=baseline)
    by_type = {row["phase_type"]: row for row in phases}

    # Base normally allows a four-hour long day; this athlete has not earned it.
    assert by_type["base"]["long_session_allowed_min"] == 75
    assert by_type["base"]["volume_bias"] == round(1.1 * 0.88, 2)
    # Already-reduced phases are not damped a second time, and the ceiling is
    # never raised above the phase default.
    assert by_type["restore"]["volume_bias"] == 0.4
    assert by_type["restore"]["long_session_allowed_min"] == 60


def test_shorter_recovery_cycle_adds_more_down_weeks():
    start = date(2026, 9, 7)
    race = start + timedelta(weeks=20)

    def down_weeks(cycle):
        phases = build_phase_blocks(
            _profile(), start, race, baseline={"recovery_cycle_weeks": cycle}
        )
        return sum(row["week_count"] for row in phases if row["phase_type"] == "recovery_week")

    assert down_weeks(3) > down_weeks(4)

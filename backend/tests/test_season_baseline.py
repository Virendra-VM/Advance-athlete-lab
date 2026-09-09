"""Tests for the athlete carrying-capacity rules behind season planning."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.season_baseline import (  # noqa: E402
    DEFAULT_RECOVERY_CYCLE_WEEKS,
    MIN_LONG_SESSION_MIN,
    SHORT_RECOVERY_CYCLE_WEEKS,
    analyze_extended_load_response,
    compose_season_baseline,
    scale_long_session,
    scale_volume_bias,
)


def _trained(**overrides):
    """A baseline with enough history to be trusted."""
    defaults = {
        "fitness_level": "intermediate",
        "age": 34,
        "typical_session_minutes": 60,
        "longest_logged_minutes": 120,
        "weeks_with_training": 5,
        "acwr": 1.0,
    }
    return compose_season_baseline(**{**defaults, **overrides})


def test_long_day_ceiling_steps_up_from_the_longest_logged_session():
    baseline = _trained(longest_logged_minutes=120)
    assert baseline["longest_session_min"] == 120
    assert baseline["longest_session_source"] == "logged"
    # 120 min + 30% is 156, rounded to the nearest quarter hour.
    assert baseline["long_session_ceiling_min"] == 150


def test_self_reported_history_counts_when_no_device_data_exists():
    baseline = _trained(
        longest_logged_minutes=None,
        longest_recent_session="2 hours",
        weeks_with_training=0,
    )
    assert baseline["longest_session_min"] == 120
    assert baseline["longest_session_source"] == "reported"


def test_a_longer_logged_session_beats_a_stale_self_report():
    baseline = _trained(longest_logged_minutes=180, longest_recent_session="90 min")
    assert baseline["longest_session_min"] == 180
    assert baseline["longest_session_source"] == "logged"


def test_no_history_at_all_stays_conservative_and_says_so():
    baseline = compose_season_baseline(
        typical_session_minutes=45, weeks_with_training=0
    )
    assert baseline["longest_session_source"] == "typical"
    assert baseline["confidence"] == "low"
    assert baseline["thin_baseline"] is True
    assert baseline["long_session_ceiling_min"] >= MIN_LONG_SESSION_MIN
    # Twice a 45 min session is below the 90 min floor, so the floor wins.
    assert baseline["long_session_ceiling_min"] <= 120
    assert any("no long sessions on record" in note for note in baseline["notes"])


def test_active_injury_damps_volume_and_shortens_the_recovery_cycle():
    baseline = _trained(active_injuries=["knee (patellar tendinopathy)"])
    assert baseline["volume_damp"] < 1.0
    assert baseline["recovery_cycle_weeks"] == SHORT_RECOVERY_CYCLE_WEEKS
    assert any("knee" in note for note in baseline["notes"])


def test_severe_injury_damps_harder_than_a_mild_one():
    mild = _trained(active_injuries=["calf"])
    severe = _trained(active_injuries=["calf"], has_severe_active_injury=True)
    assert severe["volume_damp"] < mild["volume_damp"]


def test_masters_athlete_gets_a_shorter_recovery_cycle():
    assert _trained(age=34)["recovery_cycle_weeks"] == DEFAULT_RECOVERY_CYCLE_WEEKS
    assert _trained(age=55)["recovery_cycle_weeks"] == SHORT_RECOVERY_CYCLE_WEEKS


def test_beginner_gets_a_shorter_recovery_cycle():
    assert (
        _trained(fitness_level="Beginner")["recovery_cycle_weeks"]
        == SHORT_RECOVERY_CYCLE_WEEKS
    )


def test_spiking_load_damps_volume_when_there_is_enough_history():
    baseline = _trained(acwr=1.8, weeks_with_training=5)
    assert baseline["volume_damp"] < 1.0
    assert any("1.8" in note for note in baseline["notes"])


def test_spiking_load_is_ignored_when_the_28_day_average_is_empty():
    """One logged week makes any ACWR look enormous; that is an artefact."""
    baseline = _trained(acwr=4.0, weeks_with_training=1)
    assert baseline["volume_damp"] == 1.0
    assert any("logged training" in note for note in baseline["notes"])


def test_scale_long_session_never_raises_a_phase_above_its_default():
    generous = {"long_session_ceiling_min": 600}
    assert scale_long_session(180, generous) == 180
    assert scale_long_session(60, generous) == 60


def test_scale_long_session_lowers_a_phase_to_what_was_earned():
    modest = {"long_session_ceiling_min": 75}
    assert scale_long_session(240, modest) == 75
    # And never below the usable floor.
    assert scale_long_session(240, {"long_session_ceiling_min": 10}) == MIN_LONG_SESSION_MIN


def test_scale_long_session_falls_back_to_the_default_without_a_baseline():
    assert scale_long_session(240, None) == 240
    assert scale_long_session(240, {}) == 240


def test_only_loading_phases_are_damped():
    baseline = {"volume_damp": 0.8}
    assert scale_volume_bias(1.1, baseline, loading=True) == 0.88
    # Taper and restore are already reduced; damping them again would be wrong.
    assert scale_volume_bias(0.55, baseline, loading=False) == 0.55
    assert scale_volume_bias(1.1, None, loading=True) == 1.1


def test_confidence_tracks_how_much_history_exists():
    assert _trained(weeks_with_training=5)["confidence"] == "high"
    assert _trained(weeks_with_training=1)["confidence"] == "medium"
    assert (
        compose_season_baseline(typical_session_minutes=45, weeks_with_training=0)[
            "confidence"
        ]
        == "low"
    )


def test_every_baseline_explains_itself():
    """A cap the athlete cannot explain is a cap they will ignore."""
    for baseline in (
        _trained(),
        _trained(active_injuries=["knee"]),
        _trained(age=60, acwr=1.9),
        compose_season_baseline(weeks_with_training=0),
    ):
        assert baseline["notes"]
        assert all(note.strip().endswith(".") for note in baseline["notes"])


def test_extended_load_response_detects_fast_fatiguer_pattern():
    weekly = []
    for index in range(12):
        minutes = 300 if index % 4 != 3 else 120
        weekly.append({"week_start": index, "minutes": minutes, "sessions": 3})
    extended = analyze_extended_load_response(weekly)
    assert extended["load_response_pattern"] == "fast_fatiguer"
    assert extended["load_breakdown_signals"] >= 2


def test_extended_history_shortens_recovery_cycle_when_breakdowns_repeat():
    baseline = compose_season_baseline(
        fitness_level="intermediate",
        typical_session_minutes=60,
        longest_logged_minutes=120,
        weeks_with_training=5,
        extended_weeks_with_training=12,
        load_response_pattern="fast_fatiguer",
        load_breakdown_signals=3,
        extended_notes=["Extended history note."],
    )
    assert baseline["recovery_cycle_weeks"] == SHORT_RECOVERY_CYCLE_WEEKS
    assert any("load breakdowns" in note for note in baseline["notes"])


def run() -> None:
    tests = [
        test_long_day_ceiling_steps_up_from_the_longest_logged_session,
        test_self_reported_history_counts_when_no_device_data_exists,
        test_a_longer_logged_session_beats_a_stale_self_report,
        test_no_history_at_all_stays_conservative_and_says_so,
        test_active_injury_damps_volume_and_shortens_the_recovery_cycle,
        test_severe_injury_damps_harder_than_a_mild_one,
        test_masters_athlete_gets_a_shorter_recovery_cycle,
        test_beginner_gets_a_shorter_recovery_cycle,
        test_spiking_load_damps_volume_when_there_is_enough_history,
        test_spiking_load_is_ignored_when_the_28_day_average_is_empty,
        test_scale_long_session_never_raises_a_phase_above_its_default,
        test_scale_long_session_lowers_a_phase_to_what_was_earned,
        test_scale_long_session_falls_back_to_the_default_without_a_baseline,
        test_only_loading_phases_are_damped,
        test_confidence_tracks_how_much_history_exists,
        test_every_baseline_explains_itself,
        test_extended_load_response_detects_fast_fatiguer_pattern,
        test_extended_history_shortens_recovery_cycle_when_breakdowns_repeat,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run()

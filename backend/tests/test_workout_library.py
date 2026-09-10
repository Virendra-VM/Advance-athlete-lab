"""Science Workout Library — Phase 1 tests."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coach_safety import compose_safety_profile  # noqa: E402
from app.services.coach_templates import build_template_week  # noqa: E402
from app.services.session_blueprints import enrich_workout  # noqa: E402
from app.services.workout_library import (  # noqa: E402
    anchors_from_physiology,
    apply_library_template,
    clear_library_cache,
    format_pace,
    library_stats,
    list_templates,
    load_templates,
    parse_pace_seconds,
    pick_template,
    physiology_from_context,
    render_structure,
    resolve_target_band,
)


def _physiology_run():
    return {
        "lthr_bpm": 170,
        "ftp_watts": 250,
        "threshold_pace": "4:30/km",
        "css_sec_per_100m": 95,
    }


def test_library_loads_minimum_catalog_size():
    clear_library_cache()
    templates, version = load_templates()
    stats = library_stats()
    assert version == "2.0.0"
    assert len(templates) >= 200, f"expected ≥200 templates, got {len(templates)}"
    assert stats["total"] >= 200
    assert stats["unique_ids"] >= 200
    assert stats["by_sport"].get("running", 0) >= 10
    assert stats["by_sport"].get("cycling", 0) >= 10
    assert stats["by_sport"].get("swimming", 0) >= 8
    assert stats["by_sport"].get("strength", 0) >= 8
    assert stats["by_sport"].get("mobility", 0) >= 8
    assert stats["by_sport"].get("trail_running", 0) >= 6
    assert stats["by_sport"].get("triathlon", 0) >= 4


def test_parse_pace_seconds_formats():
    assert parse_pace_seconds("4:30/km") == 270
    assert parse_pace_seconds("5:30") == 330
    assert parse_pace_seconds(270) == 270.0
    assert format_pace(270) == "4:30/km"


def test_resolve_target_band_lthr_and_ftp():
    anchors = anchors_from_physiology(_physiology_run())
    hr = resolve_target_band({"hr_pct_lthr": {"low": 0.95, "high": 1.02}}, anchors)
    assert "bpm" in hr["hr"]
    assert "170" not in hr["hr"] or "161" in hr["hr"] or "173" in hr["hr"]

    power = resolve_target_band({"pct_ftp": {"low": 0.91, "high": 1.05}}, anchors)
    assert "W" in power["power"]
    assert "228" in power["power"] or "227" in power["power"]

    pace = resolve_target_band({"pace_pct_threshold": {"low": 0.98, "high": 1.02}}, anchors)
    assert "/km" in pace["pace"]


def test_resolve_target_band_css():
    anchors = anchors_from_physiology(_physiology_run())
    swim = resolve_target_band({"css_pct": {"low": 0.98, "high": 1.02}}, anchors)
    assert "/100m" in swim["swim_pace"]


def test_pick_template_run_threshold():
    template = pick_template(
        {"sport": "Running", "session_type": "threshold", "title": "Threshold session"},
    )
    assert template is not None
    assert template["id"] in {"run_threshold_2x10_lthr1", "run_threshold_3x8_lthr2"}


def test_pick_template_bike_sweet_spot():
    template = pick_template(
        {
            "sport": "Cycling",
            "session_type": "threshold",
            "title": "Sweet spot ride",
        },
    )
    assert template is not None
    assert template["id"] == "bike_sweet_spot_2x20"


def test_pick_template_bike_vo2():
    template = pick_template(
        {"sport": "Cycling", "session_type": "intervals", "title": "VO2 session"},
    )
    assert template is not None
    assert "vo2" in template["id"]


def test_pick_template_trail_hills():
    template = pick_template(
        {"sport": "Trail running", "session_type": "hills", "title": "Trail hills"},
    )
    assert template is not None
    assert template["sports"] == ["trail_running"] or "trail" in template["id"]


def test_pick_template_strength_spine_lock():
    template = pick_template(
        {"sport": "Strength training", "session_type": "strength", "title": "Gym"},
        safety={"spine_lock": True},
    )
    assert template is not None
    assert template["id"] == "strength_spine_lock"


def test_pick_template_strength_normal():
    template = pick_template(
        {"sport": "Strength training", "session_type": "strength", "title": "Gym"},
        safety={"spine_lock": False},
    )
    assert template is not None
    assert template["id"] == "strength_full_body"


def test_pick_template_swim_css():
    template = pick_template(
        {"sport": "Swimming", "session_type": "threshold", "title": "CSS set"},
    )
    assert template is not None
    assert "css" in template["id"]


def test_render_structure_includes_zone_targets():
    template = pick_template(
        {"sport": "Running", "session_type": "threshold", "title": "Threshold"},
    )
    assert template is not None
    structure = render_structure(
        template,
        {"duration_min": 50, "sport": "Running", "session_type": "threshold"},
        anchors_from_physiology(_physiology_run()),
    )
    assert len(structure) == 3
    main = next(item for item in structure if item["segment"] == "Main set")
    assert "10 min" in main["detail"] or "threshold" in main["detail"].lower()
    assert "bpm" in main["detail"] or "LTHR" in main["intensity"] or "/km" in main["detail"]


def test_apply_library_template_sets_template_id():
    result = apply_library_template(
        {
            "sport": "Cycling",
            "session_type": "threshold",
            "title": "Threshold ride",
            "duration_min": 60,
            "structure": [],
        },
        _physiology_run(),
    )
    assert result is not None
    assert result.get("library_template_id")
    assert result.get("library_version") == "2.0.0"
    assert len(result["structure"]) == 3
    main = next(item for item in result["structure"] if item["segment"] == "Main set")
    assert "FTP" in main["detail"] or "W" in main["detail"]


def test_enrich_workout_uses_library_with_physiology():
    workout = enrich_workout(
        {
            "sport": "Running",
            "session_type": "threshold",
            "duration_min": 50,
            "structure": [],
        },
        physiology=_physiology_run(),
    )
    assert workout.get("library_template_id")
    main = next(item for item in workout["structure"] if item["segment"] == "Main set")
    assert "bpm" in main["detail"] or "/km" in main["detail"]


def test_enrich_workout_falls_back_without_physiology():
    workout = enrich_workout(
        {
            "sport": "Running",
            "session_type": "threshold",
            "duration_min": 50,
            "structure": [],
        },
    )
    assert workout.get("library_template_id")
    main = next(item for item in workout["structure"] if item["segment"] == "Main set")
    assert len(main["detail"]) >= 24


def test_enrich_workout_mobility_from_library():
    workout = enrich_workout(
        {
            "sport": "Yoga / mobility",
            "session_type": "mobility",
            "duration_min": 30,
            "structure": [],
        },
    )
    assert workout.get("library_template_id")
    main = next(item for item in workout["structure"] if item["segment"] == "Main set")
    assert "warrior" in main["detail"].lower() or "flow" in main["detail"].lower()


def test_list_templates_by_sport_and_intent():
    run_threshold = list_templates(sport="running", intent="threshold")
    assert len(run_threshold) >= 2
    bike_vo2 = list_templates(sport="cycling", intent="vo2")
    assert len(bike_vo2) >= 2


def test_physiology_from_context_merges_profile_and_coros():
    ctx = {
        "profile": {"ftp_watts": 260, "lthr_bpm": 168},
        "physiology": {"max_hr_bpm": 190},
        "coros": {"fitness": {"threshold_pace": "4:25/km"}},
    }
    merged = physiology_from_context(ctx)
    assert merged["ftp_watts"] == 260
    assert merged["lthr_bpm"] == 168
    assert merged["max_hr_bpm"] == 190
    assert merged["threshold_pace_sec_per_km"] == 265
    assert merged["run_pace_zones"]


def test_template_week_quality_uses_library():
    safety = compose_safety_profile(
        days_per_week=4,
        session_minutes=50,
        weekly_minutes_budget=200,
        fitness_level="Intermediate",
        injuries={
            "active": [],
            "past": [],
            "avoid_keywords": [],
            "avoid_session_types": [],
            "prefer": [],
            "has_severe_active": False,
        },
        readiness_flags=[],
        load={"acute_minutes": 200, "chronic_minutes": 200, "minutes_acwr": 1.0},
    )
    context = {
        "profile": {
            "primary_goal": "half marathon",
            "sports": [{"sport": "Running", "priority": "primary"}],
            "ftp_watts": None,
            "lthr_bpm": 172,
            "threshold_pace": "4:40/km",
        },
        "physiology": {"lthr_bpm": 172, "threshold_pace": "4:40/km"},
    }
    week_start = date(2026, 3, 2)
    plan = build_template_week(context, safety, week_start, today=week_start)
    quality = next(
        workout for workout in plan["workouts"] if workout.get("session_type") == "threshold"
    )
    assert quality.get("library_template_id")
    main = next(item for item in quality["structure"] if item["segment"] == "Main set")
    assert "bpm" in main["detail"] or "/km" in main["detail"]


def test_all_templates_have_evidence_tags():
    templates, _ = load_templates()
    missing = [item["id"] for item in templates if not item.get("evidence_tags")]
    assert not missing, f"templates missing evidence_tags: {missing[:5]}"


def test_all_templates_have_required_fields():
    templates, _ = load_templates()
    for template in templates:
        assert template.get("id"), "template missing id"
        assert template.get("intent"), f"{template.get('id')} missing intent"
        assert template.get("main"), f"{template.get('id')} missing main"
        sports = template.get("sports") or [template.get("sport")]
        assert sports and sports[0], f"{template.get('id')} missing sport"

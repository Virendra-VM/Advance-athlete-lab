"""Phase 2 — phase-aware workout selection engine tests."""

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
from app.services.workout_selection import (  # noqa: E402
    apply_library_selection_to_plan,
    build_library_week,
    phase_type_from_context,
    select_template_for_slot,
)


def _safety(days=4):
    return compose_safety_profile(
        days_per_week=days,
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


def _context(phase_type="build", sports=None):
    return {
        "profile": {
            "primary_goal": "half marathon",
            "sports": sports or [{"sport": "Running", "priority": "primary"}],
            "lthr_bpm": 172,
            "threshold_pace": "4:40/km",
        },
        "physiology": {"lthr_bpm": 172, "threshold_pace": "4:40/km"},
        "season": {
            "has_plan": True,
            "current_phase": {"phase_type": phase_type},
            "week_intent": {
                "phase_type": phase_type,
                "volume_bias": 1.0,
                "long_session_allowed_min": 180,
            },
        },
    }


def test_phase_type_from_context_defaults_base():
    assert phase_type_from_context({}) == "base"
    assert phase_type_from_context(_context("peak")) == "peak"


def test_build_phase_selects_vo2_in_build():
    plan = build_library_week(
        _context("build"),
        _safety(),
        date(2026, 3, 2),
        today=date(2026, 3, 2),
    )
    assert plan.get("selection_engine") == "swl-v2"
    template_ids = [row.get("library_template_id") for row in plan["workouts"]]
    assert all(template_ids), "every slot should have a library template id"
    assert "run_vo2_5x3" in template_ids or "run_threshold_2x10_lthr1" in template_ids


def test_build_phase_taper_selects_shakeout_not_vo2():
    plan = build_library_week(
        _context("taper"),
        _safety(),
        date(2026, 3, 2),
        today=date(2026, 3, 2),
    )
    template_ids = [row.get("library_template_id") for row in plan["workouts"]]
    assert "run_vo2_5x3" not in template_ids
    assert any(
        tid in template_ids
        for tid in ("run_taper_shakeout", "run_easy_z2", "run_recovery_jog")
    )


def test_build_cycling_build_sweet_spot_or_vo2():
    ctx = _context("build", sports=[{"sport": "Cycling", "priority": "primary"}])
    ctx["physiology"] = {"ftp_watts": 250}
    plan = build_library_week(ctx, _safety(), date(2026, 3, 2), today=date(2026, 3, 2))
    ids = [row.get("library_template_id") for row in plan["workouts"]]
    assert "bike_sweet_spot_2x20" in ids or "bike_vo2_5x3" in ids or "bike_threshold_3x10" in ids


def test_select_template_trail_hills_in_build():
    template = select_template_for_slot(
        sport="Trail running",
        slot="quality",
        phase_type="build",
        quality_index=0,
    )
    assert template is not None
    assert template["id"] == "trail_hills_8x60"


def test_select_template_spine_lock_strength():
    template = select_template_for_slot(
        sport="Strength training",
        slot="strength",
        phase_type="build",
        safety={"spine_lock": True},
    )
    assert template is not None
    assert template["id"] == "strength_spine_lock"


def test_apply_library_selection_to_llm_plan():
    raw_plan = {
        "title": "Test week",
        "summary": "LLM week",
        "week_start": "2026-03-02",
        "workouts": [
            {
                "date": "2026-03-02",
                "sport": "Running",
                "title": "Easy run",
                "session_type": "easy",
                "duration_min": 45,
                "structure": [{"segment": "Main", "duration_min": 45, "detail": "vague"}],
            },
            {
                "date": "2026-03-04",
                "sport": "Running",
                "title": "Quality session",
                "session_type": "threshold",
                "duration_min": 50,
                "structure": [],
            },
        ],
    }
    selected = apply_library_selection_to_plan(raw_plan, _context("build"), _safety())
    for workout in selected["workouts"]:
        assert workout.get("library_template_id")
    quality = next(w for w in selected["workouts"] if w["session_type"] == "threshold")
    assert quality["library_template_id"] in {
        "run_threshold_2x10_lthr1",
        "run_vo2_5x3",
        "run_threshold_3x8_lthr2",
    }


def test_apply_selection_clears_thin_llm_structure_for_enrichment():
    raw_plan = {
        "title": "Test",
        "summary": "s",
        "week_start": "2026-03-02",
        "workouts": [
            {
                "date": "2026-03-04",
                "sport": "Cycling",
                "title": "Bike quality",
                "session_type": "intervals",
                "duration_min": 60,
                "structure": [{"segment": "Main", "duration_min": 40, "detail": "hard"}],
            }
        ],
    }
    selected = apply_library_selection_to_plan(raw_plan, _context("build"), _safety())
    workout = selected["workouts"][0]
    assert workout.get("library_template_id")
    assert workout["structure"] == []
    enriched = enrich_workout(workout, physiology={"ftp_watts": 250})
    main = next(s for s in enriched["structure"] if s["segment"] == "Main set")
    assert "FTP" in main["detail"] or "W" in main["detail"]


def test_build_template_week_delegates_to_library():
    plan = build_template_week(
        _context("build"),
        _safety(),
        date(2026, 3, 2),
        today=date(2026, 3, 2),
    )
    assert all(row.get("library_template_id") for row in plan["workouts"])
    quality = next(
        row for row in plan["workouts"] if row.get("session_type") in {"threshold", "intervals"}
    )
    main = next(s for s in quality["structure"] if s["segment"] == "Main set")
    assert len(main["detail"]) >= 24


def test_swim_build_selects_css_or_vo2():
    ctx = _context(
        "build",
        sports=[{"sport": "Swimming", "priority": "primary"}],
    )
    ctx["physiology"] = {"css_sec_per_100m": 95}
    plan = build_library_week(ctx, _safety(days=3), date(2026, 3, 2), today=date(2026, 3, 2))
    ids = [row.get("library_template_id") for row in plan["workouts"]]
    assert any("swim_" in (tid or "") for tid in ids)


def test_restore_phase_easy_templates_only():
    plan = build_library_week(
        _context("restore"),
        _safety(days=2),
        date(2026, 3, 2),
        today=date(2026, 3, 2),
    )
    for workout in plan["workouts"]:
        assert workout.get("session_type") in {"easy", "mobility", "rest"}
